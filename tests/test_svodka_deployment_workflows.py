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
SKIP_EXPIRED_WORKFLOW = WORKFLOWS_DIR / "svodka-skip-expired.yml"
PREFLIGHT_WORKFLOW = WORKFLOWS_DIR / "svodka-telegram-preflight.yml"
QUALITY_WORKFLOW = WORKFLOWS_DIR / "svodka-quality.yml"
APPROVED_RELEASE_QUALITY_WORKFLOW = WORKFLOWS_DIR / "svodka-approved-release-quality.yml"
ROLLOUT_CANDIDATE_WORKFLOW = WORKFLOWS_DIR / "svodka-rollout-candidate.yml"
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
APPROVAL_PATH = REPOSITORY_ROOT / "content/telegram/svodka/release-approval-2026-08.json"

RETIRED_WORKFLOW_NAMES = {
    "svodka-canary.yml",
    "svodka-custom-emoji-capability-canary.yml",
    "svodka-custom-emoji-harvest.yml",
    "svodka-ledger-init.yml",
    "svodka-native-rich-message-canary.yml",
    "svodka-reconcile-provider-outcome.yml",
    "svodka-reconcile-skipped-send.yml",
    "svodka-rich-production.yml",
    "svodka-rich-reconcile-message-28.yml",
    "svodka-rich-successor.yml",
    "svodka-scheduled-publisher.yml",
}
REMAINING_WORKFLOW_NAMES = {
    "svodka-approved-release-quality.yml",
    "svodka-quality.yml",
    "svodka-rollout-candidate.yml",
    "svodka-skip-expired.yml",
    "svodka-telegram-preflight.yml",
}


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


def test_post_rollout_profile_closes_provider_write_gate_without_changing_identity() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)

    assert profile.project_key == "svodka"
    assert profile.channel_username == "@deep_info_life"
    assert profile.provider_writes_authorized is False
    assert profile.digest == "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9"
    assert binding.profile_sha256 == profile.digest


def test_only_provider_free_skip_expired_remains_in_svodka_state_writer_namespace() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    expected_group = f"group: {profile.concurrency_group}"
    discovered = {path for path in WORKFLOWS_DIR.glob("svodka-*.yml") if expected_group in _workflow(path)}

    assert discovered == {SKIP_EXPIRED_WORKFLOW}
    workflow = _workflow(SKIP_EXPIRED_WORKFLOW)
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    assert "runs-on: ubuntu-24.04" in workflow
    assert "secrets." not in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "sendRichMessage" not in workflow


def test_completed_and_expired_august_execution_workflows_are_retired() -> None:
    existing = {path.name for path in WORKFLOWS_DIR.glob("svodka-*.yml")}
    assert existing == REMAINING_WORKFLOW_NAMES
    assert existing.isdisjoint(RETIRED_WORKFLOW_NAMES)


def test_skip_expired_is_manual_exact_state_only_and_quality_proven() -> None:
    workflow = _workflow(SKIP_EXPIRED_WORKFLOW)

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "SKIP-EXPIRED:$REQUESTED_DIGEST" in workflow
    assert "skip-expired" in workflow
    _assert_materialized_release_contract(workflow)
    _assert_dual_current_main_quality(workflow)
    assert workflow.index("telegram_github_quality_gate") < workflow.index(
        'git -C "$STATE_DIR" commit -m "Skip expired Svodka publication windows [skip ci]"'
    )
    assert "SVODKA_TELEGRAM_BOT_TOKEN" not in workflow
    assert "secrets." not in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "sendRichMessage" not in workflow
    assert "send-once" not in workflow


def test_remaining_preflight_is_read_only_and_separate_from_state_writer_mutex() -> None:
    workflow = _workflow(PREFLIGHT_WORKFLOW)
    assert "contents: read" in workflow
    assert "group: svodka-telegram-preflight" in workflow
    assert "group: svodka-telegram-publisher" not in workflow
    assert "telegram_channel_cli preflight" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "sendRichMessage" not in workflow


def test_review_receipt_still_materializes_exact_historical_release_with_write_gate_closed(tmp_path: Path) -> None:
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

    assert profile.provider_writes_authorized is False
    assert candidate_digest == approval.candidate_sha256
    assert release_digest == approval.approved_release_sha256
    assert release.digest == approval.approved_release_sha256
    assert release.release_authorized is True
    assert release.project_key == profile.project_key
    assert release.profile_sha256 == profile.digest
    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == binding.chat_id
    assert release.bot_id == binding.bot_id
    assert release.bot_username == binding.bot_username


def test_remaining_svodka_workflows_pin_supported_runner_image() -> None:
    for name in REMAINING_WORKFLOW_NAMES:
        workflow = _workflow(WORKFLOWS_DIR / name)
        runs_on = [line.strip() for line in workflow.splitlines() if line.lstrip().startswith("runs-on:")]
        assert runs_on, name
        assert set(runs_on) == {"runs-on: ubuntu-24.04"}, name
        assert "ubuntu-latest" not in workflow, name


def test_quality_and_rollout_candidate_surfaces_remain_provider_free() -> None:
    for path in (QUALITY_WORKFLOW, APPROVED_RELEASE_QUALITY_WORKFLOW, ROLLOUT_CANDIDATE_WORKFLOW):
        workflow = _workflow(path)
        assert "contents: write" not in workflow, path.name
        assert "SVODKA_TELEGRAM_BOT_TOKEN" not in workflow, path.name
        assert "sendMessage" not in workflow, path.name
        assert "sendPoll" not in workflow, path.name
        assert "sendRichMessage" not in workflow, path.name
