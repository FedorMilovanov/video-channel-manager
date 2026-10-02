from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, build_depth_runtime_queue, load_depth_activation
from video_channel_manager.telegram_schedule import load_production_schedule

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
WORKFLOW = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def test_depth_v2_staging_identity_is_exact_but_provider_inert() -> None:
    activation = load_depth_activation(CONTENT / "successor-depth-activation-v1.json")
    schedule = load_production_schedule(CONTENT / "production-schedule.json")
    policy = load_presentation_policy(CONTENT / "presentation-policy-v3.json")

    assert activation.provider_writes_authorized is False
    assert activation.queue_digest == DEPTH_QUEUE_DIGEST
    assert activation.presentation_policy_id == policy.policy_id == "lordchrist-quote-v3"
    assert activation.presentation_policy_sha256 == policy.digest
    assert schedule.enabled is False
    assert "paused" in schedule.activation_note.lower()
    assert schedule.successor_queue_digest == DEPTH_QUEUE_DIGEST
    assert schedule.presentation_policy_id == policy.policy_id
    assert schedule.presentation_policy_sha256 == policy.digest


def test_depth_v2_runtime_is_release_scoped_and_starts_future_work_at_sequence_15() -> None:
    queue = build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )

    assert queue.release_id == "lordchrist-successor-depth-v2"
    assert queue.digest == DEPTH_QUEUE_DIGEST
    assert queue.posts[14].sequence == 15
    assert queue.posts[14].publication_id.startswith("lordchrist-successor-depth-v2-15-")
    assert "Пояснение:" not in queue.posts[14].text
    assert "© " not in queue.posts[14].text


def test_production_workflow_has_no_old_successor_runtime_fallback() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    publish_next = workflow.split("  historical-rich:\n", 1)[0]

    assert "video_channel_manager.telegram_quote_depth resolve" in publish_next
    assert "video_channel_manager.telegram_quote_depth initialize-ledger" in publish_next
    assert "video_channel_manager.telegram_quote_runtime resolve" not in publish_next
    assert "INITIALIZE_REVIEWED_DEPTH_V2_LEDGER" in publish_next
    assert "successor-depth-v2-publication-ledger.json" in publish_next
    assert "presentation-policy-v3.json" in publish_next
    assert "remote-depth-v2-ledger.json" in publish_next
    assert "--require-provider-writes" in publish_next
    assert "steps.intent.outputs.do_publish" in publish_next


def test_rollout_artifacts_do_not_mutate_sealed_source_v1_identity() -> None:
    source_activation = json.loads((CONTENT / "successor-activation-v1.json").read_text(encoding="utf-8"))
    assert source_activation["successor_queue_digest"] == "sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"
    assert source_activation["presentation_policy_id"] == "lordchrist-editorial-v2"
