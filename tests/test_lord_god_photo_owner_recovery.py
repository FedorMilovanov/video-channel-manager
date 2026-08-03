from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import mutations  # noqa: E402


class FakeClient:
    def __init__(
        self,
        responses: dict[str, object],
        *,
        current_user_id: int = 631487,
    ) -> None:
        self.responses = responses
        self.current_user_id = current_user_id
        self.calls: list[tuple[str, dict[str, object]]] = []

    def _call(self, method: str, *, params: dict[str, object] | None = None) -> object:
        self.calls.append((method, dict(params or {})))
        return self.responses[method]

    def get_current_user(self) -> SimpleNamespace:
        return SimpleNamespace(user_id=self.current_user_id)


def unknown_entry(*, owner_id: int = 631487) -> dict[str, Any]:
    return {
        "stage": "photo_save_unknown",
        "updated_at": datetime.now().astimezone().isoformat(),
        "upload_payload": {"photo": "temporary", "server": 1, "hash": "hash"},
        "error": f"RuntimeError: Saved wall photo has unexpected owner: {owner_id}",
    }


def wall_photo(*, photo_id: int, owner_id: int = 631487) -> dict[str, Any]:
    return {
        "id": photo_id,
        "owner_id": owner_id,
        "date": int(datetime.now().timestamp()),
        "access_key": "private-key",
        "sizes": [{"width": 1200, "height": 630}],
    }


def test_saved_photo_token_accepts_current_token_user_owner() -> None:
    client = FakeClient(
        {
            "photos.saveWallPhoto": [
                {
                    "id": 55,
                    "owner_id": 631487,
                    "access_key": "private-key",
                }
            ]
        }
    )

    token = mutations.saved_photo_token(
        client,
        {"photo": "temporary", "server": 1, "hash": "hash"},
    )

    assert token == "photo631487_55_private-key"
    assert [method for method, _ in client.calls] == ["photos.saveWallPhoto"]


def test_saved_photo_token_blocks_unrelated_owner() -> None:
    client = FakeClient({"photos.saveWallPhoto": [{"id": 55, "owner_id": 999999}]})

    with pytest.raises(RuntimeError, match="unexpected owner"):
        mutations.saved_photo_token(
            client,
            {"photo": "temporary", "server": 1, "hash": "hash"},
        )


def test_recover_saved_photo_token_uses_one_recent_wall_photo_read_only() -> None:
    client = FakeClient({"photos.get": {"count": 1, "items": [wall_photo(photo_id=77)]}})

    token = mutations.recover_saved_photo_token(
        client,
        unknown_entry(),
        current_user_id=631487,
    )

    assert token == "photo631487_77_private-key"
    assert [method for method, _ in client.calls] == ["photos.get"]
    params = client.calls[0][1]
    assert params["owner_id"] == 631487
    assert params["album_id"] == "wall"
    assert params["rev"] is True
    assert params["photo_sizes"] is True


def test_recovery_blocks_when_recent_photo_is_not_unique() -> None:
    client = FakeClient(
        {
            "photos.get": {
                "count": 2,
                "items": [wall_photo(photo_id=77), wall_photo(photo_id=78)],
            }
        }
    )

    with pytest.raises(RuntimeError, match="exactly one"):
        mutations.recover_saved_photo_token(
            client,
            unknown_entry(),
            current_user_id=631487,
        )


def test_recovery_requires_current_token_user_owner() -> None:
    client = FakeClient({"photos.get": {"count": 0, "items": []}})

    with pytest.raises(RuntimeError, match="current token user"):
        mutations.recover_saved_photo_token(
            client,
            unknown_entry(owner_id=631487),
            current_user_id=42,
        )

    assert client.calls == []
