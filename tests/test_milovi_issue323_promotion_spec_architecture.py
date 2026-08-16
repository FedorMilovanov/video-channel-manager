from __future__ import annotations

from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "src/video_channel_manager/platforms/vk/milovi_issue323_promotion_spec.py"


def test_reviewed_promotion_spec_has_no_builder_or_provider_dependency() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert "milovi_promotion" not in source
    assert "public_clip_description" not in source
    assert "public_wall_message" not in source
    assert "VkApiClient" not in source
    assert "VkWallWriter" not in source
    assert "video.edit" not in source
    assert "wall.edit" not in source
