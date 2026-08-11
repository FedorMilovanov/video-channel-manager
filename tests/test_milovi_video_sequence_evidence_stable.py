from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as base
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable


def test_stable_youtube_embed_identity_is_exact() -> None:
    expected = "FQGxV4DRPQw"
    assert stable._stable_identity_url_matches(
        platform="youtube",
        expected_id=expected,
        raw_url=f"https://www.youtube-nocookie.com/embed/{expected}?autoplay=1&mute=1",
    )
    assert stable._stable_identity_url_matches(
        platform="youtube",
        expected_id=expected,
        raw_url=f"https://www.youtube.com/embed/{expected}",
    )
    assert not stable._stable_identity_url_matches(
        platform="youtube",
        expected_id=expected,
        raw_url="https://www.youtube-nocookie.com/embed/other",
    )


def test_stable_capture_urls_keep_exact_media_identity() -> None:
    youtube_id = "MdQ0kNBSsa8"
    remote_id = "-68859909_456239176"

    assert stable._youtube_capture_url(youtube_id).startswith(
        f"https://www.youtube-nocookie.com/embed/{youtube_id}?"
    )
    assert stable._vk_capture_url(remote_id) == f"https://vk.ru/clip{remote_id}"
    assert stable._stable_identity_url_matches(
        platform="vk",
        expected_id=remote_id,
        raw_url=stable._vk_capture_url(remote_id),
    )


def test_wrapper_source_remains_read_only() -> None:
    source = Path(stable.__file__).read_text(encoding="utf-8")

    assert '"provider_writes": 0' in source
    assert ".click(" not in source
    assert ".fill(" not in source
    assert ".press(" not in source
    assert "set_input_files" not in source
    assert "video.save" not in source
    assert "wall.post" not in source


def test_wrapper_restores_base_functions_after_build_failure(tmp_path: Path) -> None:
    original_capture = base._capture_page_sequence
    original_identity = base._identity_url_matches

    missing_input = tmp_path / "missing.zip"
    try:
        stable.build_video_sequence_evidence(
            input_zip=missing_input,
            output_dir=tmp_path / "out",
            zip_output=tmp_path / "out.zip",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected missing input to fail")

    assert base._capture_page_sequence is original_capture
    assert base._identity_url_matches is original_identity
