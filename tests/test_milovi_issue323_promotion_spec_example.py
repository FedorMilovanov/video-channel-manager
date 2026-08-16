from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import promotion_spec_from_mapping

EXAMPLE = Path(__file__).resolve().parents[1] / "docs/milovi-issue323-promotion-spec.example.json"


def test_documented_partial_example_is_deliberately_rejected_as_live_spec() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    with pytest.raises(ValueError):
        promotion_spec_from_mapping(payload)
