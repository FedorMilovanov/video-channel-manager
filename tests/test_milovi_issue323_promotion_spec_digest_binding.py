from __future__ import annotations

from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS


def _spec(first_text: str) -> PromotionSpec:
    fields = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            text = first_text if (source_id, field) == (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION) else f"reviewed {source_id} {field.value}"
            fields.append(
                ReviewedPromotionField(
                    source_id=source_id,
                    field=field,
                    policy=PromotionPolicy.ADOPT_REVIEWED_EXACT,
                    before_text=text,
                    before_sha256=promotion_text_sha256(text),
                )
            )
    return PromotionSpec(review_id="manual-review", fields=tuple(fields))


def test_digest_changes_when_any_reviewed_exact_text_changes() -> None:
    assert _spec("manual current A").digest != _spec("manual current B").digest
