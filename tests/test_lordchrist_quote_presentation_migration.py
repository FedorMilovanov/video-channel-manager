from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_presentation_migration import load_migration

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
EXPECTED_QUEUE_DIGEST = "sha256:c2ad28bb96e88a9e0633c4b7a55d6033bbf29c5a557e1aa4478cc2e0359e3441"
EXPECTED_V3_DIGEST = "sha256:c6350861bcdbf3de9816afc398db5d80c605ae9fc0e750c3f7850e2e68449e0f"
EXPECTED_V4_DIGEST = "sha256:e5b4041702c74b4e06e4dd409a7cfaba4726bd81c8a0f34d2f6f0403295ead4c"


def test_presentation_migration_preserves_published_1_to_15_and_only_targets_future_suffix() -> None:
    migration = load_migration(CONTENT / "successor-depth-presentation-migration-v1.json")

    assert migration.release_id == "lordchrist-successor-depth-v2"
    assert migration.queue_digest == EXPECTED_QUEUE_DIGEST
    assert migration.published_boundary == 15
    assert migration.provider_writes_authorized is False
    assert "1-15" in migration.reason
    assert "16-60" in migration.reason


def test_presentation_migration_is_bound_to_exact_reviewed_v3_and_v4_policies() -> None:
    migration = load_migration(CONTENT / "successor-depth-presentation-migration-v1.json")
    v3 = load_presentation_policy(CONTENT / "presentation-policy-v3.json")
    v4 = load_presentation_policy(CONTENT / "presentation-policy-v4.json")

    assert migration.from_policy_id == v3.policy_id == "lordchrist-quote-v3"
    assert migration.from_policy_sha256 == v3.digest == EXPECTED_V3_DIGEST
    assert migration.to_policy_id == v4.policy_id == "lordchrist-quote-v4"
    assert migration.to_policy_sha256 == v4.digest == EXPECTED_V4_DIGEST
    assert migration.from_policy_sha256 != migration.to_policy_sha256
