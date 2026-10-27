from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# pre_ping drops dead pooled connections (db restarted, idle timeout) instead of failing a request
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


class Base(DeclarativeBase):
    pass


def get_db():
    # closing the session rolls back anything not committed
    with SessionLocal() as db:
        yield db
