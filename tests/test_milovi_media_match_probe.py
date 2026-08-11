from __future__ import annotations

from video_channel_manager.platforms.vk import milovi_media_match_probe as probe


def test_exhaustive_review_is_exact_confectionery_scope() -> None:
    assert len(probe.EXHAUSTIVE_REVIEW) == 13
    assert {row["scope"] for row in probe.EXHAUSTIVE_REVIEW.values()} <= {"CAKE", "DESSERT"}
    assert "P2Bpt77k408" not in probe.EXHAUSTIVE_REVIEW
    assert "jZjDWn_MNq0" not in probe.EXHAUSTIVE_REVIEW
    assert "2yhQ4nMWm3I" not in probe.EXHAUSTIVE_REVIEW


def test_probe_plan_is_bounded_and_exact_owner() -> None:
    pairs = probe._probe_pairs()
    assert len(pairs) == 18
    assert len(set(pairs)) == len(pairs)
    assert {youtube_id for youtube_id, _ in pairs} <= set(probe.EXHAUSTIVE_REVIEW)
    assert all(remote_id.startswith("-68859909_") for _, remote_id in pairs)


def test_known_gold_cake_repost_suspect_is_probed_for_both_youtube_rows() -> None:
    expected = {"-68859909_456239082", "-68859909_456239096"}
    assert set(probe.EXHAUSTIVE_REVIEW["SiluLt5Bz1c"]["probe_remote_ids"]) == expected
    assert set(probe.EXHAUSTIVE_REVIEW["BAVKrQQ00XI"]["probe_remote_ids"]) == expected
    assert probe.VK_INTERNAL_DUPLICATE_PROBES[0][:2] == (
        "-68859909_456239082",
        "-68859909_456239096",
    )


def test_no_shortlist_is_not_absence_authority() -> None:
    assert probe.EXHAUSTIVE_REVIEW["Oix9s6l9vNg"]["probe_remote_ids"] == ()
    assert probe.EXHAUSTIVE_REVIEW["5B9OuXbdGKc"]["probe_remote_ids"] == ()
    assert probe.EXPECTED_PUBLIC_VK_CLIP_COUNT == 106
    assert probe.EXPECTED_MEDIA_CANDIDATE_COUNT == 13
