from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
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


class ProjectQuotaGuard:
    """Durable same-host, shared-data-root quota stop and dispatch counter.

    Each admitted attempt is recorded before HTTP, including retries and
    failures. The provider's actual balance is NOT inferred from these local
    counters. A rejection with an ambiguous quota bucket conservatively stops
    all new admissions for this project for the current Pacific calendar day.
    Requests already admitted or in flight cannot be recalled.
    """

    def __init__(
        self,
        path: Path,
        account: str,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = path
        self.account = account
        self.now = now

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
        return cls(data_dir.resolve() / "youtube" / "quota" / f"{match.group(1)}.sqlite3", account)

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
                yield db
        except (OSError, sqlite3.Error) as exc:
            raise YouTubeQuotaBlocked("YouTube quota ledger unavailable; stop and reconcile") from exc

    def __call__(
        self,
        request: Callable[[], httpx.Response],
        method: str,
        resource: str,
    ) -> httpx.Response:
        day = self._day()
        with self._transaction() as db:
            stop = db.execute("SELECT reason FROM stops WHERE day = ?", (day,)).fetchone()
            if stop is not None:
                raise YouTubeQuotaBlocked(
                    f"YouTube project quota blocked for Pacific day {day}: {stop[0]}; no dispatch"
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
