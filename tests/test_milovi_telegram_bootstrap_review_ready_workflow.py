from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-bootstrap-review-ready.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_review_ready_workflow_is_manual_current_main_attempt_one_and_read_only() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert "package_run_id:" in text
    assert "expected_main_sha:" in text
    assert "expected_target_binding_sha256:" in text
    assert "expected_bound_candidate_sha256:" in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "github.ref == 'refs/heads/main' && github.run_attempt == 1" in text
    assert "persist-credentials: false" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text


def test_review_ready_workflow_pins_exact_source_run_and_artifact() -> None:
    text = _text()
    assert "source_event not in {'push', 'workflow_dispatch'}" in text
    assert "'source_run_event': source_event" in text
    assert "run.get('head_branch') != 'main'" in text
    assert "run.get('head_sha') != expected_sha" in text
    assert "milovi-telegram-bootstrap-activation-package.yml" in text
    assert "run.get('conclusion') != 'success'" in text
    assert "run.get('run_attempt') or 0" in text
    assert "source activation-package GitHub reruns are not reviewable" in text
    assert "milovi-bootstrap-activation-package-{expected_sha}" in text
    assert "source_artifact_digest" in text
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in text
    assert "run-id: ${{ inputs.package_run_id }}" in text
    assert "digest-mismatch: error" in text


def test_review_ready_workflow_never_discovers_target_authorizes_or_mutates_provider() -> None:
    text = _text()
    assert "milovi_telegram_activation_review" in text
    for forbidden in (
        "LORDCHRIST_TELEGRAM_BOT_TOKEN",
        "MILOVI_CAKE_TELEGRAM_BOT_TOKEN",
        "discover-target",
        "preflight",
        "telegram_release_review_cli",
        "authorize_release_candidate",
        "sendMessage",
        "sendPhoto",
        "sendPoll",
        "dispatch-provider",
        "state/milovi-cake-telegram",
        "git commit",
        "git push",
        "contents: write",
    ):
        assert forbidden not in text


def test_review_ready_receipt_is_short_lived_and_kept_under_one_runtime_root() -> None:
    text = _text()
    assert "RECEIPT_DIR: .runtime/milovi-bootstrap-review-ready" in text
    assert "SOURCE_METADATA_PATH: .runtime/milovi-bootstrap-review-ready/source-package-metadata.json" in text
    assert "path: ${{ env.RECEIPT_DIR }}" in text
    assert "/tmp/source-package-metadata.json" not in text
    assert "retention-days: 7" in text
