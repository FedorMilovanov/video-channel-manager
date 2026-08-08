from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_research_release_cli import main

ROOT = Path(__file__).parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
QUEUE_PATH = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"


def test_research_release_cli_builds_unauthorized_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(ROOT)
    output = tmp_path / "candidate.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_research_release_cli",
            "--profile",
            str(PROFILE_PATH),
            "--queue",
            str(QUEUE_PATH),
            "--release-id",
            "lordchrist-research-calvin-spurgeon-macarthur-v1",
            "--start-at",
            "2026-08-09T19:17:00+03:00",
            "--output",
            str(output),
        ],
    )

    assert main() == 0
    summary = json.loads(capsys.readouterr().out)
    release = load_release(output)

    assert summary["candidate_built"] is True
    assert summary["release_authorized"] is False
    assert summary["target_bound"] is False
    assert summary["candidate_sha256"] == release.candidate_digest()
    assert summary["release_sha256"] == release.digest
    assert release.release_authorized is False
    assert release.target_binding_sha256 is None
    assert [item.scheduled_at.isoformat() for item in release.items] == [
        "2026-08-09T19:17:00+03:00",
        "2026-08-11T19:17:00+03:00",
        "2026-08-13T19:17:00+03:00",
        "2026-08-15T19:17:00+03:00",
        "2026-08-17T19:17:00+03:00",
    ]
