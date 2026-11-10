"""Motor y sesiones de base de datos."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base


def _ensure_sqlite_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.database and url.database != ":memory:":
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        _ensure_sqlite_directory(database_url)
        options: dict[str, object] = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in database_url or database_url.rstrip("/") == "sqlite:":
            options["poolclass"] = StaticPool
        return create_engine(database_url, **options)
    return create_engine(database_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Crea las tablas. Las migraciones con Alembic llegan en F5."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
