import re
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import redis
from celery.utils.log import get_task_logger

from app.worker.celery_app import celery_app
from app.worker.db import SyncSessionFactory
from app.models.campaign import Campaign, CampaignJob
from app.models.dead_letter import DeadLetterJob
from app.models.smtp_channel import SmtpChannel
from app.models.subscriber import Subscriber
from app.models.template import EmailTemplate
from app.models.tracking import TrackingLink
from app.core.encryption import decrypt_value
from app.core.template_engine import render_template
from app.config import settings
from sqlalchemy import select, update

logger = get_task_logger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _select_channel_with_failover(db, tenant_id: uuid.UUID, exclude_ids: list[uuid.UUID] | None = None) -> SmtpChannel | None:
    """Select best available SMTP channel considering health, priority, and rate limits."""
    filters = [
        SmtpChannel.tenant_id == tenant_id,
        SmtpChannel.is_active.is_(True),
        SmtpChannel.deleted_at.is_(None),
        SmtpChannel.consecutive_failures < 5,
    ]
    if exclude_ids:
        filters.append(SmtpChannel.id.notin_(exclude_ids))

    channels = db.execute(
        select(SmtpChannel).where(*filters).order_by(SmtpChannel.priority.asc())
    ).scalars().all()

    r = _get_redis()
    now = datetime.now(timezone.utc)
    hourly_key_prefix = now.strftime("%Y-%m-%dT%H")
    daily_key_prefix = now.strftime("%Y-%m-%d")

    for channel in channels:
        hourly_key = f"channel:{channel.id}:hourly:{hourly_key_prefix}"
        daily_key = f"channel:{channel.id}:daily:{daily_key_prefix}"
        try:
            hourly_count = int(r.get(hourly_key) or 0)
            daily_count = int(r.get(daily_key) or 0)
        except Exception:
            hourly_count = 0
            daily_count = 0

        if hourly_count >= channel.hourly_limit:
            continue
        if daily_count >= channel.daily_limit:
            continue
        return channel

    return None


def _record_channel_send(channel_id: uuid.UUID):
    """Increment Redis rate-limit counters for the channel."""
    r = _get_redis()
    now = datetime.now(timezone.utc)
    hourly_key = f"channel:{channel_id}:hourly:{now.strftime('%Y-%m-%dT%H')}"
    daily_key = f"channel:{channel_id}:daily:{now.strftime('%Y-%m-%d')}"
    pipe = r.pipeline()
    pipe.incr(hourly_key)
    pipe.expire(hourly_key, 3600)
    pipe.incr(daily_key)
    pipe.expire(daily_key, 86400)
    pipe.execute()


def _check_tenant_limit(tenant_id: uuid.UUID) -> bool:
    """Check if tenant daily send limit is reached. Returns True if OK to send."""
    r = _get_redis()
    now = datetime.now(timezone.utc)
    key = f"tenant:{tenant_id}:daily:{now.strftime('%Y-%m-%d')}"
    try:
        count = int(r.get(key) or 0)
    except Exception:
        return True
    return count < settings.tenant_daily_send_limit


def _record_tenant_send(tenant_id: uuid.UUID):
    """Increment tenant daily send counter."""
    r = _get_redis()
    now = datetime.now(timezone.utc)
    key = f"tenant:{tenant_id}:daily:{now.strftime('%Y-%m-%d')}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)
    pipe.execute()


LINK_PATTERN = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)


def _rewrite_links_for_tracking(db, html: str, campaign_id: uuid.UUID, tenant_id: uuid.UUID, subscriber_id: uuid.UUID) -> str:
    """Find all links in HTML, create TrackingLink records, and rewrite URLs to tracking redirects."""
    urls_found = LINK_PATTERN.findall(html)
    if not urls_found:
        return html

    for original_url in set(urls_found):
        # Skip non-http links, anchors, unsubscribe links
        if original_url.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        if "unsubscribe" in original_url.lower():
            continue

        # Check if tracking link already exists for this campaign+url
        existing = db.execute(
            select(TrackingLink).where(
                TrackingLink.campaign_id == campaign_id,
                TrackingLink.original_url == original_url,
            )
        ).scalar_one_or_none()

        if existing:
            tracking_code = existing.tracking_code
        else:
            tracking_code = uuid.uuid4().hex[:12]
            link = TrackingLink(
                tenant_id=tenant_id,
                campaign_id=campaign_id,
                original_url=original_url,
                tracking_code=tracking_code,
            )
            db.add(link)
            db.flush()

        # Rewrite the URL in HTML — append subscriber ID for identification
        tracking_url = f"{settings.tracking_base_url}/click/{tracking_code}?sid={subscriber_id}"
        html = html.replace(f'"{original_url}"', f'"{tracking_url}"')
        html = html.replace(f"'{original_url}'", f"'{tracking_url}'")

    return html


