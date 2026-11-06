from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_target_binding import load_target_binding

WORKFLOW = Path(".github/workflows/lordchrist-shorts4-publisher.yml")
PROFILE = Path("content/telegram/channels/lordchrist-shorts-v1.json")
BINDING = Path("content/telegram/channels/lordchrist-shorts-v1-target-binding.json")
RELEASE = Path("content/telegram/lordchrist/shorts-v1-release.json")


def test_exact_four_video_workflow_is_one_writer_and_provider_conservative() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    profile = load_channel_profile(PROFILE)
    target = load_target_binding(BINDING, profile)
    release = load_release(RELEASE)
    assert profile.concurrency_group == "lordchrist-telegram-publisher"
    assert "group: lordchrist-telegram-publisher" in text
    assert profile.state_branch == "state/lordchrist-telegram"
    assert profile.channel_username == release.channel_username == "@lordchrist"
    assert target.chat_id == release.chat_id == -1001295216957
    assert "7 13 9-11 11 *" in text
    assert "lordchrist-short-ba4ZahiY-U0" in text
    assert "2026-11-08" in text
    assert "2026-11-11" in text or "now.day not in (9,10,11)" in text
    assert "state/lordchrist-telegram" in text
    assert "quote-v6-publication-ledger.json" not in text
    assert "shorts-v1-publication-ledger.json" in text
    assert "telegram_multichannel_cli prepare" in text
    assert "telegram_multichannel_cli send-once" in text
    assert text.index("Persist pre-send intent") < text.index("Exactly one native Telegram sendVideo attempt")
    assert text.index("Archive exact provider outcome") < text.index("Apply receipt")
    assert "telegram_multichannel_cli apply-outcome" in text
    assert "scripts.lordchrist_quote_v6_publisher import guard_cross_track" in text
    assert "github.event.workflow_run.head_sha == github.sha" in text
    assert "gh workflow run" not in text
    assert "manual" in text and "scheduled" in text


def test_no_scheduler_can_forge_first_manual_canary() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "9-11 11 *" in text
    assert "mode=manual" in text
    assert "publish-canary" in text
    assert "PUBLISH:$PUBLICATION_INPUT" in text
    assert "Manual video canary requires first exact Nov 8 item" in text
    assert "scheduled execution requires a verified manual canary" not in text
    assert "GITHUB_RUN_ATTEMPT" in text
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in text
    assert "sendVideo" in text
    assert "provider" in text.lower()
