import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value, encrypt_value
from app.exceptions import AppException
from app.models.smtp_channel import SmtpChannel


class ChannelService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def create(self, data: dict) -> SmtpChannel:
        password = data.pop("password", None)
        channel = SmtpChannel(tenant_id=self.tenant_id, **data)
        if password:
            channel.password_encrypted = encrypt_value(password)
        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)
        return channel

    async def get(self, channel_id: uuid.UUID) -> SmtpChannel:
        stmt = select(SmtpChannel).where(
            SmtpChannel.id == channel_id,
            SmtpChannel.tenant_id == self.tenant_id,
            SmtpChannel.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        channel = result.scalar_one_or_none()
        if not channel:
            raise AppException(status_code=404, detail="Channel not found")
        return channel

    async def list(self) -> list[SmtpChannel]:
        stmt = select(SmtpChannel).where(
            SmtpChannel.tenant_id == self.tenant_id,
            SmtpChannel.deleted_at.is_(None),
        ).order_by(SmtpChannel.priority.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, channel_id: uuid.UUID, data: dict) -> SmtpChannel:
        channel = await self.get(channel_id)
        password = data.pop("password", None)
        if password:
            channel.password_encrypted = encrypt_value(password)
        for key, value in data.items():
            if value is not None:
                setattr(channel, key, value)
        await self.db.commit()
        await self.db.refresh(channel)
        return channel

    async def delete(self, channel_id: uuid.UUID) -> None:
        channel = await self.get(channel_id)
        channel.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def test_connection(self, channel_id: uuid.UUID, to_email: str) -> dict:
        import aiosmtplib
        channel = await self.get(channel_id)
        password = decrypt_value(channel.password_encrypted) if channel.password_encrypted else None
        try:
            smtp = aiosmtplib.SMTP(
                hostname=channel.host,
                port=channel.port,
                use_tls=channel.use_tls,
            )
            await smtp.connect()
            if channel.username and password:
                await smtp.login(channel.username, password)
            await smtp.sendmail(
                channel.username or "test@example.com",
                [to_email],
                f"Subject: MailGenius SMTP Test\n\nThis is a test email from channel: {channel.name}",
            )
            await smtp.quit()
            channel.last_success_at = datetime.now(timezone.utc)
            channel.consecutive_failures = 0
            await self.db.commit()
            return {"success": True, "message": "Test email sent"}
        except Exception as e:
            channel.last_failure_at = datetime.now(timezone.utc)
            channel.consecutive_failures += 1
            await self.db.commit()
            return {"success": False, "message": str(e)}

    async def get_health(self, channel_id: uuid.UUID) -> dict:
        channel = await self.get(channel_id)
        is_healthy = channel.is_active and channel.consecutive_failures < 5
        return {
            "id": channel.id,
            "name": channel.name,
            "is_active": channel.is_active,
            "is_healthy": is_healthy,
            "consecutive_failures": channel.consecutive_failures,
            "last_success_at": channel.last_success_at,
            "hourly_remaining": channel.hourly_limit,
            "daily_remaining": channel.daily_limit,
        }
