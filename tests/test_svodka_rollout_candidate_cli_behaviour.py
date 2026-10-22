"""`svodka_rollout_candidate_cli` is what the rollout-candidate workflow runs; verify it runs.

`tests/test_svodka_preflight_workflow.py` proves that the workflow *mentions* the module path.
Nothing executed the module, so the workflow's only provider-inert preparation step had 0%
coverage. These tests call the real `main()` and compare the artifact it writes with the release
the library builds from the same inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager import svodka_rollout_candidate_cli as cli
from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/svodka.json"
BINDING = ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE = ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def test_main_builds_the_candidate_the_library_builds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "candidate.json"

    status = cli.main(
        [
            "--profile",
            str(PROFILE),
            "--queue",
            str(QUEUE),
            "--binding",
            str(BINDING),
            "--release-id",
            "svodka-cli-behaviour-test",
            "--output",
            str(output),
        ]
    )

    assert status == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["built"] is True
    assert printed["provider_write_performed"] is False
    assert printed["release_id"] == "svodka-cli-behaviour-test"
    assert printed["output"] == str(output)

    profile = load_channel_profile(PROFILE)
    binding = load_target_binding(BINDING, profile)
    queue = load_svodka_draft(QUEUE, profile, apply_schedule_overlay=True)
    expected = build_svodka_release_candidate(
        profile, queue, release_id="svodka-cli-behaviour-test", binding=binding
    )
    written = load_release(output)

    assert written.digest == expected.digest
    assert printed["release_digest"] == expected.digest
    assert printed["count"] == len(expected.items)
    assert printed["chat_id"] == binding.chat_id
    assert printed["bot_username"] == binding.bot_username
    # A candidate is never authorized: authorization is a separate reviewed step.
    assert written.release_authorized is False
    assert printed["release_authorized"] is False


def test_main_requires_every_option(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--profile", str(PROFILE)])

    assert excinfo.value.code == 2


def test_main_refuses_a_binding_from_another_profile(tmp_path: Path) -> None:
    """A foreign binding must fail closed instead of producing a candidate for the wrong chat."""

    output = tmp_path / "candidate.json"

    with pytest.raises(ValueError):
        cli.main(
            [
                "--profile",
                str(PROFILE),
                "--queue",
                str(QUEUE),
                "--binding",
                str(ROOT / "content/telegram/channels/milovi-cake-target-binding.json"),
                "--release-id",
                "svodka-cli-behaviour-test",
                "--output",
                str(output),
            ]
        )

    assert not output.exists()
