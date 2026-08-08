from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from video_channel_manager import telegram_channel_cli
from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release, save_release
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
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


def _write_candidate(path: Path, *, tamper_binding_digest: bool = False) -> str:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-cli-review",
        binding=binding,
    )
    if tamper_binding_digest:
        candidate = candidate.model_copy(update={"target_binding_sha256": "sha256:" + "0" * 64})
    save_release(path, candidate)
    return candidate.digest


def test_authorize_release_requires_current_binding_and_records_candidate_digest(monkeypatch, capsys, tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    release_path = tmp_path / "approved.json"
    candidate_digest = _write_candidate(candidate_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram-channel-cli",
            "authorize-svodka-release",
            "--profile",
            str(PROFILE_PATH),
            "--binding",
            str(BINDING_PATH),
            "--candidate",
            str(candidate_path),
            "--reviewed-by",
            "test-reviewer",
            "--reviewed-at",
            "2026-08-08T03:00:00+00:00",
            "--output",
            str(release_path),
        ],
    )

    assert telegram_channel_cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    release = load_release(release_path)
    assert output["reviewed_candidate_sha256"] == candidate_digest
    assert release.reviewed_candidate_sha256 == candidate_digest
    assert release.release_authorized is True


def test_authorize_release_rejects_candidate_with_stale_binding(monkeypatch, tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    release_path = tmp_path / "approved.json"
    _write_candidate(candidate_path, tamper_binding_digest=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram-channel-cli",
            "authorize-svodka-release",
            "--profile",
            str(PROFILE_PATH),
            "--binding",
            str(BINDING_PATH),
            "--candidate",
            str(candidate_path),
            "--reviewed-by",
            "test-reviewer",
            "--reviewed-at",
            "2026-08-08T03:00:00+00:00",
            "--output",
            str(release_path),
        ],
    )

    with pytest.raises(ValueError, match="current pinned target binding"):
        telegram_channel_cli.main()
    assert not release_path.exists()
