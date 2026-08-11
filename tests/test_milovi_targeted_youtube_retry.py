from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.platforms.vk import milovi_targeted_youtube_retry as retry


def test_retry_scope_is_exactly_the_two_failed_youtube_ids() -> None:
    assert retry.RETRY_PAIRS == {
        "d48QLgOuiTs": (
            "-68859909_456239182",
            "-68859909_456239172",
            "-68859909_456239115",
        ),
        "uA8SbnXzJJc": ("-68859909_456239109",),
    }
    assert sum(len(remote_ids) for remote_ids in retry.RETRY_PAIRS.values()) == 4


def test_retry_is_pinned_to_the_accepted_exact_vk_probe() -> None:
    assert retry.ACCEPTED_MEDIA_PROBE_ZIP_SHA256 == ("89aefa40e51450ab3823db1f794ccf262203d8dd14ac5f2543f10b4ec69487ea")
    assert retry.ACCEPTED_MEDIA_PROBE_RESULT_SHA256 == (
        "c3db469e1b4c6d450481b87951db16b13a9ffa93b4d292ceb91553f458a61f36"
    )


def test_retry_rejects_invalid_wait_before_touching_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="wait_ms"):
        retry.build_targeted_retry(
            input_zip=tmp_path / "missing.zip",
            output_dir=tmp_path / "out",
            zip_output=tmp_path / "out.zip",
            wait_ms=100,
        )


def test_parser_keeps_headless_explicit() -> None:
    args = retry.parser().parse_args(
        [
            "--input",
            "probe.zip",
            "--output-dir",
            "out",
            "--zip-output",
            "out.zip",
        ]
    )
    assert args.headless is False

    args = retry.parser().parse_args(
        [
            "--input",
            "probe.zip",
            "--output-dir",
            "out",
            "--zip-output",
            "out.zip",
            "--headless",
        ]
    )
    assert args.headless is True
