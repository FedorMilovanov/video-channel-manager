from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import photo_wave_v5 as photo_v5  # noqa: E402


class ReadClient:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def get_current_user(self) -> SimpleNamespace:
        self.events.append("read_current_user")
        return SimpleNamespace(user_id=631487)


class MutationClient:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def _call(self, method: str, *, params: dict[str, object] | None = None) -> object:
        self.events.append(method)
        return None

    def get_current_user(self) -> SimpleNamespace:
        raise AssertionError("mutation client must not fetch the user after photo save")


def test_v5_pins_current_user_before_photo_mutation(monkeypatch: Any, tmp_path: Path) -> None:
    events: list[str] = []
    read_client = ReadClient(events)
    mutation_client = MutationClient(events)

    def fake_prepare_photo_token(**kwargs: Any) -> str:
        events.append("prepare_photo")
        pinned = kwargs["mutation_client"]
        assert pinned.get_current_user().user_id == 631487
        assert events == ["read_current_user", "prepare_photo"]
        return "photo631487_55_private-key"

    monkeypatch.setattr(
        photo_v5.mutations,
        "prepare_photo_token",
        fake_prepare_photo_token,
    )

    token = photo_v5.prepare_photo_token(
        operation={"operation_id": "operation-1"},
        jpeg=b"jpeg",
        read_client=read_client,
        mutation_client=mutation_client,
        journal={"operations": {}},
        journal_path=tmp_path / "journal.json",
    )

    assert token == "photo631487_55_private-key"
    assert events == ["read_current_user", "prepare_photo"]
