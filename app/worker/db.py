from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

sync_engine = create_engine(
    settings.database_url_sync,
    pool_size=5,
    max_overflow=10,
)
SyncSessionFactory = sessionmaker(bind=sync_engine, class_=Session)


def get_sync_db() -> Session:
    session = SyncSessionFactory()
    try:
        yield session
    finally:
        session.close()
