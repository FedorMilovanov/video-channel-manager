from __future__ import annotations

from pathlib import Path

from _workflow_actions import MINIMUM_RELEASES, assert_actions_pinned, assert_no_retired_refs


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "lord-god-vk-postponed-wave.yml"
RUNBOOK = ROOT / "docs" / "operations" / "lord-god-vk-daily-postponed-runbook.md"

DOWNLOAD_ARTIFACT_PIN = "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131 # v7.0.0"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job_sections() -> tuple[str, str]:
    text = _workflow_text()
    prepare, apply = text.split("\n  apply:\n", 1)
    return prepare, apply


def test_lord_god_workflow_actions_are_pinned_and_download_artifact_is_reviewed() -> None:
    text = _workflow_text()

    pins = assert_actions_pinned(text, source=WORKFLOW.name)
    assert_no_retired_refs(text, source=WORKFLOW.name)

    assert {pin.action for pin in pins} == {
        "actions/checkout",
        "actions/download-artifact",
        "actions/setup-python",
        "actions/upload-artifact",
    }
    assert MINIMUM_RELEASES["actions/download-artifact"] == (7, 0, 0)
    assert DOWNLOAD_ARTIFACT_PIN in text


def test_lord_god_workflow_is_manual_main_only_and_environment_gated() -> None:
    text = _workflow_text()

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert text.count("environment: The_Lord_God_VK") == 2
    assert text.count("github.ref == 'refs/heads/main'") == 2
    assert text.count("github.run_attempt == 1") == 2
    assert "group: lord-god-vk-postponed-wave" in text
    assert "cancel-in-progress: false" in text
    assert "queue: max" in text
    assert "actions: read" in text
    assert "contents: read" in text

    # The VK token exists only as an Environment secret reference in the two
    # import steps. It is never a workflow input, artifact path or repository file.
    assert text.count("secrets.LORD_SECRET") == 2
    assert text.count("VCM_VK_ACCESS_TOKEN: ${{ secrets.LORD_SECRET }}") == 2
    assert "VK_OWN_APP_54555649_TOKEN" not in text
    assert "vk_tokens.json" not in text
    assert "${{ env.VCM_DATA_DIR }}\n" not in text


def test_prepare_stage_is_provider_inert_and_builds_the_reviewed_handoff() -> None:
    prepare, _apply = _job_sections()

    assert "video-manager wave apply" not in prepare
    assert "actions/download-artifact" not in prepare
    assert "ref: state/lordchrist-telegram" in prepare
    assert "persist-credentials: false" in prepare

    login = prepare.index('video-manager vk community-key-login --account "$VK_ACCOUNT"')
    capabilities = prepare.index('video-manager vk community-key-capabilities --account "$VK_ACCOUNT"')
    audit = prepare.index("python scripts/build_vk_wall_content_audit.py")
    backlog = prepare.index("python scripts/build_lord_god_content_backlog_v2.py")
    handoff = prepare.index("python scripts/prepare_lord_god_content_wave.py")

    assert login < capabilities < audit < backlog < handoff
    assert "video-manager vk community-probe" not in prepare
    assert "video-manager vk wall-probe" not in prepare
    assert "video-manager vk token-capabilities" not in prepare
    assert '"wall" not in permissions' in prepare
    assert "start_date must be a Monday in Europe/Moscow" in prepare
    assert "start_date must be in the future in Europe/Moscow" in prepare

    for phrase in (
        '--candidate "$SUCCESSOR_CANDIDATE_PATH"',
        '--integrity-amendments "$SUCCESSOR_INTEGRITY_AMENDMENTS_PATH"',
        '--source-v1-runtime-queue "$SOURCE_V1_RUNTIME_QUEUE_PATH"',
        '--depth-v2-runtime-queue "$DEPTH_V2_RUNTIME_QUEUE_PATH"',
        '--runtime-queue "$DEPTH_RUNTIME_QUEUE_PATH"',
        '--depth-ledger "$DEPTH_LEDGER_PATH"',
        '--restore "$DEPTH_RESTORE_PATH"',
        "--confirm INITIALIZE_REVIEWED_DEPTH_V3_LEDGER",
        '--account "$VK_ACCOUNT"',
        '--community "$VK_COMMUNITY_ID"',
        '--output-dir "$AUDIT_OUTPUT_DIR"',
        '--quote-ledger "$EFFECTIVE_DEPTH_LEDGER_PATH"',
        "--days 60",
        "--video-count 60",
        "--telegram-count 1",
        "--quote-count 24",
        "--historical-text-mode full",
        "--max-views 1500",
        '--output-dir "$HANDOFF_DIR"',
        "--enable-provider-writes",
        "source.verify_artifacts(root)",
        "intent.assert_matches(plan, source)",
        "plan contains a postponed publish_date",
        "name: lord-god-vk-audit-${{ github.run_id }}-${{ github.run_attempt }}",
        "name: ${{ env.HANDOFF_ARTIFACT_NAME }}",
        "retention-days: 30",
    ):
        assert phrase in prepare


