from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

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
