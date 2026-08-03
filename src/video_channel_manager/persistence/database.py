from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from video_channel_manager.persistence.models import Base

_SQLITE_BUSY_TIMEOUT_MILLISECONDS = 5_000


def _configure_sqlite_connection(
    dbapi_connection: Any,
    _connection_record: Any,
    *,
    enable_wal: bool,
) -> None:
    """Apply reliability pragmas to every SQLite DB-API connection."""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MILLISECONDS}")
        if enable_wal:
            cursor.execute("PRAGMA journal_mode=WAL")
            mode_row = cursor.fetchone()
            mode = str(mode_row[0]).lower() if mode_row else ""
            if mode != "wal":
                raise RuntimeError(f"SQLite refused WAL mode; active journal_mode={mode or 'unknown'}")
    finally:
        cursor.close()


class Database:
    def __init__(self, database_url: str) -> None:
        is_sqlite = database_url.startswith("sqlite")
        is_memory_sqlite = is_sqlite and (":memory:" in database_url or database_url.rstrip("/") == "sqlite:")
        connect_args: dict[str, object] = {}
        if is_sqlite:
            connect_args = {
                "check_same_thread": False,
                "timeout": _SQLITE_BUSY_TIMEOUT_MILLISECONDS / 1_000,
            }

        self.engine: Engine = create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        if is_sqlite:
            enable_wal = not is_memory_sqlite

            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
                _configure_sqlite_connection(
                    dbapi_connection,
                    connection_record,
                    enable_wal=enable_wal,
                )

        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)

    def create_schema(self) -> None:
        """Development/bootstrap helper. Production changes use Alembic migrations."""

        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        """Release pooled database connections deterministically."""

        self.engine.dispose()

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
