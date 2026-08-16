from __future__ import annotations

from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import PromotionPolicy


def test_reviewed_policy_vocabulary_is_exact_and_small() -> None:
    assert {policy.value for policy in PromotionPolicy} == {
        "managed_exact",
        "adopt_reviewed_exact",
        "preserve_external",
    }
