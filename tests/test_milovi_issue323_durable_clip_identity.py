from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_finalize import (
    MiloviFinalizerBlocked,
    _assert_native_clip,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import build_description

SOURCE_ID = "d48QLgOuiTs"
TITLE = "Durable cake"
LEGACY_DESCRIPTION = build_description(TITLE, SOURCE_ID)
PROMOTED_DESCRIPTION = "promoted internal copy"


class _Writer:
    def __init__(self, item: dict[str, Any]) -> None:
        self.item = item

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        assert owner_id == -68859909
        assert video_id == 456239225
        return dict(self.item)


def _asset() -> Any:
    return SimpleNamespace(source_id=SOURCE_ID, title=TITLE, description=PROMOTED_DESCRIPTION)


def _durable_item(*, description: str = LEGACY_DESCRIPTION) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 456239225,
        "type": "short_video",
        "processing": 1,
        "converting": 0,
        "title": "",
        "description": description,
        "duration": 30,
        "can_watch": 0,
    }


def test_durable_verified_clip_ignores_transient_player_and_title_projection() -> None:
    writer = _Writer(_durable_item())

    raw = _assert_native_clip(
        writer,  # type: ignore[arg-type]
        _asset(),
        "-68859909_456239225",
        description_mode="legacy_or_promoted",
        durable_verified=True,
    )

    assert raw["owner_id"] == -68859909
    assert raw["id"] == 456239225
    assert raw["type"] == "short_video"


def test_durable_verified_clip_accepts_exact_promoted_binding() -> None:
    writer = _Writer(_durable_item(description=PROMOTED_DESCRIPTION))

    raw = _assert_native_clip(
        writer,  # type: ignore[arg-type]
        _asset(),
        "-68859909_456239225",
        description_mode="legacy_or_promoted",
        durable_verified=True,
    )

    assert raw["description"] == PROMOTED_DESCRIPTION


def test_durable_verified_clip_still_requires_exact_legacy_or_promoted_binding() -> None:
    writer = _Writer(
        _durable_item(
            description=f"manual override still containing https://www.youtube.com/shorts/{SOURCE_ID}"
        )
    )

    with pytest.raises(MiloviFinalizerBlocked, match="neither exact reviewed legacy nor exact promoted"):
        _assert_native_clip(
            writer,  # type: ignore[arg-type]
            _asset(),
            "-68859909_456239225",
            description_mode="legacy_or_promoted",
            durable_verified=True,
        )


def test_durable_verified_clip_still_requires_native_type() -> None:
    item = _durable_item()
    item["type"] = "video"
    writer = _Writer(item)

    with pytest.raises(MiloviFinalizerBlocked, match="lost native short_video type"):
        _assert_native_clip(
            writer,  # type: ignore[arg-type]
            _asset(),
            "-68859909_456239225",
            description_mode="legacy_or_promoted",
            durable_verified=True,
        )