def _inject_tracking_pixel(html: str, job_id: str) -> str:
    """Inject open-tracking pixel into HTML."""
    pixel = f'<img src="{settings.tracking_base_url}/pixel/{job_id}.gif" width="1" height="1" alt="" style="display:none" />'
    if "</body>" in html:
        html = html.replace("</body>", f"{pixel}</body>")
    else:
        html += pixel
    return html


@celery_app.task(queue="send", bind=True, max_retries=3, rate_limit="100/m")
def send_email(self, job_id: str):
    with SyncSessionFactory() as db:
        job = db.execute(
            select(CampaignJob).where(CampaignJob.id == uuid.UUID(job_id))
        ).scalar_one_or_none()
        if not job:
            return
        if job.status == "sent":
            return  # Idempotency

        campaign = db.execute(
            select(Campaign).where(Campaign.id == job.campaign_id)
        ).scalar_one_or_none()
        if not campaign or campaign.status in ("paused", "cancelled"):
            job.status = "pending"
            db.commit()
            return

        subscriber = db.execute(
            select(Subscriber).where(Subscriber.id == job.subscriber_id)
        ).scalar_one_or_none()
        if not subscriber:
            job.status = "failed"
            job.error_message = "Subscriber not found"
            job.failed_at = datetime.now(timezone.utc)
            db.commit()
            return

        template = db.execute(
            select(EmailTemplate).where(EmailTemplate.id == campaign.template_id)
        ).scalar_one_or_none()
        if not template:
            job.status = "failed"
            job.error_message = "Template not found"
            job.failed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Check tenant daily limit
        if not _check_tenant_limit(campaign.tenant_id):
            _handle_retry(self, job, db, "Tenant daily send limit reached")
            return

        # Select channel with failover — try multiple channels
        tried_channel_ids: list[uuid.UUID] = []
        channel = None
        while True:
            channel = _select_channel_with_failover(db, campaign.tenant_id, exclude_ids=tried_channel_ids or None)
            if not channel:
                break
            tried_channel_ids.append(channel.id)
            # Found a valid channel
            break

        if not channel:
            _handle_retry(self, job, db, "No available SMTP channel (all exhausted or rate-limited)")
            return

        # Render template
        variables = {
            "email": subscriber.email,
            "name": subscriber.name or "",
            **(subscriber.custom_fields or {}),
        }
        try:
            rendered_subject = render_template(template.subject, variables)
            rendered_html = render_template(template.html_body, variables)
        except Exception as e:
            job.status = "failed"
            job.error_message = f"Template render error: {e}"
            job.failed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Rewrite links for click tracking (creates TrackingLink records)
        rendered_html = _rewrite_links_for_tracking(
            db, rendered_html, campaign.id, campaign.tenant_id, subscriber.id
        )

        # Inject open-tracking pixel
        rendered_html = _inject_tracking_pixel(rendered_html, str(job.id))

        # Build email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = rendered_subject
        msg["From"] = f"{campaign.sender_name or settings.default_sender_name} <{campaign.sender_email or channel.username or settings.default_sender_email}>"
        msg["To"] = subscriber.email
        if campaign.reply_to:
            msg["Reply-To"] = campaign.reply_to
        msg["X-Mailer"] = "MailGenius"
        msg["List-Unsubscribe"] = f"<{settings.public_api_url}/api/v1/subscription/unsubscribe/{subscriber.id}?campaign={campaign.id}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        if template.text_body:
            rendered_text = render_template(template.text_body, variables)
            msg.attach(MIMEText(rendered_text, "plain"))
        msg.attach(MIMEText(rendered_html, "html"))

        # Attempt sending — loop through all channels by priority on failure
        import asyncio
        last_error = None
        current_channel = channel

        while current_channel:
            password = decrypt_value(current_channel.password_encrypted) if current_channel.password_encrypted else None
            try:
                loop = asyncio.new_event_loop()
                message_id = loop.run_until_complete(
                    _async_send(current_channel.host, current_channel.port, current_channel.use_tls, current_channel.username, password, msg)
                )
                loop.close()

                # Success — commit job status first (critical path)
                job.status = "sent"
                job.message_id = message_id
                job.sent_at = datetime.now(timezone.utc)
                current_channel.last_success_at = datetime.now(timezone.utc)
                current_channel.consecutive_failures = 0
                campaign.sent_count += 1
                db.commit()

                # Record rate limit counters (non-critical — failures are logged only)
                try:
                    _record_channel_send(current_channel.id)
                    _record_tenant_send(campaign.tenant_id)
                except Exception as redis_err:
                    logger.warning(f"Redis counter update failed (non-fatal): {redis_err}")

                return

            except Exception as e:
                last_error = e
                current_channel.last_failure_at = datetime.now(timezone.utc)
                current_channel.consecutive_failures += 1
                db.commit()
                tried_channel_ids.append(current_channel.id)
                current_channel = _select_channel_with_failover(db, campaign.tenant_id, exclude_ids=tried_channel_ids)

        # All channels exhausted — retry with backoff
        _handle_retry(self, job, db, f"SMTP send failed (all channels exhausted): {last_error}")


