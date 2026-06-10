import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from celery.utils.log import get_task_logger

from app.worker.celery_app import celery_app
from app.worker.db import SyncSessionFactory
from app.models.campaign import Campaign, CampaignJob
from app.models.dead_letter import DeadLetterJob
from app.models.smtp_channel import SmtpChannel
from app.models.subscriber import Subscriber
from app.models.template import EmailTemplate
from app.core.encryption import decrypt_value
from app.core.template_engine import render_template
from app.config import settings
from sqlalchemy import select, update

logger = get_task_logger(__name__)


def _select_channel(db, tenant_id: uuid.UUID) -> SmtpChannel | None:
    channels = db.execute(
        select(SmtpChannel).where(
            SmtpChannel.tenant_id == tenant_id,
            SmtpChannel.is_active.is_(True),
            SmtpChannel.deleted_at.is_(None),
            SmtpChannel.consecutive_failures < 5,
        ).order_by(SmtpChannel.priority.asc())
    ).scalars().all()
    return channels[0] if channels else None


def _inject_tracking(html: str, job_id: str, campaign_id: str, tracking_base_url: str) -> str:
    pixel = f'<img src="{tracking_base_url}/pixel/{job_id}.gif" width="1" height="1" alt="" />'
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

        channel = _select_channel(db, campaign.tenant_id)
        if not channel:
            _handle_retry(self, job, db, "No available SMTP channel")
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

        # Inject tracking pixel
        rendered_html = _inject_tracking(
            rendered_html, str(job.id), str(campaign.id), settings.tracking_base_url
        )

        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = rendered_subject
        msg["From"] = f"{campaign.sender_name or settings.default_sender_name} <{campaign.sender_email or channel.username or settings.default_sender_email}>"
        msg["To"] = subscriber.email
        if campaign.reply_to:
            msg["Reply-To"] = campaign.reply_to
        msg["X-Mailer"] = "MailGenius"
        msg["List-Unsubscribe"] = f"<{settings.public_api_url}/api/v1/subscription/unsubscribe/{subscriber.id}?campaign={campaign.id}>"

        if template.text_body:
            rendered_text = render_template(template.text_body, variables)
            msg.attach(MIMEText(rendered_text, "plain"))
        msg.attach(MIMEText(rendered_html, "html"))

        # Send via SMTP
        password = decrypt_value(channel.password_encrypted) if channel.password_encrypted else None
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            message_id = loop.run_until_complete(
                _async_send(channel.host, channel.port, channel.use_tls, channel.username, password, msg)
            )
            loop.close()

            # Success
            job.status = "sent"
            job.message_id = message_id
            job.sent_at = datetime.now(timezone.utc)
            channel.last_success_at = datetime.now(timezone.utc)
            channel.consecutive_failures = 0
            campaign.sent_count += 1
            db.commit()

        except Exception as e:
            channel.last_failure_at = datetime.now(timezone.utc)
            channel.consecutive_failures += 1
            db.commit()
            _handle_retry(self, job, db, str(e))


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

        channel = _select_channel(db, campaign.tenant_id)
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
            msg.replace_header("To", email) if "To" in msg else msg.__setitem__("To", email)
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
