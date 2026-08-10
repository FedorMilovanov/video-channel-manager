from __future__ import annotations

from datetime import datetime
from pathlib import Path

from video_channel_manager.lordchrist_research_rollout import (
    FIRST_CANARY_PUBLICATION_ID,
    load_lordchrist_research_rollout_approval,
    materialize_lordchrist_research_rollout,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_research import load_research_queue
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/lordchrist.json"
BINDING = ROOT / "content/telegram/channels/lordchrist-target-binding.json"
QUEUE = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"
APPROVAL = ROOT / "content/telegram/lordchrist/research-queues/rollout-approval-2026-08.json"
WORKFLOW = ROOT / ".github/workflows/lordchrist-research-v2-publisher.yml"
LEGACY = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def test_exact_rollout_materializes_only_from_reviewed_identity(tmp_path: Path) -> None:
    approval = load_lordchrist_research_rollout_approval(APPROVAL)
    base_profile = load_channel_profile(PROFILE)
    binding = load_target_binding(BINDING, base_profile)
    release, runtime_profile = materialize_lordchrist_research_rollout(
        profile_path=PROFILE,
        queue_path=QUEUE,
        binding_path=BINDING,
        approval_path=APPROVAL,
        release_output_path=tmp_path / "release.json",
        runtime_profile_output_path=tmp_path / "profile.json",
    )
    assert base_profile.provider_writes_authorized is False
    assert runtime_profile.provider_writes_authorized is True
    assert runtime_profile.digest == base_profile.digest
    assert release.release_authorized is True
    assert release.candidate_digest() == approval.candidate_sha256
    assert release.digest == approval.approved_release_sha256
    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == -1001295216957
    assert release.bot_id == 8716602202
    assert release.items[0].publication_id == FIRST_CANARY_PUBLICATION_ID
    assert [item.scheduled_at.isoformat() for item in release.items] == [
        "2026-08-10T15:00:00+03:00",
        "2026-08-12T15:00:00+03:00",
        "2026-08-14T15:00:00+03:00",
        "2026-08-16T15:00:00+03:00",
        "2026-08-18T15:00:00+03:00",
    ]


def test_canonical_research_and_profile_remain_inert() -> None:
    profile = load_channel_profile(PROFILE)
    research = load_research_queue(QUEUE)
    assert profile.provider_writes_authorized is False
    assert profile.daily_verified_limit == 1
    assert research.schedule.state == "staged"
    assert research.schedule.activation_at_utc is None
    assert research.schedule.canary_publication_id is None
    assert research.schedule.canary_message_id is None
    assert research.live_eligible is False


def test_workflow_is_canary_first_same_writer_and_bounded() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    legacy = LEGACY.read_text(encoding="utf-8")
    assert 'cron: "0 15 10-18 8 *"' in workflow
    assert 'cron: "47 15 10-18 8 *"' in workflow
    assert workflow.count("timezone: Europe/Moscow") == 2
    assert "group: lordchrist-telegram-publisher" in workflow
    assert "group: lordchrist-telegram-publisher" in legacy
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    assert "FIRST_CANARY_PUBLICATION_ID: lordchrist-research-three-preachers-numbers" in workflow
    assert "phase = 'canary'" in workflow
    assert "phase = 'scheduled'" in workflow
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in workflow
    assert "LEDGER_RELATIVE_PATH: content/telegram/lordchrist/research-v2/publication-ledger.json" in workflow
    assert "LEGACY_LEDGER_PATH: .state/lordchrist/content/telegram/lordchrist/publication-ledger.json" in workflow


def test_cross_track_quota_is_explicit_and_precedes_telegram_access() -> None:
    approval = load_lordchrist_research_rollout_approval(APPROVAL)
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert approval.per_track_daily_verified_limit == 1
    assert approval.cross_track_daily_verified_limit == 2
    assert approval.cross_track_guard_issue == 246
    quota = workflow.index("Enforce explicit legacy plus research daily ceiling")
    preflight = workflow.index("Fresh read-only exact target preflight")
    prepare = workflow.index("Prepare exactly one strict research dispatch")
    assert quota < preflight < prepare
    assert "lordchrist_research_cross_track_guard" in workflow
    assert "steps.cross_track_quota.outputs.capacity == 'true'" in workflow


def test_preflight_materializes_exact_target_inside_same_shell_step() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    preflight = workflow.split("      - name: Fresh read-only exact target preflight\n", 1)[1].split(
        "      - name: Prepare exactly one strict research dispatch\n", 1
    )[0]
    assert "GITHUB_ENV" not in preflight
    assert (
        "IFS=$'\\t' read -r LORDCHRIST_RESEARCH_CHAT_ID LORDCHRIST_RESEARCH_BOT_ID "
        "LORDCHRIST_RESEARCH_BOT_USERNAME" in preflight
    )
    assert 'print(f"{binding.chat_id}\\t{binding.bot_id}\\t{binding.bot_username}")' in preflight
    assert '--expected-chat-id "$LORDCHRIST_RESEARCH_CHAT_ID"' in preflight
    assert '--expected-bot-id "$LORDCHRIST_RESEARCH_BOT_ID"' in preflight
    assert '--expected-bot-username "$LORDCHRIST_RESEARCH_BOT_USERNAME"' in preflight


def test_workflow_orders_durable_intent_before_provider_and_outcome_before_state() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    persist = workflow.index("Persist research intent before Telegram mutation")
    reproof = workflow.index("Re-prove current-main CI immediately before Telegram mutation")
    send = workflow.index("Send exactly one research payload")
    archive = workflow.index("Archive exact research provider outcome before state mutation")
    apply = workflow.index("Apply and persist exact research provider outcome")
    assert persist < reproof < send < archive < apply
    assert workflow.count("GH_TOKEN:") == 3
    assert "if-no-files-found: error" in workflow
    assert "retention-days: 30" in workflow
    assert "!cancelled()" in workflow


def test_approval_binds_issue_and_today_start() -> None:
    approval = load_lordchrist_research_rollout_approval(APPROVAL)
    assert approval.owning_issue == 242
    assert approval.first_canary_publication_id == FIRST_CANARY_PUBLICATION_ID
    assert approval.start_at == datetime.fromisoformat("2026-08-10T15:00:00+03:00")
