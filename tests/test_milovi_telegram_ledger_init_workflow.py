from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-ledger-init.yml"
PUBLISHER = ROOT / ".github" / "workflows" / "milovi-telegram-bootstrap-publisher.yml"
STATE_BRANCH = "state/milovi-cake-telegram"
AUTHORIZED_RELEASE = "content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json"
ACTIVE_ROLLOUT = "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_milovi_ledger_init_is_manual_exact_main_and_single_attempt_only() -> None:
    text = _text()

    assert "  workflow_dispatch:" in text
    assert "  schedule:" not in text
    assert "  push:" not in text
    assert "  pull_request:" not in text
    assert "expected_main_sha:" in text
    assert "release_digest:" in text
    assert "confirm:" in text
    assert "github.ref == 'refs/heads/main' && github.run_attempt == 1" in text
    assert 'expected_main != os.environ["GITHUB_SHA"]' in text
    assert 'confirmation != f"INITIALIZE:{requested_digest}"' in text


def test_milovi_ledger_init_reuses_publisher_identity_schedule_and_concurrency() -> None:
    text = _text()
    publisher = PUBLISHER.read_text(encoding="utf-8")

    assert "group: milovi-cake-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert f"STATE_BRANCH: {STATE_BRANCH}" in text
    assert f"AUTHORIZED_RELEASE_PATH: {AUTHORIZED_RELEASE}" in text
    assert f"ROLLOUT_PATH: {ACTIVE_ROLLOUT}" in text
    assert f"STATE_BRANCH: {STATE_BRANCH}" in publisher
    assert f"AUTHORIZED_RELEASE_PATH: {AUTHORIZED_RELEASE}" in publisher
    assert f"ROLLOUT_PATH: {ACTIVE_ROLLOUT}" in publisher
    assert "EXPECTED_CHAT_ID" not in text
    assert "binding.chat_id != -1002215328390" in text
    assert "binding.bot_id != 8716602202" in text
    assert 'binding.bot_username.casefold() != "preaching_mp3_bot"' in text


def test_milovi_ledger_init_requires_reviewed_release_before_any_state_write() -> None:
    text = _text()

    assert "profile.provider_writes_authorized is not False" in text
    assert "authorized.digest != requested_digest" in text
    assert "not authorized.release_authorized" in text
    assert "not authorized.reviewed_candidate_sha256" in text
    assert "not authorized.reviewed_by" in text
    assert "authorized.reviewed_at is None" in text
    assert "authorized.items != expected.items" in text
    assert "authorized.target_binding_sha256 != binding.digest" in text
    assert "len(authorized.items) != 10" in text

    validation = text.index("Verify exact reviewed release and explicit initialization authority")
    quality = text.index("Require exact current-main Milovi bootstrap quality")
    state_creation = text.index("Create isolated state branch from exact current main if absent")
    assert validation < quality < state_creation


def test_milovi_ledger_init_creates_missing_state_branch_from_exact_main_only() -> None:
    text = _text()

    assert "permissions:\n  actions: read\n  contents: write" in text
    assert 'current_main = os.environ["GITHUB_SHA"]' in text
    assert "if exc.code != 404:" in text
    assert '"ref": f"refs/heads/{branch}", "sha": current_main' in text
    assert '"creation_base_sha": current_main if created else None' in text
    assert "ref: state/milovi-cake-telegram" in text
    assert "persist-credentials: true" in text


def test_milovi_ledger_init_initializes_once_and_stages_only_ledger() -> None:
    text = _text()

    assert 'if [[ -f "$LEDGER_PATH" ]]; then' in text
    assert "telegram_multichannel_cli validate-ledger" in text
    assert "Matching Milovi ledger already exists; refusing to overwrite it." in text
    assert "telegram_multichannel_cli initialize-ledger" in text
    assert '--confirm "INITIALIZE:$REQUESTED_DIGEST"' in text
    assert 'staged="$(git -C "$STATE_DIR" diff --cached --name-only)"' in text
    assert '[[ "$staged" == "$LEDGER_RELATIVE_PATH" ]]' in text
    assert 'git -C "$STATE_DIR" push origin "HEAD:$STATE_BRANCH"' in text
    assert '[[ "$local_sha" == "$remote_sha" ]]' in text


def test_milovi_ledger_init_has_no_telegram_provider_access_path() -> None:
    text = _text()

    for forbidden in (
        "TELEGRAM_BOT_TOKEN",
        "api.telegram.org",
        "discover-target",
        "sendMessage",
        "sendPhoto",
        "sendPoll",
        "dispatch-provider",
        "telegram_multichannel_cli prepare",
        "telegram_multichannel_cli record-outcome",
    ):
        assert forbidden not in text
    assert "provider_access_performed=false" in text