async def _async_send(host, port, use_tls, username, password, msg) -> str:
    smtp = aiosmtplib.SMTP(hostname=host, port=port, use_tls=use_tls)
    await smtp.connect()
    if username and password:
        await smtp.login(username, password)
    response = await smtp.send_message(msg)
    await smtp.quit()
    return str(response)


def _handle_retry(task, job: CampaignJob, db, error_msg: str):
    now = datetime.now(timezone.utc)
    job.retry_count += 1
    job.error_chain = (job.error_chain or []) + [
        {"attempt": job.retry_count, "error": error_msg, "timestamp": now.isoformat()}
    ]
    job.error_message = error_msg

    if job.retry_count >= job.max_retries:
        job.status = "dead_letter"
        job.failed_at = now
        db.commit()
        move_to_dead_letter.delay(str(job.id))
    else:
        job.status = "failed"
        job.failed_at = now
        db.commit()
        countdown = 60 * (2 ** job.retry_count)  # Exponential backoff
        task.retry(countdown=countdown, exc=Exception(error_msg))


@celery_app.task(queue="dead_letter")
def move_to_dead_letter(job_id: str):
    with SyncSessionFactory() as db:
        job = db.execute(
            select(CampaignJob).where(CampaignJob.id == uuid.UUID(job_id))
        ).scalar_one_or_none()
        if not job:
            return
        dlj = DeadLetterJob(
            tenant_id=job.tenant_id,
            campaign_job_id=job.id,
            campaign_id=job.campaign_id,
            subscriber_id=job.subscriber_id,
            final_error=job.error_message,
            error_chain=job.error_chain,
        )
        db.add(dlj)

        # Update campaign failed_count
        db.execute(
            update(Campaign).where(Campaign.id == job.campaign_id).values(
                failed_count=Campaign.failed_count + 1
            )
        )
        db.commit()


@celery_app.task(queue="send", bind=True)
def retry_failed_job(self, job_id: str):
    with SyncSessionFactory() as db:
        job = db.execute(
            select(CampaignJob).where(CampaignJob.id == uuid.UUID(job_id))
        ).scalar_one_or_none()
        if not job:
            return
        job.status = "queued"
        job.retry_count = 0
        job.error_chain = []
        job.error_message = None
        job.failed_at = None
        db.commit()
        send_email.delay(job_id)


@celery_app.task(queue="send")
def send_test_email(campaign_id: str, to_emails: list[str], variables: dict):
    with SyncSessionFactory() as db:
        campaign = db.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()
        if not campaign:
            return

        template = db.execute(
            select(EmailTemplate).where(EmailTemplate.id == campaign.template_id)
        ).scalar_one_or_none()
        if not template:
            return

        channel = _select_channel_with_failover(db, campaign.tenant_id)
        if not channel:
            logger.error("No SMTP channel for test send")
            return

        test_vars = {"email": "test@example.com", "name": "Test User", **variables}
        rendered_subject = render_template(template.subject, test_vars)
        rendered_html = render_template(template.html_body, test_vars)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[TEST] {rendered_subject}"
        msg["From"] = f"{campaign.sender_name or 'MailGenius'} <{campaign.sender_email or channel.username}>"
        if template.text_body:
            msg.attach(MIMEText(render_template(template.text_body, test_vars), "plain"))
        msg.attach(MIMEText(rendered_html, "html"))

        password = decrypt_value(channel.password_encrypted) if channel.password_encrypted else None

        import asyncio
        loop = asyncio.new_event_loop()
        for email in to_emails:
            if "To" in msg:
                msg.replace_header("To", email)
            else:
                msg["To"] = email
            try:
                loop.run_until_complete(
                    _async_send(channel.host, channel.port, channel.use_tls, channel.username, password, msg)
                )
            except Exception as e:
                logger.error(f"Test send to {email} failed: {e}")
        loop.close()


@celery_app.task(queue="default")
def health_check_channels():
    with SyncSessionFactory() as db:
        channels = db.execute(
            select(SmtpChannel).where(
                SmtpChannel.is_active.is_(True),
                SmtpChannel.deleted_at.is_(None),
                SmtpChannel.consecutive_failures >= 5,
            )
        ).scalars().all()

        for channel in channels:
            password = decrypt_value(channel.password_encrypted) if channel.password_encrypted else None
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                smtp = aiosmtplib.SMTP(hostname=channel.host, port=channel.port, use_tls=channel.use_tls)
                loop.run_until_complete(smtp.connect())
                if channel.username and password:
                    loop.run_until_complete(smtp.login(channel.username, password))
                loop.run_until_complete(smtp.quit())
                loop.close()
                channel.consecutive_failures = 0
                channel.last_success_at = datetime.now(timezone.utc)
            except Exception:
                pass
        db.commit()
