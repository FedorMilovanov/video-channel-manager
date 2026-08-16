from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
    plan_reviewed_promotion_batch,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS


def test_batch_planner_refuses_partial_observation() -> None:
    fields = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            text = f"reviewed {source_id} {field.value}"
            fields.append(
                ReviewedPromotionField(
                    source_id=source_id,
                    field=field,
                    policy=PromotionPolicy.ADOPT_REVIEWED_EXACT,
                    before_text=text,
                    before_sha256=promotion_text_sha256(text),
                )
            )
    spec = PromotionSpec(review_id="complete-review", fields=tuple(fields))

    with pytest.raises(ValueError, match="exact 12x2 field set"):
        plan_reviewed_promotion_batch(spec, {})
