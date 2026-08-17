from __future__ import annotations

import hashlib

from video_channel_manager.platforms.vk.milovi_issue323_read_model import (
    _copy_state,
    _legacy_wall_message,
    _promote_asset,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import SourceAsset

SOURCE_ID = "d48QLgOuiTs"
LATE_PREPARED_WALL = (
    "Романтичный Торт с Бантом от #Milovi_Cake #ТортыНаЗаказ #Cake #Shorts #CakeDecorating\n\n"
    "🌐 https://milovicake.ru/\n"
    "Источник: https://www.youtube.com/shorts/d48QLgOuiTs"
)
HISTORICAL_WALL = (
    "Романтичный Торт с Бантом от #Milovi_Cake #ТортыНаЗаказСПб #Cake #Shorts #CakeDecorating\n\n"
    "🌐 https://milovicake.ru/"
)


def _asset(*, wall_message: str = LATE_PREPARED_WALL, legacy_wall_message: str | None = None) -> SourceAsset:
    return SourceAsset(
        source_id=SOURCE_ID,
        source_url=f"https://www.youtube.com/shorts/{SOURCE_ID}",
        title="Романтичный Торт с Бантом от #Milovi_Cake #ТортыНаЗаказ #Cake #Shorts #CakeDecorating",
        duration_seconds=30,
        media_path="Z:/protected/d48QLgOuiTs.mp4",
        media_sha256="0" * 64,
        width=1080,
        height=1920,
        description=f"Источник YouTube Shorts: https://www.youtube.com/shorts/{SOURCE_ID}",
        wall_message=wall_message,
        legacy_wall_message=legacy_wall_message,
    )


def test_exact_live_canary_copy_restores_historical_legacy_before_state() -> None:
    asset = _asset()

    assert hashlib.sha256(LATE_PREPARED_WALL.encode("utf-8")).hexdigest() == (
        "3a8ed916bd6e86ff924ed0ae6315ccbfad05fc972e2604ba98ec1171a0119fc0"
    )
    assert hashlib.sha256(HISTORICAL_WALL.encode("utf-8")).hexdigest() == (
        "cddb2b01370b146708556779244c493f8e97f4a3da873cd914e121c97031e4b0"
    )
    assert asset.legacy_wall_message == HISTORICAL_WALL

    promoted = _promote_asset(asset)
    assert _legacy_wall_message(promoted) == HISTORICAL_WALL
    assert (
        _copy_state(
            current=HISTORICAL_WALL,
            legacy=_legacy_wall_message(promoted),
            promoted=promoted.wall_message.strip(),
            source_id=SOURCE_ID,
            field="Wall message",
        )
        == "legacy"
    )


def test_canary_near_miss_prepared_copy_is_not_rewritten() -> None:
    near_miss = LATE_PREPARED_WALL.replace("#ТортыНаЗаказ ", "#ТортыНаЗаказX ", 1)
    asset = _asset(wall_message=near_miss)

    assert asset.legacy_wall_message is None


def test_canary_explicit_different_legacy_copy_is_not_overwritten() -> None:
    explicit = LATE_PREPARED_WALL + "\noperator-reviewed-different-state"
    asset = _asset(legacy_wall_message=explicit)

    assert asset.legacy_wall_message == explicit
