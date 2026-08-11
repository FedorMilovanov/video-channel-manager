from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as base
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable


def test_stable_youtube_embed_identity_is_exact() -> None:
    expected = "FQGxV4DRPQw"
    assert stable._stable_identity_url_matches(
        platform="youtube",
        expected_id=expected,
        raw_url=stable._youtube_capture_url(expected),
    )
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
        raw_url=stable._youtube_capture_url("other"),
    )


def test_stable_capture_urls_bind_exact_media_identity() -> None:
    youtube_id = "MdQ0kNBSsa8"
    remote_id = "-68859909_456239176"

    assert stable._youtube_capture_url(youtube_id) == f"{stable._LOCAL_YOUTUBE_ORIGIN}/youtube/{youtube_id}"
    embed_url = stable._youtube_embed_url(youtube_id)
    assert embed_url.startswith(f"https://www.youtube-nocookie.com/embed/{youtube_id}?")
    assert "enablejsapi=1" in embed_url
    assert "origin=http%3A%2F%2F127.0.0.1%3A8765" in embed_url

    document = stable._youtube_embed_document(youtube_id)
    assert f"/embed/{youtube_id}" in document
    assert 'referrerpolicy="strict-origin-when-cross-origin"' in document

    vk_url = stable._vk_capture_url(remote_id)
    assert vk_url == "https://vk.com/clip_ext.php?oid=-68859909&id=456239176&autoplay=1"
    assert stable._stable_identity_url_matches(
        platform="vk",
        expected_id=remote_id,
        raw_url=vk_url,
    )
    assert not stable._stable_identity_url_matches(
        platform="vk",
        expected_id=remote_id,
        raw_url="https://vk.com/clip_ext.php?oid=-68859909&id=456239175&autoplay=1",
    )


def test_temporal_diversity_gate_suppresses_collapsed_capture() -> None:
    repeated = tuple(
        {
            "index": index,
            "sha256": "same-frame",
        }
        for index in range(12)
    )
    capture = base.CaptureResult(
        status="captured",
        canonical_url="https://vk.com/clip-68859909_456239130",
        final_url="https://vk.com/clip_ext.php",
        duration_s=39.0,
        video_width=720,
        video_height=1280,
        frames=repeated,
        page_title="",
        block_hints=(),
    )

    gated = stable._temporal_diversity_gate(capture)
    assert gated.status == "temporal_capture_unreliable"
    assert gated.frames == ()
    assert gated.error is not None
    assert "collapsed" in gated.error


def test_temporal_diversity_gate_accepts_moving_capture() -> None:
    frames = tuple(
        {
            "index": index,
            "sha256": f"frame-{index}",
        }
        for index in range(12)
    )
    capture = base.CaptureResult(
        status="captured",
        canonical_url="https://vk.com/clip-68859909_456239176",
        final_url="https://vk.com/clip_ext.php",
        duration_s=35.0,
        video_width=720,
        video_height=1280,
        frames=frames,
        page_title="",
        block_hints=(),
    )

    assert stable._temporal_diversity_gate(capture) is capture


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
