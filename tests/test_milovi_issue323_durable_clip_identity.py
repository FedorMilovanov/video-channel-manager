from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalizer


class _Reader:
    def __init__(self, item: dict[str, Any]) -> None:
        self.item = item

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == 456239225
        return dict(self.item)


def _durable_item(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "owner_id": -68859909,
        "id": 456239225,
        "type": "short_video",
        "processing": 1,
        "converting": 0,
        "can_watch": 0,
        "player": "",
        "files": {},
        "title": "",
        "description": "Источник: https://www.youtube.com/shorts/d48QLgOuiTs",
    }
    payload.update(overrides)
    return payload


def _asset() -> Any:
    return SimpleNamespace(
        source_id="d48QLgOuiTs",
        description="promoted internal copy",
    )


def test_durable_verified_clip_ignores_transient_player_and_title_projection() -> None:
    raw = _durable_item()

    observed = finalizer._assert_native_clip(
        _Reader(raw),  # type: ignore[arg-type]
        _asset(),  # type: ignore[arg-type]
        "-68859909_456239225",
        description_mode="legacy_or_promoted",
        durable_verified=True,
    )

    assert observed == raw


def test_durable_verified_clip_still_requires_native_short_video_type() -> None:
    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="lost native short_video type"):
        finalizer._assert_native_clip(
            _Reader(_durable_item(type="video")),  # type: ignore[arg-type]
            _asset(),  # type: ignore[arg-type]
            "-68859909_456239225",
            description_mode="legacy_or_promoted",
            durable_verified=True,
        )


def test_durable_verified_clip_still_requires_exact_owner_and_id() -> None:
    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="identity changed"):
        finalizer._assert_native_clip(
            _Reader(_durable_item(owner_id=-1)),  # type: ignore[arg-type]
            _asset(),  # type: ignore[arg-type]
            "-68859909_456239225",
            description_mode="legacy_or_promoted",
            durable_verified=True,
        )


def test_durable_verified_clip_still_requires_source_or_promoted_binding() -> None:
    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="cannot be bound to source"):
        finalizer._assert_native_clip(
            _Reader(_durable_item(description="unrelated description")),  # type: ignore[arg-type]
            _asset(),  # type: ignore[arg-type]
            "-68859909_456239225",
            description_mode="legacy_or_promoted",
            durable_verified=True,
        )


def test_default_clip_verification_remains_strict_on_transient_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(finalizer, "clip_readiness", lambda _asset: object())
    monkeypatch.setattr(
        finalizer,
        "_native_clip_assessment",
        lambda *args, **kwargs: SimpleNamespace(ready=False, reasons=("processing", "not_playable")),
    )

    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="not a verified native short_video"):
        finalizer._assert_native_clip(
            _Reader(_durable_item()),  # type: ignore[arg-type]
            _asset(),  # type: ignore[arg-type]
            "-68859909_456239225",
            description_mode="legacy_or_promoted",
        )
