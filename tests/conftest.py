import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.mailing_list import ListSubscriber, MailingList
from app.models.subscriber import Subscriber
from app.models.tenant import Tenant
from app.models.user import User, UserRole

TEST_DATABASE_URL = settings.database_url + "_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def tenant_a(db_session: AsyncSession):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant A", slug=f"tenant-a-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def tenant_b(db_session: AsyncSession):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant B", slug=f"tenant-b-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession, tenant_a: Tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="admin@tenanta.com",
        password_hash=hash_password("password123"),
        full_name="Admin A",
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRole(id=uuid.uuid4(), user_id=user.id, tenant_id=tenant_a.id, role="tenant_admin")
    db_session.add(role)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession, tenant_b: Tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        email="admin@tenantb.com",
        password_hash=hash_password("password123"),
        full_name="Admin B",
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRole(id=uuid.uuid4(), user_id=user.id, tenant_id=tenant_b.id, role="tenant_admin")
    db_session.add(role)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def token_a(user_a: User):
    return create_access_token(user_a.id, user_a.tenant_id, ["tenant_admin"])


@pytest_asyncio.fixture
async def token_b(user_b: User):
    return create_access_token(user_b.id, user_b.tenant_id, ["tenant_admin"])


@pytest_asyncio.fixture
async def member_user(db_session: AsyncSession, tenant_a: Tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="member@tenanta.com",
        password_hash=hash_password("password123"),
        full_name="Member A",
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRole(id=uuid.uuid4(), user_id=user.id, tenant_id=tenant_a.id, role="member")
    db_session.add(role)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def member_token(member_user: User):
    return create_access_token(member_user.id, member_user.tenant_id, ["member"])


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
