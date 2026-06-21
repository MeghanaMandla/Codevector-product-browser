"""
Database engine and session management.

Exposes:
- `engine`: the SQLAlchemy engine bound to DATABASE_URL.
- `SessionLocal`: a session factory used by the `get_db` FastAPI dependency.
- `Base`: the declarative base all ORM models inherit from.
- `get_db`: a FastAPI dependency that yields a request-scoped session and
  guarantees it is closed afterwards, even on error.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

# SQLite (used in tests) needs check_same_thread=False since FastAPI's
# TestClient may use a different thread than the one that created the engine.
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
