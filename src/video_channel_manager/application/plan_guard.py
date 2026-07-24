from __future__ import annotations

from dataclasses import dataclass, field

from video_channel_manager.config.settings import AppSettings
from video_channel_manager.domain.enums import (
    DESTRUCTIVE_OPERATIONS,
    MUTATING_EXISTING_TARGET_OPERATIONS,
    RiskLevel,
)
from video_channel_manager.exchange.change_plan import ChangePlan


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    operation_id: str | None = None


@dataclass(slots=True)
class PlanValidationResult:
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


class PlanGuard:
    """Policy validation independent from Pydantic schema validation."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def validate(self, plan: ChangePlan) -> PlanValidationResult:
        result = PlanValidationResult()
        enabled = [item for item in plan.operations if item.enabled]

        if len(enabled) > self.settings.max_operations_per_plan:
            result.errors.append(
                ValidationIssue(
                    code="operation_limit_exceeded",
                    message=(
                        f"Plan has {len(enabled)} enabled operations; limit is "
                        f"{self.settings.max_operations_per_plan}."
                    ),
                )
            )

        for operation in enabled:
            operation_id = str(operation.operation_id)
            if operation.operation in DESTRUCTIVE_OPERATIONS and not self.settings.allow_destructive_operations:
                result.errors.append(
                    ValidationIssue(
                        code="destructive_operation_disabled",
                        message=f"Operation {operation.operation} is disabled by policy.",
                        operation_id=operation_id,
                    )
                )

            if (
                self.settings.require_expected_revision
                and operation.operation in MUTATING_EXISTING_TARGET_OPERATIONS
                and not operation.expected_revision
            ):
                result.errors.append(
                    ValidationIssue(
                        code="missing_expected_revision",
                        message="Mutation of an existing remote object requires expected_revision.",
                        operation_id=operation_id,
                    )
                )

            if operation.risk in {RiskLevel.HIGH, RiskLevel.DESTRUCTIVE}:
                result.warnings.append(
                    ValidationIssue(
                        code="high_risk_operation",
                        message=f"Operation declares risk level {operation.risk}.",
                        operation_id=operation_id,
                    )
                )

        if not enabled:
            result.warnings.append(ValidationIssue(code="empty_plan", message="Plan has no enabled operations."))
        return result
