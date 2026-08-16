from __future__ import annotations

from pathlib import Path

MODULE = (
    Path(__file__).resolve().parents[1]
    / "src/video_channel_manager/platforms/vk/milovi_issue323_promotion_spec.py"
)


def test_promotion_spec_plan_explicitly_never_authorizes_provider_mutation() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert '"provider_mutation_authorized": False' in source
    assert "confirmation_required" in source
    assert "mutation_authorized" not in source
