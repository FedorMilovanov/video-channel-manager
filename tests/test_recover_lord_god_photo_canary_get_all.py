from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import recover_lord_god_photo_canary as recovery  # noqa: E402


class FakeClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def _call(self, method: str, *, params: dict[str, object] | None = None) -> object:
        self.calls.append((method, dict(params or {})))
        return self.response


def unknown_entry(*, owner_id: int = 631487) -> dict[str, Any]:
    return {
        "stage": "photo_save_unknown",
        "updated_at": datetime.now().astimezone().isoformat(),
        "upload_payload": {"photo": "temporary", "server": 1, "hash": "hash"},
        "error": f"RuntimeError: Saved wall photo has unexpected owner: {owner_id}",
    }


def photo(*, photo_id: int, owner_id: int = 631487) -> dict[str, Any]:
    return {
        "id": photo_id,
        "owner_id": owner_id,
        "date": int(datetime.now().timestamp()),
        "access_key": "private-key",
        "sizes": [{"width": 1200, "height": 630}],
    }


def test_recovery_uses_photos_get_all_with_service_and_hidden_photos() -> None:
    client = FakeClient({"count": 1, "items": [photo(photo_id=77)]})

    token = recovery.recover_saved_photo_token_from_all(
        client,
        unknown_entry(),
        current_user_id=631487,
    )

    assert token == "photo631487_77_private-key"
    assert [method for method, _ in client.calls] == ["photos.getAll"]
    params = client.calls[0][1]
    assert params["owner_id"] == 631487
    assert params["count"] == 200
    assert params["photo_sizes"] is True
    assert params["no_service_albums"] is False
    assert params["need_hidden"] is True
    assert params["skip_hidden"] is False


def test_recovery_blocks_when_get_all_has_no_exact_candidate() -> None:
    client = FakeClient({"count": 1, "items": [photo(photo_id=77, owner_id=42)]})

    with pytest.raises(RuntimeError, match=r"candidates=0; photos_seen=1; same_owner=0"):
        recovery.recover_saved_photo_token_from_all(
            client,
            unknown_entry(),
            current_user_id=631487,
        )

    assert [method for method, _ in client.calls] == ["photos.getAll"]


def test_recovery_blocks_when_get_all_has_multiple_exact_candidates() -> None:
    client = FakeClient(
        {
            "count": 2,
            "items": [photo(photo_id=77), photo(photo_id=78)],
        }
    )

    with pytest.raises(RuntimeError, match=r"candidates=2"):
        recovery.recover_saved_photo_token_from_all(
            client,
            unknown_entry(),
            current_user_id=631487,
        )


def test_recovery_rejects_non_current_owner_before_api_call() -> None:
    client = FakeClient({"count": 0, "items": []})

    with pytest.raises(RuntimeError, match="current token user"):
        recovery.recover_saved_photo_token_from_all(
            client,
            unknown_entry(owner_id=631487),
            current_user_id=42,
        )

    assert client.calls == []
