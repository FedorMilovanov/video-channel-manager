from __future__ import annotations

import pytest

from video_channel_manager.youtube_provider_semantics import (
    canonical_srt_sha256,
    classify_boolean_readback,
    effect_after_accepted_mutation,
    manual_caption_ids,
    playlist_contains_video,
    playlist_item_video_id,
    tags_equivalent,
)


def test_tags_are_order_insensitive_but_multiplicity_preserving() -> None:
    expected = ["Есенин", "Чёрный человек", "Есенин"]

    assert tags_equivalent(expected, ["Чёрный человек", "Есенин", "Есенин"])
    assert not tags_equivalent(expected, ["Чёрный человек", "Есенин"])
    assert not tags_equivalent(expected, ["Чёрный человек", "Есенин", "Yesenin"])


def test_boolean_readback_distinguishes_unobserved_from_false() -> None:
    missing = classify_boolean_readback(payload={}, key="containsSyntheticMedia", expected=True)
    null = classify_boolean_readback(
        payload={"containsSyntheticMedia": None}, key="containsSyntheticMedia", expected=True
    )
    explicit_false = classify_boolean_readback(
        payload={"containsSyntheticMedia": False},
        key="containsSyntheticMedia",
        expected=True,
    )
    explicit_true = classify_boolean_readback(
        payload={"containsSyntheticMedia": True},
        key="containsSyntheticMedia",
        expected=True,
    )

    assert missing.verdict == "unobserved"
    assert missing.actual is None
    assert null.verdict == "unobserved"
    assert explicit_false.verdict == "mismatch"
    assert explicit_false.actual is False
    assert explicit_true.verdict == "verified"
    assert explicit_true.actual is True


def test_accepted_mutation_with_empty_readback_is_may_exist() -> None:
    assert effect_after_accepted_mutation(provider_accepted=True, readback_verified=False) == "may_exist"
    assert effect_after_accepted_mutation(provider_accepted=True, readback_verified=True) == "verified"
    assert effect_after_accepted_mutation(provider_accepted=False, readback_verified=False) == "not_dispatched"

    with pytest.raises(ValueError, match="never accepted"):
        effect_after_accepted_mutation(provider_accepted=False, readback_verified=True)


def test_playlist_item_video_id_accepts_both_documented_shapes() -> None:
    by_content_details = {"contentDetails": {"videoId": "x-puy27S2qs"}}
    by_resource_id = {"snippet": {"resourceId": {"kind": "youtube#video", "videoId": "x-puy27S2qs"}}}

    assert playlist_item_video_id(by_content_details) == "x-puy27S2qs"
    assert playlist_item_video_id(by_resource_id) == "x-puy27S2qs"
    assert playlist_item_video_id({"snippet": {}}) is None


def test_playlist_contains_video_uses_exact_id() -> None:
    items = [
        {"contentDetails": {"videoId": "other"}},
        {"snippet": {"resourceId": {"videoId": "x-puy27S2qs"}}},
    ]

    assert playlist_contains_video(items, video_id="x-puy27S2qs")
    assert not playlist_contains_video(items, video_id="x-puy27S2q")


def test_canonical_srt_preserves_text_and_timing() -> None:
    base = b"1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\nWorld\n"
    digest = canonical_srt_sha256(base, duration_seconds=2)
    assert canonical_srt_sha256(b"\xef\xbb\xbf" + base.replace(b"\n", b"\r\n")) == digest
    assert canonical_srt_sha256(base.replace(b"Hello", b"Hello ")) == digest
    assert canonical_srt_sha256(base.replace(b"Hello", b"Other")) != digest
    assert canonical_srt_sha256(base.replace(b"00:00:02,000", b"00:00:02,100")) != digest


@pytest.mark.parametrize(
    "data",
    [
        b"\xff",
        b"",
        b"2\n00:00:00,000 --> 00:00:01,000\nText",
        b"1\n00:00:60,000 --> 00:00:01,000\nText",
        b"1\n00:00:02,000 --> 00:00:01,000\nText",
        b"1\n00:00:00,000 --> 00:00:03,000\nText",
        b"1\n00:00:01,000 --> 00:00:02,000\nText\n\n2\n00:00:00,000 --> 00:00:01,000\nOther",
        b"1\n00:00:00,000 --> 00:00:01,000\n   ",
    ],
)
def test_canonical_srt_rejects_bad_cues(data: bytes) -> None:
    with pytest.raises(ValueError):
        canonical_srt_sha256(data, duration_seconds=2)


def test_manual_caption_identity_does_not_count_asr() -> None:
    tracks = {
        "asr": {"language": "ru", "trackKind": "ASR"},
        "manual": {"language": "RU", "name": "", "trackKind": "standard"},
        "other": {"language": "ru", "name": "Other", "trackKind": "standard"},
    }
    assert manual_caption_ids(tracks, "ru", "") == ["manual"]
    with pytest.raises(ValueError, match="Incomplete"):
        manual_caption_ids({"unknown": {}}, "ru", "")
