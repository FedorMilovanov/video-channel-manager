from __future__ import annotations

from dataclasses import replace

from video_channel_manager.platforms.vk import milovi_d48_youtube_overlay_clean as clean
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence


def _capture_with_phashes(phashes: list[str]) -> sequence.CaptureResult:
    frames = tuple(
        {
            "index": index,
            "position": 0.06 + index * 0.08,
            "target_time_s": float(index + 1),
            "observed_time_s": float(index + 1),
            "filename": f"{index:02d}.jpg",
            "sha256": f"sha-{index}",
            "dhash": f"{index:016x}",
            "phash": phash,
            "source_width": 360,
            "source_height": 640,
        }
        for index, phash in enumerate(phashes)
    )
    return sequence.CaptureResult(
        status="captured",
        canonical_url="https://www.youtube.com/watch?v=d48QLgOuiTs",
        final_url="https://www.youtube.com/watch",
        duration_s=34.781,
        video_width=360,
        video_height=640,
        frames=frames,
        page_title="target",
        block_hints=(),
        error=None,
    )


def test_overlay_clean_is_pinned_to_uploaded_fallback() -> None:
    assert clean.ACCEPTED_FALLBACK_ZIP_SHA256 == "5b45553bc792b7eaf7adec5fda3e0fbc7d9aa0c1af76d87d71c878cdb4d6e2f6"
    assert clean.ACCEPTED_FALLBACK_RESULT_SHA256 == "d65b8078a780250481fbbbd99d2b3819c1fdd30c4ad257d4fa3a3b5b412c6007"


def test_overlay_clean_scope_is_only_d48_and_three_vk_candidates() -> None:
    assert clean.YOUTUBE_ID == "d48QLgOuiTs"
    assert clean.VK_REMOTE_IDS == (
        "-68859909_456239182",
        "-68859909_456239172",
        "-68859909_456239115",
    )


def test_transport_order_prefers_nocookie_then_clean_watch() -> None:
    transports = clean._transport_urls(clean.YOUTUBE_ID)
    assert transports[0][0] == "nocookie_embed"
    assert transports[0][1].startswith("https://www.youtube-nocookie.com/embed/d48QLgOuiTs?")
    assert transports[1] == ("watch_overlay_clean", "https://www.youtube.com/watch?v=d48QLgOuiTs")


def test_perceptual_gate_rejects_twelve_distinct_jpegs_with_one_phash() -> None:
    capture = _capture_with_phashes(["cb19fc4c805dc2cf"] * 12)
    gated = clean._perceptual_diversity_gate(capture)
    assert gated.status == "visual_capture_obscured"
    assert gated.frames == ()
    assert gated.error is not None
    assert "1 unique pHash" in gated.error


def test_perceptual_gate_accepts_real_perceptual_diversity() -> None:
    phashes = [f"{index:016x}" for index in range(12)]
    capture = _capture_with_phashes(phashes)
    assert clean._perceptual_diversity_gate(capture) == capture


def test_perceptual_gate_leaves_non_captured_result_unchanged() -> None:
    capture = _capture_with_phashes(["0" * 16] * 12)
    failed = replace(capture, status="capture_error", frames=())
    assert clean._perceptual_diversity_gate(failed) == failed


def test_parser_keeps_headless_explicit() -> None:
    args = clean.parser().parse_args(
        [
            "--input",
            "fallback.zip",
            "--output-dir",
            "out",
            "--zip-output",
            "out.zip",
        ]
    )
    assert args.headless is False
    assert args.wait_ms == 1000
