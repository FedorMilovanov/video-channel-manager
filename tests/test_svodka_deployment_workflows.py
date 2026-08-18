from __future__ import annotations

from pathlib import Path

from video_channel_manager.svodka_approval_cli import (
    load_svodka_release_approval,
    materialize_svodka_approved_release,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPOSITORY_ROOT / ".github/workflows"
LEDGER_WORKFLOW = WORKFLOWS_DIR / "svodka-ledger-init.yml"
CANARY_WORKFLOW = WORKFLOWS_DIR / "svodka-canary.yml"
CUSTOM_EMOJI_CANARY_WORKFLOW = WORKFLOWS_DIR / "svodka-custom-emoji-capability-canary.yml"
NATIVE_RICH_CANARY_WORKFLOW = WORKFLOWS_DIR / "svodka-native-rich-message-canary.yml"
RETIRED_RICH_PRODUCTION_WORKFLOW = WORKFLOWS_DIR / "svodka-rich-production.yml"
SUCCESSOR_WORKFLOW = WORKFLOWS_DIR / "svodka-rich-successor.yml"
SKIP_EXPIRED_WORKFLOW = WORKFLOWS_DIR / "svodka-skip-expired.yml"
SCHEDULED_WORKFLOW = WORKFLOWS_DIR / "svodka-scheduled-publisher.yml"
RECONCILE_SKIPPED_WORKFLOW = WORKFLOWS_DIR / "svodka-reconcile-skipped-send.yml"
RECONCILE_OUTCOME_WORKFLOW = WORKFLOWS_DIR / "svodka-reconcile-provider-outcome.yml"
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
APPROVAL_PATH = REPOSITORY_ROOT / "content/telegram/svodka/release-approval-2026-08.json"

RELEASE_STATE_WRITER_WORKFLOWS = (
    LEDGER_WORKFLOW,
    SKIP_EXPIRED_WORKFLOW,
    CANARY_WORKFLOW,
    SCHEDULED_WORKFLOW,
    RECONCILE_SKIPPED_WORKFLOW,
    RECONCILE_OUTCOME_WORKFLOW,
)
LEGACY_SERIALIZED_WRITERS = RELEASE_STATE_WRITER_WORKFLOWS + (
    CUSTOM_EMOJI_CANARY_WORKFLOW,
    NATIVE_RICH_CANARY_WORKFLOW,
)


def _workflow(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_materialized_release_contract(workflow: str) -> None:
    assert "release-approval-2026-08.json" in workflow
    assert "video_channel_manager.svodka_approval_cli" in workflow
    assert '--approval "$APPROVAL_PATH"' in workflow
    assert "RELEASE_PATH: .runtime/svodka-approved-release.json" in workflow


def _assert_dual_current_main_quality(workflow: str) -> None:
    assert "svodka-quality.yml" in workflow
    assert "svodka-approved-release-quality.yml" in workflow
    assert '--sha "$GITHUB_SHA"' in workflow


def test_legacy_state_writers_share_lossless_serialization_contract() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    expected_group = f"group: {profile.concurrency_group}"
    discovered = {
        path
        for path in WORKFLOWS_DIR.glob("*.yml")
        if expected_group in _workflow(path)
    }

    assert not RETIRED_RICH_PRODUCTION_WORKFLOW.exists()
    assert discovered == set(LEGACY_SERIALIZED_WRITERS)
    for path in discovered:
        workflow = _workflow(path)
        assert "cancel-in-progress: false" in workflow, path.name
        assert "queue: max" in workflow, path.name
        assert "runs-on: ubuntu-24.04" in workflow, path.name
    for path in RELEASE_STATE_WRITER_WORKFLOWS:
        _assert_materialized_release_contract(_workflow(path))


def test_successor_writer_is_manual_only_and_uses_its_own_serialization_group() -> None:
    workflow = _workflow(SUCCESSOR_WORKFLOW)
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "schedule:" not in workflow
    assert "contents: write" in workflow
    assert "group: svodka-rich-successor" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    assert "runs-on: ubuntu-24.04" in workflow
    assert "SVODKA-RICH-SUCCESSOR:@deep_info_life" in workflow
    assert "Persist intent before Telegram mutation" in workflow
    assert "Send exactly one successor Rich Message" in workflow
    assert "Apply provider outcome and persist terminal state" in workflow
    assert "sendMessage" not in workflow

    persist = workflow.index("Persist intent before Telegram mutation")
    send = workflow.index("Send exactly one successor Rich Message")
    apply = workflow.index("Apply provider outcome and persist terminal state")
    assert persist < send < apply


def test_custom_emoji_capability_canary_is_manual_serialized_and_release_independent() -> None:
    workflow = _workflow(CUSTOM_EMOJI_CANARY_WORKFLOW)
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "CUSTOM-EMOJI-CANARY:@deep_info_life:ONE-POST" in workflow
    assert "group: svodka-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    _assert_dual_current_main_quality(workflow)
    assert "release-approval-2026-08.json" not in workflow
    assert "Persist intent before Telegram mutation" in workflow
    assert "Archive exact canary outcome before durable-state mutation" in workflow
    assert "Persist exact canary outcome and block blind retry" in workflow
    assert "sendMessage" not in workflow
    assert "deleteMessage" not in workflow


def test_native_rich_canary_is_manual_main_only_serialized_and_release_independent() -> None:
    workflow = _workflow(NATIVE_RICH_CANARY_WORKFLOW)
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "RICH-CANARY:@deep_info_life:ONE-ARTICLE" in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "group: svodka-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    _assert_dual_current_main_quality(workflow)
    assert "Persist durable intent before any Telegram mutation" in workflow
    assert "Dispatch exactly one native sendRichMessage mutation" in workflow
    assert "Archive exact provider outcome before durable outcome" in workflow
    assert "sendMessage" not in workflow
    assert "deleteMessage" not in workflow


def test_release_workflows_remain_manual_or_provider_free_and_quality_bound() -> None:
    for path in RELEASE_STATE_WRITER_WORKFLOWS:
        workflow = _workflow(path)
        _assert_materialized_release_contract(workflow)
        if "send-once" in workflow:
            _assert_dual_current_main_quality(workflow)
            assert "Persist" in workflow
        else:
            assert "sendMessage" not in workflow
            assert "sendPoll" not in workflow


def test_no_push_triggered_write_capable_svodka_workflows_remain() -> None:
    assert sorted(path.name for path in WORKFLOWS_DIR.glob("svodka-*-once.yml")) == []
    for path in WORKFLOWS_DIR.glob("svodka-*.yml"):
        workflow = _workflow(path)
        if "push:" in workflow:
            assert "contents: write" not in workflow, path.name


def test_all_svodka_workflows_pin_supported_runner_image() -> None:
    for path in WORKFLOWS_DIR.glob("svodka-*.yml"):
        workflow = _workflow(path)
        runs_on = [
            line.strip()
            for line in workflow.splitlines()
            if line.lstrip().startswith("runs-on:")
        ]
        assert runs_on, path.name
        assert set(runs_on) == {"runs-on: ubuntu-24.04"}, path.name
        assert "ubuntu-latest" not in workflow, path.name


def test_review_receipt_materializes_exact_authorized_historical_release(tmp_path: Path) -> None:
    output = tmp_path / "approved-release.json"
    approval = load_svodka_release_approval(APPROVAL_PATH)
    candidate_digest, release_digest = materialize_svodka_approved_release(
        profile_path=PROFILE_PATH,
        queue_path=QUEUE_PATH,
        binding_path=BINDING_PATH,
        approval_path=APPROVAL_PATH,
        output_path=output,
    )
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    release = load_release(output)

    assert candidate_digest == approval.candidate_sha256
    assert release_digest == approval.approved_release_sha256
    assert release.digest == approval.approved_release_sha256
    assert release.release_authorized is True
    assert release.project_key == profile.project_key
    assert release.channel_username == profile.channel_username
    assert release.profile_sha256 == profile.digest
    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == binding.chat_id
    assert release.bot_id == binding.bot_id
    assert release.bot_username == binding.bot_username
