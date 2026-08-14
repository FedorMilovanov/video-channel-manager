from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.platforms.vk import milovi_issue323_finalize as finalize
from video_channel_manager.platforms.vk.milovi_issue323_finalize import (
    ANOMALY_POST_ID,
    MiloviFinalizerBlocked,
)
from video_channel_manager.platforms.vk.milovi_promotion import (
    MILOVI_ABOUT_URL,
    MILOVI_CERTIFICATES_URL,
    MILOVI_CLIPS_URL,
    MILOVI_GALLERY_URL,
    MILOVI_MARKET_URL,
    MILOVI_MERINGUE_URL,
    MILOVI_SITE_URL,
    assert_internal_promotion_copy,
    public_clip_description,
    public_urls,
    public_wall_message,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import SourceAsset


def _legacy_anomaly_asset() -> SourceAsset:
    source_id = "o1WXIMupuws"
    title = "Меренговый рулет с малиной"
    source_url = f"https://www.youtube.com/shorts/{source_id}"
    return SourceAsset(
        source_id=source_id,
        source_url=source_url,
        title=title,
        duration_seconds=27,
        media_path=str(Path("clip.mp4")),
        media_sha256="a" * 64,
        width=1080,
        height=1920,
        description=f"{title}\n\nИсточник YouTube Shorts: {source_url}",
        wall_message=f"{title}\n\nИсточник: {source_url}",
    )


class _ReadOnlyPhase2Writer:
    def __init__(self, post: dict[str, object] | None) -> None:
        self.post = post
        self.delete_calls = 0

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, object] | None:
        assert community_id == 68859909
        assert post_id == ANOMALY_POST_ID
        return dict(self.post) if self.post is not None else None

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, object] | None:
        assert owner_id == -68859909
        assert video_id == 456239232
        return {
            "owner_id": owner_id,
            "id": video_id,
            "type": "short_video",
            "processing": 1,
            "title": "",
            "can_watch": 0,
        }

    def _call(self, method: str, *, params: dict[str, Any]) -> object:
        self.delete_calls += 1
        raise AssertionError(f"Phase 2 must never dispatch {method}: {params}")


@pytest.mark.parametrize(
    "title",
    [
        "Меренговый рулет с малиной",
        "Бенто-торт для подруги",
        "Детский торт с персонажем",
        "Свадебный торт",
        "Торт на день рождения",
        "Авторский торт Milovi Cake",
    ],
)
def test_public_copy_is_internal_milovi_promotion(title: str) -> None:
    for text in (public_clip_description(title), public_wall_message(title)):
        assert "youtube" not in text.casefold()
        assert "youtu.be" not in text.casefold()
        urls = public_urls(text)
        for url in (MILOVI_SITE_URL, MILOVI_GALLERY_URL, MILOVI_MARKET_URL, MILOVI_CLIPS_URL):
            assert urls.count(url) == 1
        assert urls.count(MILOVI_ABOUT_URL) == 1
        assert urls.count(MILOVI_CERTIFICATES_URL) == 1
        assert_internal_promotion_copy(text, title=title)


def test_meringue_copy_routes_to_exact_product_page() -> None:
    title = "Меренговый рулет с малиной"
    description = public_clip_description(title)
    assert public_urls(description).count(MILOVI_MERINGUE_URL) == 1
    assert "воздушная меренга" in description.casefold()
    assert "крем-чиз" in description.casefold()
    assert "малина" in description.casefold()


def test_trust_copy_names_viktoria_and_certificates() -> None:
    text = public_wall_message("Авторский торт")
    assert "Виктории Миловановой" in text
    assert "частная кондитерская" in text
    assert "5 лет опыта" in text
    assert "акварельная роспись" in text
    assert "шоколадная флористика" in text
    assert "Сертификаты и обучение" in text


def test_public_copy_guard_rejects_youtube() -> None:
    text = public_clip_description("Авторский торт") + "\nhttps://www.youtube.com/shorts/example"
    with pytest.raises(ValueError, match="YouTube"):
        assert_internal_promotion_copy(text, title="Авторский торт")


def test_issue323_phase2_adopts_exact_deleted_tombstone_without_delete(tmp_path: Path) -> None:
    writer = _ReadOnlyPhase2Writer({"owner_id": -68859909, "id": ANOMALY_POST_ID, "is_deleted": True})
    state: dict[str, Any] = {"cleanup_475": {"status": "verified_absent"}}
    journal_path = tmp_path / "finalizer.json"

    finalize._cleanup_anomaly_475(
        writer=writer,  # type: ignore[arg-type]
        promoted_asset=_legacy_anomaly_asset(),
        finalizer=state,
        finalizer_path=journal_path,
    )

    cleanup = state["cleanup_475"]
    assert writer.delete_calls == 0
    assert cleanup["status"] == "verified_absent"
    assert cleanup["phase2_delete_authority"] is False
    assert cleanup["phase2_absence_evidence"] == "wall.getById:is_deleted_true"
    assert cleanup["protected_clip_remote_id"] == "-68859909_456239232"
    assert cleanup["protected_clip_preserved"] is True
    persisted = json.loads(journal_path.read_text(encoding="utf-8"))
    assert persisted["cleanup_475"] == cleanup


def test_issue323_phase2_rejects_live_475_without_delete_dispatch(tmp_path: Path) -> None:
    writer = _ReadOnlyPhase2Writer({"owner_id": -68859909, "id": ANOMALY_POST_ID, "is_deleted": False})
    state: dict[str, Any] = {"cleanup_475": {"status": "verified_absent"}}

    with pytest.raises(MiloviFinalizerBlocked, match="phase 2 has no delete authority"):
        finalize._cleanup_anomaly_475(
            writer=writer,  # type: ignore[arg-type]
            promoted_asset=_legacy_anomaly_asset(),
            finalizer=state,
            finalizer_path=tmp_path / "finalizer.json",
        )

    assert writer.delete_calls == 0
    assert state["cleanup_475"] == {"status": "verified_absent"}


def test_issue323_phase2_requires_durable_phase1_reconciliation(tmp_path: Path) -> None:
    writer = _ReadOnlyPhase2Writer({"owner_id": -68859909, "id": ANOMALY_POST_ID, "is_deleted": True})
    state: dict[str, Any] = {"cleanup_475": {"status": "pending"}}

    with pytest.raises(MiloviFinalizerBlocked, match="not durably reconciled by phase 1"):
        finalize._cleanup_anomaly_475(
            writer=writer,  # type: ignore[arg-type]
            promoted_asset=_legacy_anomaly_asset(),
            finalizer=state,
            finalizer_path=tmp_path / "finalizer.json",
        )

    assert writer.delete_calls == 0
    assert state["cleanup_475"] == {"status": "pending"}
