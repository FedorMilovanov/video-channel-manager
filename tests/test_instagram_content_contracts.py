from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.editorial.instagram_launch_preview import build_instagram_launch_preview
from video_channel_manager.exchange.instagram_content import (
    InstagramAnalyticsMetrics,
    InstagramAnalyticsSnapshot,
    InstagramLaunchPack,
    InstagramMetricValue,
)


ROOT = Path(__file__).resolve().parents[1]
INSTAGRAM_CONTENT = ROOT / "content" / "instagram"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


@pytest.mark.parametrize(
    ("filename", "project_key"),
    [
        ("legendary-poet-launch-candidates.json", "legendary-poet"),
        ("lord-god-strength-launch-candidates.json", "lord-god-strength"),
    ],
)
def test_repository_launch_packs_are_typed_source_bound_and_provider_inert(
    filename: str,
    project_key: str,
) -> None:
    path = INSTAGRAM_CONTENT / filename
    raw = path.read_bytes()
    pack = InstagramLaunchPack.model_validate_json(raw)

    assert pack.project_key == project_key
    assert len(pack.candidates) == 9
    assert pack.provider_account_id is None
    assert pack.provider_writes_authorized is False
    assert all(candidate.blocking_unknowns for candidate in pack.candidates)

    preview = build_instagram_launch_preview(
        pack,
        source_pack_sha256=f"sha256:{hashlib.sha256(raw).hexdigest()}",
    )

    assert preview.project_key == project_key
    assert preview.provider_effect == "impossible"
    assert preview.provider_writes_authorized is False
    assert preview.counts.total == 9
    assert preview.counts.valid == 9
    assert preview.counts.blocked == 0
    assert preview.counts.errors == 0
    assert all(item.rendered_caption for item in preview.items)
    assert all(item.blocking_unknowns for item in preview.items)


def test_launch_pack_rejects_unknown_source_reference() -> None:
    raw = (INSTAGRAM_CONTENT / "legendary-poet-launch-candidates.json").read_bytes()
    pack = InstagramLaunchPack.model_validate_json(raw)
    payload = pack.model_dump(mode="json")
    payload["candidates"][0]["source_ids"] = ["does-not-exist"]

    with pytest.raises(ValidationError, match="unknown source_ids"):
        InstagramLaunchPack.model_validate(payload)


def test_analytics_unknown_is_null_not_zero() -> None:
    metrics = InstagramAnalyticsMetrics()

    assert metrics.reach.state == "not_observed"
    assert metrics.reach.value is None
    assert metrics.watch_time_seconds.value is None
    assert metrics.completion_ratio.value is None


def test_analytics_accepts_observed_zero_without_conflating_unknown() -> None:
    metrics = InstagramAnalyticsMetrics(
        reach=InstagramMetricValue(state="observed", unit="count", value=0),
    )

    assert metrics.reach.state == "observed"
    assert metrics.reach.value == 0
    assert metrics.saves.state == "not_observed"
    assert metrics.saves.value is None


def test_analytics_rejects_value_for_unavailable_metric() -> None:
    with pytest.raises(ValidationError, match="must be null"):
        InstagramMetricValue(state="unavailable", unit="count", value=0)


def test_analytics_snapshot_requires_exact_numeric_identity_and_time_order() -> None:
    published = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
    observed = datetime(2026, 8, 20, 11, 0, tzinfo=UTC)
    snapshot = InstagramAnalyticsSnapshot(
        project_key="legendary-poet",
        candidate_id="ig-poet-001-yesenin-ya-ustalym-reel",
        instagram_professional_account_id="123456789",
        instagram_media_id="987654321",
        creative_sha256=SHA_A,
        published_at=published,
        observed_at=observed,
        source_evidence_sha256=SHA_B,
        source="instagram_api",
    )

    assert snapshot.provider_effect == "read_only"
    assert snapshot.provider_writes_authorized is False
    assert snapshot.metrics.reach.value is None

    with pytest.raises(ValidationError, match="exact numeric provider IDs"):
        InstagramAnalyticsSnapshot(
            project_key="legendary-poet",
            candidate_id="ig-poet-001-yesenin-ya-ustalym-reel",
            instagram_professional_account_id="@TheLegendaryPoOet",
            instagram_media_id="987654321",
            creative_sha256=SHA_A,
            published_at=published,
            observed_at=observed,
            source_evidence_sha256=SHA_B,
            source="instagram_api",
        )

    with pytest.raises(ValidationError, match="cannot precede"):
        InstagramAnalyticsSnapshot(
            project_key="legendary-poet",
            candidate_id="ig-poet-001-yesenin-ya-ustalym-reel",
            instagram_professional_account_id="123456789",
            instagram_media_id="987654321",
            creative_sha256=SHA_A,
            published_at=published,
            observed_at=datetime(2026, 8, 20, 9, 0, tzinfo=UTC),
            source_evidence_sha256=SHA_B,
            source="instagram_api",
        )
