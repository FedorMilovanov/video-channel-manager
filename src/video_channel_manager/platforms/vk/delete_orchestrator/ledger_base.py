from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.delete_orchestrator.ledger_schema import SCHEMA, iso


class LedgerBase:
    path: Path

    @contextmanager
    def connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        for pragma in (
            "PRAGMA foreign_keys = ON",
            "PRAGMA journal_mode = WAL",
            "PRAGMA synchronous = FULL",
            "PRAGMA busy_timeout = 5000",
        ):
            connection.execute(pragma)
        connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_schema(self) -> None:
        with sqlite3.connect(self.path, timeout=30.0) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(SCHEMA)

    def _event(
        self,
        connection: sqlite3.Connection,
        *,
        run_id: str,
        operation_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        previous = connection.execute(
            "SELECT event_sha256 FROM delete_events WHERE run_id=? ORDER BY event_id DESC LIMIT 1", (run_id,)
        ).fetchone()
        previous_hash = str(previous["event_sha256"]) if previous else None
        event_at = iso()
        event_hash = canonical_sha256(
            {
                "run_id": run_id,
                "operation_id": operation_id,
                "event_type": event_type,
                "event_at": event_at,
                "payload": payload,
                "previous_event_sha256": previous_hash,
            }
        )
        connection.execute(
            """INSERT INTO delete_events
            (run_id,operation_id,event_type,event_at,payload_json,previous_event_sha256,event_sha256)
            VALUES (?,?,?,?,?,?,?)""",
            (
                run_id,
                operation_id,
                event_type,
                event_at,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                previous_hash,
                event_hash,
            ),
        )

    @staticmethod
    def new_lease_owner() -> str:
        return uuid.uuid4().hex
