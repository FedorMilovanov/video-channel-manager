from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_cli import _send_exact_payload
from video_channel_manager.telegram_multichannel_state import initialize_ledger, prepare_next
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
GITHUB_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40


def test_missing_token_becomes_explicit_not_dispatched_outcome(monkeypatch) -> None:
    base_profile = load_channel_profile(PROFILE_PATH)
    profile = base_profile.model_copy(update={"provider_writes_authorized": True})
    draft = load_svodka_draft(QUEUE_PATH, profile)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-missing-token-test",
        binding=binding,
    )
    release = authorize_svodka_release(
        candidate,
        reviewed_by="runtime-test",
        reviewed_at=datetime(2026, 8, 8, 0, 0, tzinfo=UTC),
    )
    ledger = initialize_ledger(release)
    now = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    first_id = release.items[0].publication_id
    prepared = prepare_next(
        profile,
        release,
        ledger,
        run_id="777",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target,
        expected_publication_id=first_id,
        now=now,
    )
    assert prepared.envelope is not None

    monkeypatch.delenv(profile.bot_token_env, raising=False)
    outcome = _send_exact_payload(profile, release, ledger, prepared.envelope)

    assert outcome.provider_effect == "not_dispatched"
    assert outcome.retryable is False
    assert outcome.receipt is None
    assert outcome.error == f"missing Telegram token in {profile.bot_token_env}"