def test_apply_stage_downloads_verifies_and_applies_the_exact_handoff_once() -> None:
    text = _workflow_text()
    _prepare, apply = _job_sections()

    assert text.count("video-manager wave apply") == 1
    assert DOWNLOAD_ARTIFACT_PIN in apply
    assert "name: ${{ env.HANDOFF_ARTIFACT_NAME }}" in apply
    assert "path: ${{ env.HANDOFF_DIR }}" in apply
    assert "run-id: ${{ inputs.prepare_run_id }}" in apply
    assert "github-token: ${{ github.token }}" in apply

    confirmation = apply.index("Validate exact apply confirmation before downloading the handoff")
    download = apply.index("Download the immutable prepare handoff")
    verify = apply.index("Verify downloaded handoff against exact operator confirmation")
    login = apply.index('video-manager vk community-key-login --account "$VK_ACCOUNT"')
    capabilities = apply.index('video-manager vk community-key-capabilities --account "$VK_ACCOUNT"')
    wave_apply = apply.index("video-manager wave apply")

    assert confirmation < download < verify < login < capabilities < wave_apply
    assert "video-manager vk community-probe" not in apply
    assert "video-manager vk wall-probe" not in apply
    assert "video-manager vk token-capabilities" not in apply

    for phrase in (
        "REQUESTED_PREPARE_RUN_ID: ${{ inputs.prepare_run_id }}",
        "REQUESTED_PLAN_SELF_DIGEST: ${{ inputs.plan_self_digest }}",
        "REQUESTED_OPERATION_SET_DIGEST: ${{ inputs.operation_set_digest }}",
        "REQUESTED_CONFIRM: ${{ inputs.confirm }}",
        "prepare_run_id must be a numeric GitHub run ID",
        "apply must be a separate run from prepare",
        "plan_self_digest must be an exact 64-character lowercase hex digest",
        "operation_set_digest must be an exact 64-character lowercase hex digest",
        "APPLY-LORD-GOD-VK:{prepare_run_id}:{plan_digest}:{operation_digest}",
        "EXPECTED_PLAN_SELF_DIGEST: ${{ inputs.plan_self_digest }}",
        "EXPECTED_OPERATION_SET_DIGEST: ${{ inputs.operation_set_digest }}",
        "downloaded plan_self_digest differs from the confirmed value",
        "downloaded operation_set_digest differs from the confirmed value",
        "source.verify_artifacts(root)",
        "intent.assert_matches(plan, source)",
        '--source "$HANDOFF_DIR/06-source.json"',
        '--plan "$HANDOFF_DIR/07-plan.json"',
        '--intent "$HANDOFF_DIR/08-apply-intent.json"',
        "--repository-root .",
        '--journal-directory "$APPLY_JOURNAL_DIR"',
        '--vk-account "$VK_ACCOUNT"',
        "--enable-provider-writes",
        "${{ env.APPLY_JOURNAL_DIR }}/result.json",
        "${{ env.APPLY_JOURNAL_DIR }}/preflight-summary.json",
        "${{ env.APPLY_JOURNAL_DIR }}/operations/*.json",
        "${{ env.VCM_DATA_DIR }}/vk/token_capabilities_flood_state.json",
        "if-no-files-found: warn",
        "retention-days: 90",
    ):
        assert phrase in apply


def test_lord_god_runbook_describes_the_github_prepare_apply_path() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    for phrase in (
        "lord-god-vk-postponed-wave.yml",
        "GitHub Environment",
        "The_Lord_God_VK",
        "LORD_SECRET",
        "community-key-login",
        "action=prepare",
        "action=apply",
        "APPLY-LORD-GOD-VK:<prepare_run_id>:<plan_self_digest>:<operation_set_digest>",
        "state/lordchrist-telegram",
        "Не запускайте apply второй раз",
        "wave reconcile",
        "Посты, присланные текстом",
    ):
        assert phrase in text


def test_prepare_supports_the_community_key_text_only_lane() -> None:
    prepare, _apply = _job_sections()
    text = _workflow_text()

    assert "lane:" in text
    assert "default: text-only" in text
    assert prepare.count("if: inputs.lane == 'full'") >= 3
    assert "if: inputs.lane == 'text-only'" in prepare
    assert "--text-only" in prepare
    assert "--video-count 0" in prepare
    # The text-only handoff must not reference audit artifacts at all.
    text_only_step = prepare.split("Build the provider-inert 60-day text-only backlog", 1)[1].split("- name:", 1)[0]
    assert "AUDIT_JSON" not in text_only_step
    handoff_step = prepare.split("Prepare the immutable provider-inert text-only handoff", 1)[1].split("- name:", 1)[0]
    assert "--videos" not in handoff_step


def test_workflow_repository_file_paths_exist() -> None:
    # Regression (prepare run failure): env pointed at
    # successor-translation-ledger.json / successor-integrity-amendments.json
    # while the committed files carry the -v1 suffix. Every committed-content
    # path referenced by the workflow env must exist in the repository;
    # state-checkout paths (.state/...) and runtime dirs are excluded.
    import re

    text = _workflow_text()
    referenced = sorted(set(re.findall(r"(?m)^  [A-Z0-9_]+: (content/\S+)$", text)))

    assert referenced, "expected the workflow to reference committed content files"
    for relative in referenced:
        assert (ROOT / relative).is_file(), f"workflow references missing repository file: {relative}"
