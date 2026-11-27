from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from video_channel_manager.platforms.youtube.models import OAuthToken, YouTubeAccount

_ACCOUNT_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class AccountNotFoundError(KeyError):
    pass


class TokenStore:
    """Stores OAuth tokens separately from a small non-secret account registry."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.token_dir = data_dir / "secrets" / "youtube"
        self.registry_path = data_dir / "youtube" / "accounts.json"

    @staticmethod
    def validate_alias(alias: str) -> str:
        alias = alias.strip()
        if not _ACCOUNT_ALIAS_RE.fullmatch(alias):
            raise ValueError("account alias must contain only letters, digits, dots, underscores, or hyphens")
        return alias

    def ensure_directories(self) -> None:
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def token_path(self, alias: str) -> Path:
        alias = self.validate_alias(alias)
        return self.token_dir / f"{alias}.json"

    def token_exists(self, alias: str) -> bool:
        return self.token_path(alias).is_file()

    def save_token(self, alias: str, token: OAuthToken) -> Path:
        self.ensure_directories()
        path = self.token_path(alias)
        self._write_json_atomic(path, token.model_dump(mode="json"), secret=True)
        return path

    def load_token(self, alias: str) -> OAuthToken:
        path = self.token_path(alias)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AccountNotFoundError(f"YouTube account token not found: {alias}") from exc
        return OAuthToken.model_validate(payload)

    def delete_token(self, alias: str) -> None:
        path = self.token_path(alias)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def list_accounts(self) -> list[YouTubeAccount]:
        if not self.registry_path.exists():
            return []
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Invalid YouTube account registry: {self.registry_path}")
        return sorted((YouTubeAccount.model_validate(item) for item in payload), key=lambda item: item.alias)

    def get_account(self, alias: str) -> YouTubeAccount:
        alias = self.validate_alias(alias)
        for account in self.list_accounts():
            if account.alias == alias:
                return account
        raise AccountNotFoundError(f"YouTube account is not registered: {alias}")

    def save_account(self, account: YouTubeAccount) -> None:
        self.ensure_directories()
        account.alias = self.validate_alias(account.alias)
        accounts = {item.alias: item for item in self.list_accounts()}
        previous = accounts.get(account.alias)
        if previous is not None:
            account.created_at = previous.created_at
        account.updated_at = datetime.now(UTC)
        accounts[account.alias] = account
        payload = [item.model_dump(mode="json") for item in sorted(accounts.values(), key=lambda item: item.alias)]
        self._write_json_atomic(self.registry_path, payload, secret=False)

    @staticmethod
    def _write_json_atomic(path: Path, payload: object, *, secret: bool) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if secret:
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
        temp_path.replace(path)
        if secret:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass


class YouTubeQuotaBlocked(RuntimeError):
    """The local quota gate prevented dispatch, or could not persist a known rejection."""


def quota_exhaustion_reason(response: httpx.Response) -> str | None:
    """Do not latch OAuth failures, permissions, or temporary rate limits."""
    if response.status_code != 403:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
        return None
    error = payload["error"]
    errors = error.get("errors")
    reasons = (
        {str(item.get("reason")) for item in errors if isinstance(item, dict) and item.get("reason")}
        if isinstance(errors, list)
        else set()
    )
    for reason in ("quotaExceeded", "dailyLimitExceeded"):
        if reason in reasons:
            return reason
    # Older responses may omit the structured reason. Accept only Google's
    # specific exhaustion wording, never a generic mention of "quota".
    if not reasons:
        message = str(error.get("message") or "").casefold()
        if "you have exceeded your" in message and "quota" in message:
            return "quotaExceeded"
    return None


# Cost table: https://developers.google.com/youtube/data/determine_quota_cost
# The documented search and video-insert buckets are separate from shared units.
# For resumable media/status HTTP attempts, conservatively charge one upload
# allowance per dispatch; that estimate is NOT a Google usage receipt.
_QUOTA_BUCKETS = ("shared", "search", "uploads")
# Exact project, approved use case, six-month grant from 24 November 2026.
# End conservatively at the start of the last Pacific date pending renewal.
# Local ceilings reserve 10% for external consumers/reconciliation, not a
# statement about Google's actual remaining balance.
_APPROVED_PROJECT_NUMBER = "1067074369047"
_APPROVED_GRANT_START = "2026-11-24"
_APPROVED_GRANT_END_EXCLUSIVE = "2027-05-24"
_APPROVED_LOCAL_CEILINGS = {"shared": 99_000, "search": 90, "uploads": 90}
_READ_ONE = {"channels", "videos", "playlists", "playlistItems", "commentThreads", "comments"}
_QUOTA_COSTS = {
    ("GET", "videos.read-exact"): ("shared", 1),
    ("GET", "playlistItems.list"): ("shared", 1),
    ("GET", "search"): ("search", 1),
    ("GET", "search.list"): ("search", 1),
    ("GET", "captions"): ("shared", 50),
    ("GET", "captions.list"): ("shared", 50),
    ("GET", "captions.download"): ("shared", 200),
    ("POST", "captions"): ("shared", 400),
    ("POST", "captions.insert"): ("shared", 400),
    ("PUT", "captions"): ("shared", 450),
    ("PUT", "captions.update"): ("shared", 450),
    ("POST", "commentThreads"): ("shared", 50),
    ("POST", "comments"): ("shared", 50),
    ("PUT", "comments"): ("shared", 50),
    ("PUT", "videos"): ("shared", 50),
    ("PUT", "playlists"): ("shared", 50),
    ("PUT", "playlists.update"): ("shared", 50),
    ("PUT", "videos.update.metadata-status"): ("shared", 50),
    ("PUT", "videos.update.visibility"): ("shared", 50),
    ("POST", "playlistItems.insert"): ("shared", 50),
    ("POST", "playlistItems"): ("shared", 50),
    ("POST", "thumbnails.set"): ("shared", 50),
    ("POST", "videos.insert.resumable-session"): ("uploads", 1),
    ("PUT", "videos.insert.resumable-media"): ("uploads", 1),
    ("PUT", "videos.insert.resumable-status"): ("uploads", 1),
}


def quota_cost(method: str, resource: str) -> tuple[str, int] | None:
    method = method.upper()
    if method == "GET" and (resource in _READ_ONE or resource.removesuffix(".list") in _READ_ONE):
        return "shared", 1
    return _QUOTA_COSTS.get((method, resource))


class ProjectQuotaGuard:
    """Durable same-host, shared-data-root quota stop and dispatch counter.

    Each admitted attempt is recorded before HTTP, including retries and
    failures. The provider's actual balance is NOT inferred from these local
    counters. When explicitly configured, daily bucket allowances and bounded
    operation reservations enforce local admission ceilings. A rejection with
    an ambiguous quota bucket conservatively stops
    all new admissions for this project for the current Pacific calendar day.
    Requests already admitted or in flight cannot be recalled.
    """

    def __init__(
        self,
        path: Path,
        account: str,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        project_number: str | None = None,
    ) -> None:
        self.path = path
        self.account = account
        self.project_number = project_number
        self.now = now
        self._active: ContextVar[tuple[str, str, str] | None] = ContextVar("youtube_quota_reservation", default=None)

    @classmethod
    def for_client(cls, data_dir: Path | None, client_id: str, account: str) -> "ProjectQuotaGuard | None":
        # Google Desktop OAuth IDs embed the Cloud project number before the
        # hyphen. Distinct channel aliases and clients with that number share
        # the same database. Synthetic fixture IDs do not identify a project.
        match = re.fullmatch(r"(\d+)-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", client_id)
        if match is None:
            return None
        if data_dir is None:
            raise YouTubeQuotaBlocked("YouTube quota guard requires the canonical shared data directory")
        number = match.group(1)
        return cls(data_dir.resolve() / "youtube" / "quota" / f"{number}.sqlite3", account, project_number=number)

    def _day(self) -> str:
        return self.now().astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS stops (day TEXT PRIMARY KEY, reason TEXT NOT NULL)")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS attempts (day TEXT, account TEXT, method TEXT, "
                    "resource TEXT, count INTEGER NOT NULL, PRIMARY KEY(day, account, method, resource))"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS quota_usage (day TEXT, bucket TEXT, account TEXT, "
                    "units INTEGER NOT NULL, PRIMARY KEY(day, bucket, account))"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS quota_limits (day TEXT, bucket TEXT, ceiling INTEGER NOT NULL, "
                    "evidence TEXT NOT NULL, PRIMARY KEY(day, bucket))"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS quota_reservations (id TEXT PRIMARY KEY, day TEXT NOT NULL, "
                    "bucket TEXT NOT NULL, account TEXT NOT NULL, remaining INTEGER NOT NULL)"
                )
                yield db
        except (OSError, sqlite3.Error) as exc:
            raise YouTubeQuotaBlocked("YouTube quota ledger unavailable; stop and reconcile") from exc

    @staticmethod
    def _totals(db: sqlite3.Connection, day: str, bucket: str) -> tuple[int, int]:
        spent = db.execute(
            "SELECT COALESCE(SUM(units), 0) FROM quota_usage WHERE day = ? AND bucket = ?", (day, bucket)
        ).fetchone()[0]
        held = db.execute(
            "SELECT COALESCE(SUM(remaining), 0) FROM quota_reservations WHERE day = ? AND bucket = ?",
            (day, bucket),
        ).fetchone()[0]
        return int(spent), int(held)

    def _grant_ceiling(self, day: str, bucket: str) -> int | None:
        if (
            self.project_number == _APPROVED_PROJECT_NUMBER
            and _APPROVED_GRANT_START <= day < _APPROVED_GRANT_END_EXCLUSIVE
        ):
            return _APPROVED_LOCAL_CEILINGS.get(bucket)
        return None

    def _configured(self, db: sqlite3.Connection, day: str) -> bool:
        return (
            self._grant_ceiling(day, "shared") is not None
            or db.execute("SELECT 1 FROM quota_limits LIMIT 1").fetchone() is not None
        )

    def _effective_ceiling(self, db: sqlite3.Connection, day: str, bucket: str) -> int | None:
        manual = db.execute("SELECT ceiling FROM quota_limits WHERE day = ? AND bucket = ?", (day, bucket)).fetchone()
        grant = self._grant_ceiling(day, bucket)
        if manual is None:
            return grant
        return int(manual[0]) if grant is None else min(int(manual[0]), grant)

    def _check_day(self, db: sqlite3.Connection, day: str) -> None:
        stop = db.execute("SELECT reason FROM stops WHERE day = ?", (day,)).fetchone()
        if stop is not None:
            raise YouTubeQuotaBlocked(f"YouTube project quota blocked for Pacific day {day}: {stop[0]}; no dispatch")
        if (
            self._grant_ceiling(day, "shared") is None
            and self._configured(db, day)
            and db.execute("SELECT 1 FROM quota_limits WHERE day = ?", (day,)).fetchone() is None
        ):
            raise YouTubeQuotaBlocked(f"YouTube quota allowance for Pacific day {day} is missing; no dispatch")

    def _check_capacity(self, db: sqlite3.Connection, day: str, bucket: str, units: int) -> None:
        limit = self._effective_ceiling(db, day, bucket)
        if limit is not None:
            spent, held = self._totals(db, day, bucket)
            if spent + held + units > limit:
                raise YouTubeQuotaBlocked(f"YouTube local {bucket} quota allowance exhausted; no dispatch")

    def configure_day(self, *, day: str, allowances: dict[str, int], evidence: str) -> None:
        """Record a one-time additional local allowance from a reviewed Console snapshot.

        The operator must first pause competing writers and account for other
        clients. This does not query or set Google's actual quota. No silent refill.
        """
        if (
            set(allowances) != set(_QUOTA_BUCKETS)
            or any(type(value) is not int or not 0 <= value <= 1_000_000_000 for value in allowances.values())
            or not evidence.strip()
        ):
            raise ValueError("Three non-negative bucket allowances and non-secret evidence are required.")
        with self._transaction() as db:
            if day != self._day():
                raise ValueError("Allowance must be for the current Pacific calendar day.")
            if db.execute("SELECT 1 FROM quota_limits WHERE day = ?", (day,)).fetchone() is not None:
                raise ValueError("Today's quota allowance is already configured; no refill.")
            if db.execute("SELECT 1 FROM quota_reservations WHERE day = ?", (day,)).fetchone() is not None:
                raise ValueError("Active reservations exist; pause and reconcile operators first.")
            for bucket, units in allowances.items():
                spent, _ = self._totals(db, day, bucket)
                db.execute("INSERT INTO quota_limits VALUES (?, ?, ?, ?)", (day, bucket, spent + units, evidence))

    def require_reviewed_allowance(self, units: int, *, bucket: str = "shared") -> None:
        """Require a reviewed manual ceiling or an active, project-bound approved grant."""
        if type(units) is not int or units <= 0 or bucket not in _QUOTA_BUCKETS:
            raise ValueError("A positive allowance requirement and known quota bucket are required.")
        with self._transaction() as db:
            day = self._day()
            self._check_day(db, day)
            self._require_reviewed_evidence(db, day, bucket)
            self._check_capacity(db, day, bucket, units)

    def _require_reviewed_evidence(self, db: sqlite3.Connection, day: str, bucket: str) -> None:
        if self._grant_ceiling(day, bucket) is not None:
            return
        evidence = db.execute(
            "SELECT evidence FROM quota_limits WHERE day = ? AND bucket = ?", (day, bucket)
        ).fetchone()
        if evidence is None or not str(evidence[0]).strip():
            raise YouTubeQuotaBlocked("Reviewed current-day YouTube quota allowance is required; no dispatch")

    def budget_status(self) -> dict[str, object]:
        """Local estimates only; no provider request and no inferred grant."""
        with self._transaction() as db:
            day = self._day()
            buckets: dict[str, dict[str, int | None]] = {}
            for bucket in _QUOTA_BUCKETS:
                spent, held = self._totals(db, day, bucket)
                limit = self._effective_ceiling(db, day, bucket)
                buckets[bucket] = {
                    "estimated_units": spent,
                    "reserved_units": held,
                    "local_remaining": None if limit is None else limit - spent - held,
                }
            stop = db.execute("SELECT reason FROM stops WHERE day = ?", (day,)).fetchone()
            unpriced, _ = self._totals(db, day, "unpriced")
            return {
                "pacific_day": day,
                "quota_policy_enabled": self._configured(db, day),
                "approved_grant_active": self._grant_ceiling(day, "shared") is not None,
                "provider_stop": None if stop is None else str(stop[0]),
                "buckets": buckets,
                "unpriced_attempts": unpriced,
                "google_remaining": None,
            }

    @contextmanager
    def reserve(self, units: int, *, bucket: str = "shared", require_reviewed: bool = False) -> Iterator[None]:
        """Hold a bounded operation's write and verification allowance atomically."""
        if type(units) is not int or units <= 0 or bucket not in _QUOTA_BUCKETS:
            raise ValueError("A positive reservation and known quota bucket are required.")
        active = self._active.get()
        with self._transaction() as db:
            day = self._day()
            self._check_day(db, day)
            if require_reviewed:
                self._require_reviewed_evidence(db, day, bucket)
            if active is not None:
                reservation_id, reserved_day, reserved_bucket = active
                remaining = db.execute(
                    "SELECT remaining FROM quota_reservations WHERE id = ?", (reservation_id,)
                ).fetchone()
                if reserved_day != day or reserved_bucket != bucket or remaining is None or int(remaining[0]) < units:
                    raise YouTubeQuotaBlocked("Nested YouTube quota reservation cannot be satisfied; no dispatch")
            else:
                self._check_capacity(db, day, bucket, units)
                reservation_id = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO quota_reservations VALUES (?, ?, ?, ?, ?)",
                    (reservation_id, day, bucket, self.account, units),
                )
        if active is not None:
            yield
            return
        token = self._active.set((reservation_id, day, bucket))
        try:
            yield
        except BaseException as error:
            try:
                self._release(reservation_id)
            except YouTubeQuotaBlocked as cleanup:
                error.add_note(str(cleanup))
            raise
        else:
            self._release(reservation_id)
        finally:
            self._active.reset(token)

    def _release(self, reservation_id: str) -> None:
        with self._transaction() as db:
            db.execute("DELETE FROM quota_reservations WHERE id = ?", (reservation_id,))

    def __call__(
        self,
        request: Callable[[], httpx.Response],
        method: str,
        resource: str,
    ) -> httpx.Response:
        cost = quota_cost(method, resource)
        with self._transaction() as db:
            day = self._day()
            self._check_day(db, day)
            active = self._active.get()
            if cost is None and (active is not None or self._configured(db, day)):
                raise YouTubeQuotaBlocked("Unpriced YouTube API method under quota policy; no dispatch")
            bucket, units = cost if cost is not None else ("unpriced", 1)
            if active is not None:
                reservation_id, reserved_day, reserved_bucket = active
                if reserved_day != day or reserved_bucket != bucket:
                    raise YouTubeQuotaBlocked("YouTube quota reservation day or bucket changed; no dispatch")
                result = db.execute(
                    "UPDATE quota_reservations SET remaining = remaining - ? WHERE id = ? AND remaining >= ?",
                    (units, reservation_id, units),
                )
                if result.rowcount != 1:
                    raise YouTubeQuotaBlocked("YouTube operation quota reservation exhausted; no dispatch")
            else:
                self._check_capacity(db, day, bucket, units)
            db.execute(
                "INSERT INTO quota_usage VALUES (?, ?, ?, ?) "
                "ON CONFLICT(day, bucket, account) DO UPDATE SET units = units + excluded.units",
                (day, bucket, self.account, units),
            )
            db.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, ?, 1) "
                "ON CONFLICT(day, account, method, resource) DO UPDATE SET count = count + 1",
                (day, self.account, method.upper(), resource),
            )
        response = request()
        reason = quota_exhaustion_reason(response)
        if reason is not None:
            with self._transaction() as db:
                # A delayed response at midnight is conservatively latched
                # for the day on which the refusal was observed.
                db.execute("INSERT OR REPLACE INTO stops VALUES (?, ?)", (self._day(), reason))
        return response


@contextmanager
def reserve_shared_quota(guard: ProjectQuotaGuard | None, units: int, error_type: type[RuntimeError]) -> Iterator[None]:
    """Keep quota errors in the existing adapter's public error hierarchy."""
    if guard is None:
        yield
        return
    try:
        with guard.reserve(units):
            yield
    except YouTubeQuotaBlocked as exc:
        raise error_type(str(exc)) from exc
