from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from video_channel_manager.domain.enums import RiskLevel
from video_channel_manager.exchange.change_plan import ChangePlan


@dataclass(frozen=True, slots=True)
class PlanPreview:
    total_operations: int
    enabled_operations: int
    disabled_operations: int
    operations_by_type: dict[str, int]
    operations_by_risk: dict[str, int]


def build_plan_preview(plan: ChangePlan) -> PlanPreview:
    enabled = [item for item in plan.operations if item.enabled]
    return PlanPreview(
        total_operations=len(plan.operations),
        enabled_operations=len(enabled),
        disabled_operations=len(plan.operations) - len(enabled),
        operations_by_type=dict(Counter(item.operation.value for item in enabled)),
        operations_by_risk=dict(Counter(item.risk.value for item in enabled)),
    )


def has_high_risk_operations(preview: PlanPreview) -> bool:
    return any(preview.operations_by_risk.get(level.value, 0) for level in (RiskLevel.HIGH, RiskLevel.DESTRUCTIVE))
