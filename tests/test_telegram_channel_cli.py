from __future__ import annotations

import json
import sys
from pathlib import Path

from video_channel_manager import telegram_channel_cli

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def test_svodka_quiz_preview_uses_sendpoll_bot_api_10_2(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram-channel-cli",
            "preview-svodka",
            "--profile",
            str(PROFILE_PATH),
            "--queue",
            str(QUEUE_PATH),
            "--sequence",
            "7",
        ],
    )
    assert telegram_channel_cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["provider_method"] == "sendPoll"
    assert output["publication_id"] == "svodka-quiz-lightning-vs-sun"
    assert output["correct_option_ids"] == [0]
    assert output["description"].startswith("- Сводка -\n\n📎")
    assert "NOAA" in output["description"]
    assert output["provider_payload_sha256"].startswith("sha256:")


def test_svodka_fact_preview_remains_sendmessage(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram-channel-cli",
            "preview-svodka",
            "--profile",
            str(PROFILE_PATH),
            "--queue",
            str(QUEUE_PATH),
            "--sequence",
            "1",
        ],
    )
    assert telegram_channel_cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["provider_method"] == "sendMessage"
    assert output["publication_id"] == "svodka-venus-day-longer-than-year"
    assert "НА ВЕНЕРЕ ДЕНЬ ДЛИННЕЕ ГОДА" in output["expected_plain_text"]
    assert output["provider_payload_sha256"].startswith("sha256:")
