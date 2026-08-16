from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from video_channel_manager.milovi_telegram_bootstrap import build_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_release_binding import bind_release_candidate
from video_channel_manager.telegram_target_binding import target_binding_from_proof

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-bootstrap-activation-package.yml"
PUBLISHER_WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-bootstrap-publisher.yml"
MILOVI = ROOT / "content" / "telegram" / "milovi-cake"
ACTIVE_ROLLOUT = "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
PROFILE = ROOT / "content" / "telegram" / "channels" / "milovi-cake.json"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_activation_package_runs_on_relevant_current_main_changes_and_stays_read_only() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert "  push:" in text
    assert "    branches:\n      - main" in text
    for path in (
        ".github/workflows/milovi-telegram-bootstrap-activation-package.yml",
        "requirements/telegram-publisher.txt",
        "src/video_channel_manager/milovi_telegram_bootstrap.py",
        "src/video_channel_manager/telegram_channel_cli.py",
        "src/video_channel_manager/telegram_channel_profile.py",
        "src/video_channel_manager/telegram_target_binding.py",
        "src/video_channel_manager/telegram_target_binding_cli.py",
        "src/video_channel_manager/telegram_release_binding.py",
        "src/video_channel_manager/telegram_release_binding_cli.py",
        "src/video_channel_manager/telegram_multichannel_release.py",
        "src/video_channel_manager/telegram_multichannel_transport.py",
        "content/telegram/channels/milovi-cake.json",
        ACTIVE_ROLLOUT,
        "content/telegram/milovi-cake/bootstrap-first-screen-candidates-2026-08.json",
        "content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json",
        "content/telegram/milovi-cake/publishing-window-2026-08.json",
    ):
        assert f'      - "{path}"' in text
    assert "schedule:" not in text
    assert "pull_request:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "persist-credentials: false" in text
    assert "provider_writes_authorized') is not False" in text


def test_activation_package_and_publisher_compile_same_operational_rollout() -> None:
    package_text = _text()
    publisher_text = PUBLISHER_WORKFLOW.read_text(encoding="utf-8")
    rollout_env = f"ROLLOUT_PATH: {ACTIVE_ROLLOUT}"

    assert rollout_env in package_text
    assert rollout_env in publisher_text
    assert '--rollout "$ROLLOUT_PATH"' in package_text
    assert '--rollout "$ROLLOUT_PATH"' in publisher_text
    assert "bootstrap-rollout-candidate-2026-08.json" not in package_text


def test_activation_package_discovers_only_exact_reviewed_milovi_target() -> None:
    text = _text()
    assert "PROFILE_PATH: content/telegram/channels/milovi-cake.json" in text
    assert "EXPECTED_CHAT_ID: -1002215328390" in text
    assert "EXPECTED_BOT_ID: 8716602202" in text
    assert "EXPECTED_BOT_USERNAME: preaching_mp3_bot" in text
    assert "MILOVI_CAKE_TELEGRAM_BOT_TOKEN: ${{ secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN }}" in text
    assert "telegram_channel_cli discover-target" in text
    assert "telegram_target_binding_cli" in text


def test_activation_package_builds_then_binds_but_never_authorizes_release() -> None:
    text = _text()
    assert "milovi_telegram_bootstrap build-release" in text
    assert "telegram_release_binding_cli" in text
    assert "--expected-unbound-candidate-sha256" in text
    assert "bootstrap-unbound.json" in text
    assert "bootstrap-bound-unauthorized.json" in text
    assert "release_authorized') is not False" in text
    assert "reviewed_candidate_sha256" in text
    assert "unbound_candidate_sha256" in text
    assert "bound_candidate_sha256" in text
    assert "target_binding_sha256" in text
    assert "telegram_release_review_cli" not in text
    assert "authorize_release_candidate" not in text


def test_activation_package_has_no_provider_or_state_mutation_path() -> None:
    text = _text()
    for forbidden in (
        "sendMessage",
        "sendPhoto",
        "sendPoll",
        "dispatch-provider",
        "telegram_multichannel_cli prepare",
        "telegram_multichannel_cli record-outcome",
        "state/milovi-cake-telegram",
        "git commit",
        "git push",
        "provider_writes_authorized=true",
    ):
        assert forbidden not in text
    assert "provider_write_performed" in text
    assert "read_only_target_discovery_only" in text


def test_activation_package_is_ephemeral_and_preserves_exact_ten_items() -> None:
    text = _text()
    assert "bootstrap_items': 10" in text
    assert "len(candidate.get('items') or []) != 10" in text
    assert "unbound.get('items') != bound.get('items')" in text
    assert "milovi-bootstrap-activation-package-${{ github.sha }}" in text
    assert "retention-days: 7" in text


def test_activation_package_pipeline_binds_real_active_bootstrap_without_authorizing() -> None:
    profile = load_channel_profile(PROFILE)
    assert profile.provider_writes_authorized is False

    proof = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="milovi-cake",
        channel_username="@MiloviCake",
        profile_sha256=profile.digest,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1002215328390,
        chat_username="MiloviCake",
        chat_title="Milovi Cake",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime(2026, 8, 17, 0, 30, tzinfo=UTC),
    )
    binding = target_binding_from_proof(profile, proof)
    assert binding.provider_write_performed is False

    unbound = build_release_candidate(
        profile,
        rollout_path=ROOT / ACTIVE_ROLLOUT,
        candidates_path=MILOVI / "bootstrap-first-screen-candidates-2026-08.json",
        transport_proof_path=MILOVI / "bootstrap-photo-transport-proof-2026-08.json",
        publishing_window_path=MILOVI / "publishing-window-2026-08.json",
    )
    assert len(unbound.items) == 10
    assert unbound.release_authorized is False
    assert unbound.target_binding_sha256 is None
    assert unbound.items[0].scheduled_at.isoformat() == "2026-08-17T10:30:00+03:00"
    assert unbound.items[-1].scheduled_at.isoformat() == "2026-08-21T20:00:00+03:00"

    bound = bind_release_candidate(
        unbound,
        profile=profile,
        binding=binding,
        expected_unbound_candidate_sha256=unbound.candidate_digest(),
    )
    assert bound.items == unbound.items
    assert bound.release_authorized is False
    assert bound.reviewed_candidate_sha256 is None
    assert bound.reviewed_by is None
    assert bound.reviewed_at is None
    assert bound.target_binding_sha256 == binding.digest
    assert bound.chat_id == -1002215328390
    assert bound.bot_id == 8716602202
    assert bound.bot_username == "preaching_mp3_bot"
    assert bound.candidate_digest() != unbound.candidate_digest()
