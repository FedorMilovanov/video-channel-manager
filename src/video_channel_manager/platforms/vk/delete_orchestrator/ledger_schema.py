from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(UTC).isoformat()


def parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value).astimezone(UTC) if value else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS delete_runs (
 run_id TEXT PRIMARY KEY, decision_set_id TEXT NOT NULL UNIQUE,
 community_id INTEGER NOT NULL, policy_sha256 TEXT NOT NULL,
 policy_path TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 started_at TEXT, completed_at TEXT, paused_reason TEXT,
 lease_owner TEXT, lease_expires_at TEXT,
 successful_epochs INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS delete_epochs (
 epoch_id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT NOT NULL REFERENCES delete_runs(run_id) ON DELETE CASCADE,
 epoch_no INTEGER NOT NULL, status TEXT NOT NULL, batch_size INTEGER NOT NULL,
 started_at TEXT NOT NULL, cooldown_until TEXT, closed_at TEXT,
 UNIQUE(run_id, epoch_no)
);
CREATE TABLE IF NOT EXISTS delete_operations (
 operation_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES delete_runs(run_id) ON DELETE CASCADE,
 epoch_id INTEGER REFERENCES delete_epochs(epoch_id) ON DELETE SET NULL,
 ordinal INTEGER NOT NULL, candidate_id TEXT NOT NULL, primary_id TEXT NOT NULL,
 operation_sha256 TEXT NOT NULL, state TEXT NOT NULL,
 dispatch_count INTEGER NOT NULL DEFAULT 0,
 accepted_at TEXT, first_absent_at TEXT, confirmed_at TEXT,
 next_reconcile_at TEXT, visibility_deadline TEXT,
 last_error_code INTEGER, last_error_class TEXT, last_error_message TEXT,
 updated_at TEXT NOT NULL,
 UNIQUE(run_id, ordinal), UNIQUE(run_id, candidate_id)
);
CREATE TABLE IF NOT EXISTS delete_attempts (
 attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
 operation_id TEXT NOT NULL REFERENCES delete_operations(operation_id) ON DELETE CASCADE,
 attempt_no INTEGER NOT NULL, intent_at TEXT NOT NULL,
 request_sha256 TEXT NOT NULL, response_at TEXT, response_json TEXT,
 api_error_code INTEGER, transport_error TEXT, outcome TEXT NOT NULL,
 UNIQUE(operation_id, attempt_no)
);
CREATE TABLE IF NOT EXISTS delete_observations (
 observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT NOT NULL REFERENCES delete_runs(run_id) ON DELETE CASCADE,
 operation_id TEXT REFERENCES delete_operations(operation_id) ON DELETE CASCADE,
 observed_at TEXT NOT NULL, source TEXT NOT NULL,
 candidate_present INTEGER, primary_present INTEGER,
 owner_count INTEGER, visible_item_count INTEGER, album_ids_json TEXT,
 payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS delete_events (
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT NOT NULL REFERENCES delete_runs(run_id) ON DELETE CASCADE,
 operation_id TEXT REFERENCES delete_operations(operation_id) ON DELETE CASCADE,
 event_type TEXT NOT NULL, event_at TEXT NOT NULL, payload_json TEXT NOT NULL,
 previous_event_sha256 TEXT, event_sha256 TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS delete_operations_due_idx
 ON delete_operations(run_id, state, next_reconcile_at);
CREATE INDEX IF NOT EXISTS delete_observations_operation_idx
 ON delete_observations(operation_id, observed_at);
"""
