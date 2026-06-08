import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.tenant import Tenant
from app.models.user import RefreshToken, User, UserRole
from app.schemas.auth import RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register(self, data: RegisterRequest) -> tuple[User, TokenResponse]:
        async with self.session.begin():
            tenant = Tenant(name=data.tenant_name, slug=data.tenant_slug)
            self.session.add(tenant)
            await self.session.flush()

            user = User(
                tenant_id=tenant.id,
                email=data.email,
                password_hash=hash_password(data.password),
                full_name=data.full_name,
            )
            self.session.add(user)
            await self.session.flush()

            role = UserRole(user_id=user.id, tenant_id=tenant.id, role="tenant_admin")
            self.session.add(role)
            await self.session.flush()

        tokens = await self._issue_tokens(user, ["tenant_admin"])
        return user, tokens

    async def login(self, email: str, password: str) -> tuple[User, TokenResponse]:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None), User.is_active.is_(True))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        roles = [r.role for r in user.roles]
        tokens = await self._issue_tokens(user, roles)
        return user, tokens

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        token_hash = hash_token(raw_refresh_token)
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        result = await self.session.execute(stmt)
        stored = result.scalar_one_or_none()

        if stored is None:
            raise ValueError("Invalid or expired refresh token")

        stored.revoked_at = datetime.now(timezone.utc)

        user_stmt = select(User).where(User.id == stored.user_id)
        user_result = await self.session.execute(user_stmt)
        user = user_result.scalar_one()
        roles = [r.role for r in user.roles]

        tokens = await self._issue_tokens(user, roles)
        await self.session.commit()
        return tokens

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_token(raw_refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
        result = await self.session.execute(stmt)
        stored = result.scalar_one_or_none()
        if stored:
            stored.revoked_at = datetime.now(timezone.utc)
            await self.session.commit()

    async def _issue_tokens(self, user: User, roles: list[str]) -> TokenResponse:
        access_token = create_access_token(user.id, user.tenant_id, roles)
        raw_refresh, refresh_hash = generate_refresh_token()

        from app.config import settings

        refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
        self.session.add(refresh_record)
        await self.session.commit()

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh)
