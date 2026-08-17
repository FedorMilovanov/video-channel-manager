from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-bootstrap-review-ready.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_review_ready_workflow_is_manual_attempt_one_and_read_only() -> None:
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


def test_review_ready_workflow_accepts_immutable_ancestor_only_when_milovi_critical_paths_are_unchanged() -> None:
    text = _text()

    assert "Check out current main for package-lineage proof" in text
    assert "fetch-depth: 0" in text
    assert 'git merge-base --is-ancestor "$EXPECTED_MAIN_SHA" "$GITHUB_SHA"' in text
    assert "source package revision is not an ancestor of current main" in text
    assert "Milovi-critical files changed after source package revision" in text
    assert "review-ready handoff only accepts a package from exact current main" not in text

    for critical_path in (
        ".github/workflows/milovi-telegram-bootstrap-activation-package.yml",
        "requirements/telegram-publisher.txt",
        "src/video_channel_manager/milovi_telegram_bootstrap.py",
        "src/video_channel_manager/milovi_telegram_activation_review.py",
        "src/video_channel_manager/telegram_channel_profile.py",
        "src/video_channel_manager/telegram_target_binding.py",
        "src/video_channel_manager/telegram_target_discovery.py",
        "src/video_channel_manager/telegram_multichannel_release.py",
        "content/telegram/channels/milovi-cake.json",
        "content/telegram/channels/milovi-cake-target-binding.json",
        "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json",
        "content/telegram/milovi-cake/bootstrap-first-screen-candidates-2026-08.json",
        "content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json",
        "content/telegram/milovi-cake/publishing-window-2026-08.json",
    ):
        assert critical_path in text

    # The review workflow itself is intentionally not a critical package input: this
    # provider-inert repair must be able to review an older immutable package.
    lineage_block = text.split("Prove source package revision remains review-eligible", 1)[1].split(
        "Check out immutable source package revision", 1
    )[0]
    assert ".github/workflows/milovi-telegram-bootstrap-review-ready.yml" not in lineage_block

    assert "Check out immutable source package revision" in text
    assert "ref: ${{ inputs.expected_main_sha }}" in text


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
    assert "milovi-bootstrap-review-ready-${{ inputs.expected_main_sha }}-${{ inputs.package_run_id }}" in text


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
