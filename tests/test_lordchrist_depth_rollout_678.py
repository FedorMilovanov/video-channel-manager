from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_depth import (
    DEPTH_QUEUE_DIGEST,
    build_depth_runtime_queue,
    load_depth_activation,
)
from video_channel_manager.telegram_schedule import load_production_schedule

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
WORKFLOW = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def test_depth_v2_activation_and_schedule_form_one_exact_production_identity() -> None:
    activation = load_depth_activation(CONTENT / "successor-depth-activation-v1.json")
    schedule = load_production_schedule(CONTENT / "production-schedule.json")
    policy = load_presentation_policy(CONTENT / "presentation-policy-v3.json")

    assert activation.provider_writes_authorized is True
    assert activation.queue_digest == DEPTH_QUEUE_DIGEST
    assert activation.presentation_policy_id == policy.policy_id == "lordchrist-quote-v3"
    assert activation.presentation_policy_sha256 == policy.digest
    # The sealed depth-v2 activation keeps the 14/46 handoff identity and the quote-v3
    # digest it was sealed with; arming the live schedule is carried by the rolling
    # quote-v4 runtime activation checkpoint instead of by mutating the seal.
    runtime_activation = json.loads(
        (CONTENT / "successor-depth-runtime-activation-v5.json").read_text(encoding="utf-8")
    )
    v5_policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")
    assert activation.required_published_prefix == 14
    assert activation.required_pending_suffix == 46
    assert schedule.enabled is runtime_activation["provider_writes_authorized"]
    assert "depth-v3" in schedule.activation_note.casefold() or "v4" in schedule.activation_note.casefold()
    # successor_queue_digest is the legacy predecessor digest (distinct from the live v4 queue digest)
    assert schedule.successor_queue_digest == "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
    assert schedule.presentation_policy_id == v5_policy.policy_id == "lordchrist-quote-v5"
    assert schedule.presentation_policy_sha256 == v5_policy.digest
    assert runtime_activation["presentation_policy_sha256"] == v5_policy.digest


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


def test_production_workflow_resolves_directly_from_v4_queue() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    publish_next = workflow.split("  historical-rich:\n", 1)[0]

    # After the v4 cutover, the publisher resolves directly from the strict-schema
    # 30-post queue rather than running the depth-v3 successor-resolution pipeline.
    assert "video_channel_manager.telegram_quote_depth resolve" not in publish_next
    assert "INITIALIZE_STRICT_TELEGRAM_LEDGER" in publish_next
    assert "INITIALIZE_REVIEWED_DEPTH_V3_LEDGER" not in publish_next
    assert "verified-30-posts.json" in publish_next
    assert "lordchrist-puritan-spurgeon-v4" in publish_next


def test_rollout_artifacts_do_not_mutate_sealed_source_v1_identity() -> None:
    source_activation = json.loads((CONTENT / "successor-activation-v1.json").read_text(encoding="utf-8"))
    assert (
        source_activation["successor_queue_digest"]
        == "sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"
    )
    assert source_activation["presentation_policy_id"] == "lordchrist-editorial-v2"
