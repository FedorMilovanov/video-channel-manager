from __future__ import annotations

from video_channel_manager.platforms.vk import milovi_d48_youtube_fallback as fallback
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence


def test_fallback_is_pinned_to_uploaded_stable_retry() -> None:
    assert fallback.ACCEPTED_RETRY_ZIP_SHA256 == (
        "22604bc2329381b563e7243e66bbd548b93fbe770e3b8b23d0a6f9b0b0ca5022"
    )
    assert fallback.ACCEPTED_RETRY_RESULT_SHA256 == (
        "76f46a7ac7b8183a8033f6d859ac8cd96c2f426dea105771892f2563594053e6"
    )


def test_fallback_scope_is_only_d48_and_three_reviewed_vk_candidates() -> None:
    assert fallback.YOUTUBE_ID == "d48QLgOuiTs"
    assert fallback.VK_REMOTE_IDS == (
        "-68859909_456239182",
        "-68859909_456239172",
        "-68859909_456239115",
    )


def test_transport_urls_keep_exact_d48_identity() -> None:
    transports = fallback._transport_urls(fallback.YOUTUBE_ID)
    assert transports == (
        ("shorts", "https://www.youtube.com/shorts/d48QLgOuiTs"),
        ("watch", "https://www.youtube.com/watch?v=d48QLgOuiTs"),
    )
    for _name, url in transports:
        assert stable_sequence._stable_identity_url_matches(
            platform="youtube",
            expected_id=fallback.YOUTUBE_ID,
            raw_url=url,
        )
        assert not stable_sequence._stable_identity_url_matches(
            platform="youtube",
            expected_id="wrong-id",
            raw_url=url,
        )


def test_parser_keeps_headless_explicit() -> None:
    args = fallback.parser().parse_args(
        [
            "--input",
            "retry.zip",
            "--output-dir",
            "out",
            "--zip-output",
            "out.zip",
        ]
    )
    assert args.headless is False
    assert args.wait_ms == 1000

    args = fallback.parser().parse_args(
        [
            "--input",
            "retry.zip",
            "--output-dir",
            "out",
            "--zip-output",
            "out.zip",
            "--headless",
        ]
    )
    assert args.headless is True
