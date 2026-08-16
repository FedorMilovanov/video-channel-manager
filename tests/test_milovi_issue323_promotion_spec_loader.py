from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
    promotion_spec_from_mapping,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS


def _complete_spec() -> PromotionSpec:
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
    return PromotionSpec(review_id="explicit-human-review", fields=tuple(fields))


def test_loader_rejects_field_level_unreviewed_metadata() -> None:
    payload = _complete_spec().as_dict()
    raw_fields = payload["fields"]
    assert isinstance(raw_fields, list)
    raw_fields[0]["derived_from_title"] = True

    with pytest.raises(ValueError, match="unreviewed keys"):
        promotion_spec_from_mapping(payload)
