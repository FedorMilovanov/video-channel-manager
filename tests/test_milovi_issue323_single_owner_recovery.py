from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_read_model as read_model


class _ClipReader:
    def __init__(self, video: dict[str, Any]) -> None:
        self.video = video

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == 456239232
        return dict(self.video)


def _protected_projection() -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 456239232,
        "processing": 1,
        "title": "",
        "type": "short_video",
        "can_watch": 0,
    }


def test_preservation_only_check_does_not_require_clip_readiness() -> None:
    raw = _protected_projection()
    writer = _ClipReader(raw)
    asset = SimpleNamespace(source_id="o1WXIMupuws", description="promoted")

    observed = read_model._assert_native_clip(
        writer,  # type: ignore[arg-type]
        asset,  # type: ignore[arg-type]
        "-68859909_456239232",
        description_mode="legacy_or_promoted",
        preservation_only=True,
    )

    assert observed == raw


def test_default_native_clip_check_remains_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _ClipReader(_protected_projection())
    asset = SimpleNamespace(source_id="o1WXIMupuws", description="promoted")
    monkeypatch.setattr(read_model, "clip_readiness", lambda _asset: object())
    monkeypatch.setattr(
        read_model,
        "_native_clip_assessment",
        lambda *args, **kwargs: SimpleNamespace(ready=False, reasons=("not_playable",)),
    )

    with pytest.raises(read_model.MiloviIssue323ReadModelBlocked, match="not a verified native short_video"):
        read_model._assert_native_clip(
            writer,  # type: ignore[arg-type]
            asset,  # type: ignore[arg-type]
            "-68859909_456239232",
            description_mode="legacy_or_promoted",
        )
