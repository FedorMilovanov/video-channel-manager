"""Provider-inert Clip readiness helper retained for Issue #323 read models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from video_channel_manager.platforms.vk.upload_lifecycle import (
    VkUploadReadiness,
    VkUploadReadinessAssessment,
    assess_vk_upload_readiness,
)


def _native_clip_assessment(
    item: Mapping[str, Any],
    *,
    expected_owner_id: int,
    expected_video_id: int,
    readiness: VkUploadReadiness,
) -> VkUploadReadinessAssessment:
    """Accept the narrow VK processing/blank-title projection only when material Clip invariants hold."""

    assessment = assess_vk_upload_readiness(
        item,
        expected_owner_id=expected_owner_id,
        expected_video_id=expected_video_id,
        readiness=readiness,
    )
    if assessment.ready:
        return assessment

    reasons = set(assessment.reasons)
    observed = dict(assessment.observed)
    if not reasons or not reasons.issubset({"processing", "title_mismatch"}):
        return assessment
    if observed.get("owner_id") != expected_owner_id or observed.get("video_id") != expected_video_id:
        return assessment
    if observed.get("type") != "short_video":
        return assessment
    if bool(observed.get("converting")):
        return assessment
    if not bool(observed.get("playable")):
        return assessment
    duration = observed.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < readiness.minimum_duration_seconds:
        return assessment
    if "title_mismatch" in reasons and str(observed.get("title") or "") != "":
        return assessment

    observed["readiness_mode"] = "playable_native_short_video"
    observed["provider_processing_flag_tolerated"] = "processing" in reasons
    observed["blank_clip_title_tolerated"] = "title_mismatch" in reasons
    return VkUploadReadinessAssessment(ready=True, reasons=(), observed=observed)


__all__ = ["_native_clip_assessment"]
