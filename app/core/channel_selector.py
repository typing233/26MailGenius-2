import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.models.smtp_channel import SmtpChannel


class ChannelSelector:
    """Selects the best available SMTP channel based on priority, health, and rate limits."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def select_channel(self, redis_client=None) -> SmtpChannel | None:
        stmt = select(SmtpChannel).where(
            SmtpChannel.tenant_id == self.tenant_id,
            SmtpChannel.is_active.is_(True),
            SmtpChannel.deleted_at.is_(None),
            SmtpChannel.consecutive_failures < 5,
        ).order_by(SmtpChannel.priority.asc())

        result = await self.db.execute(stmt)
        channels = result.scalars().all()

        for channel in channels:
            if redis_client:
                now = datetime.now(timezone.utc)
                hourly_key = f"channel:{channel.id}:hourly:{now.strftime('%Y-%m-%dT%H')}"
                daily_key = f"channel:{channel.id}:daily:{now.strftime('%Y-%m-%d')}"
                hourly_count = int(await redis_client.get(hourly_key) or 0)
                daily_count = int(await redis_client.get(daily_key) or 0)
                if hourly_count >= channel.hourly_limit:
                    continue
                if daily_count >= channel.daily_limit:
                    continue
            return channel

        return None

    async def record_success(self, channel: SmtpChannel, redis_client=None) -> None:
        channel.last_success_at = datetime.now(timezone.utc)
        channel.consecutive_failures = 0
        if redis_client:
            now = datetime.now(timezone.utc)
            hourly_key = f"channel:{channel.id}:hourly:{now.strftime('%Y-%m-%dT%H')}"
            daily_key = f"channel:{channel.id}:daily:{now.strftime('%Y-%m-%d')}"
            pipe = redis_client.pipeline()
            pipe.incr(hourly_key)
            pipe.expire(hourly_key, 3600)
            pipe.incr(daily_key)
            pipe.expire(daily_key, 86400)
            await pipe.execute()

    async def record_failure(self, channel: SmtpChannel) -> None:
        channel.last_failure_at = datetime.now(timezone.utc)
        channel.consecutive_failures += 1

    def get_password(self, channel: SmtpChannel) -> str | None:
        if channel.password_encrypted:
            return decrypt_value(channel.password_encrypted)
        return None
