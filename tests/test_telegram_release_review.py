from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release, save_release
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_release_review_cli import main
from video_channel_manager.telegram_research import load_research_queue
from video_channel_manager.telegram_research_release import build_research_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
BINDING_PATH = ROOT / "content/telegram/channels/lordchrist-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"
EXPECTED_CANDIDATE = "sha256:0f25f23fc87665b03df0b8486d6f336e8e405b6213457772ead6ce2a363cd07d"


def research_candidate():
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    research = load_research_queue(QUEUE_PATH)
    candidate = build_research_release_candidate(
        profile,
        research,
        release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
        start_at=datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow")),
        binding=binding,
    )
    assert candidate.candidate_digest() == EXPECTED_CANDIDATE
    return candidate


def test_exact_research_candidate_can_be_authorized_without_provider_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    candidate = research_candidate()
    approved = authorize_release_candidate(
        candidate,
        expected_candidate_sha256=EXPECTED_CANDIDATE,
        reviewed_by="FedorMilovanov",
        reviewed_at=datetime(2026, 8, 8, 9, 30, tzinfo=UTC),
    )

    assert approved.release_authorized is True
    assert approved.reviewed_candidate_sha256 == EXPECTED_CANDIDATE
    assert approved.reviewed_by == "FedorMilovanov"
    assert approved.target_binding_sha256 == candidate.target_binding_sha256
    assert approved.items == candidate.items
    assert approved.digest != candidate.digest


def test_review_rejects_candidate_drift_and_missing_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    candidate = research_candidate()
    with pytest.raises(ValueError, match="differs from the reviewed digest"):
        authorize_release_candidate(
            candidate,
            expected_candidate_sha256="sha256:" + "0" * 64,
            reviewed_by="FedorMilovanov",
            reviewed_at=datetime(2026, 8, 8, 9, 30, tzinfo=UTC),
        )

    unbound = candidate.model_copy(
        update={
            "target_binding_sha256": None,
            "chat_id": None,
            "bot_id": None,
            "bot_username": None,
        }
    )
    with pytest.raises(ValueError, match="complete exact target binding"):
        authorize_release_candidate(
            unbound,
            expected_candidate_sha256=unbound.candidate_digest(),
            reviewed_by="FedorMilovanov",
            reviewed_at=datetime(2026, 8, 8, 9, 30, tzinfo=UTC),
        )


def test_review_rejects_naive_time_blank_reviewer_and_double_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    candidate = research_candidate()
    with pytest.raises(ValueError, match="non-empty reviewer"):
        authorize_release_candidate(
            candidate,
            expected_candidate_sha256=EXPECTED_CANDIDATE,
            reviewed_by="   ",
            reviewed_at=datetime(2026, 8, 8, 9, 30, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        authorize_release_candidate(
            candidate,
            expected_candidate_sha256=EXPECTED_CANDIDATE,
            reviewed_by="FedorMilovanov",
            reviewed_at=datetime(2026, 8, 8, 9, 30),
        )

    approved = authorize_release_candidate(
        candidate,
        expected_candidate_sha256=EXPECTED_CANDIDATE,
        reviewed_by="FedorMilovanov",
        reviewed_at=datetime(2026, 8, 8, 9, 30, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="already authorized"):
        authorize_release_candidate(
            approved,
            expected_candidate_sha256=EXPECTED_CANDIDATE,
            reviewed_by="FedorMilovanov",
            reviewed_at=datetime(2026, 8, 8, 9, 31, tzinfo=UTC),
        )


def test_review_cli_writes_exact_approved_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(ROOT)
    candidate_path = tmp_path / "candidate.json"
    approved_path = tmp_path / "approved.json"
    save_release(candidate_path, research_candidate())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_release_review_cli",
            "--candidate",
            str(candidate_path),
            "--expected-candidate-sha256",
            EXPECTED_CANDIDATE,
            "--reviewed-by",
            "FedorMilovanov",
            "--reviewed-at",
            "2026-08-08T12:30:00+03:00",
            "--output",
            str(approved_path),
        ],
    )

    assert main() == 0
    summary = json.loads(capsys.readouterr().out)
    approved = load_release(approved_path)
    assert summary["authorized"] is True
    assert summary["reviewed_candidate_sha256"] == EXPECTED_CANDIDATE
    assert summary["approved_release_sha256"] == approved.digest
    assert approved.reviewed_at == datetime(2026, 8, 8, 9, 30, tzinfo=UTC)
