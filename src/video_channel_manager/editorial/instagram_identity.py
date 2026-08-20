from __future__ import annotations

from datetime import datetime

from video_channel_manager.editorial._project_profiles import PROJECT_KEYS
from video_channel_manager.exchange.instagram_identity import (
    InstagramAccountObservation,
    InstagramProjectBinding,
)


class InstagramIdentityBindingError(ValueError):
    pass


def build_instagram_project_binding(
    observation: InstagramAccountObservation,
    *,
    project_key: str,
    observation_sha256: str,
    approved_at: datetime,
    approved_by: str,
) -> InstagramProjectBinding:
    """Bind one exact provider-read observation to one canonical project after human review."""

    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        raise InstagramIdentityBindingError(f"unknown canonical project_key: {project_key!r}")

    reviewer = approved_by.strip()
    if not reviewer:
        raise InstagramIdentityBindingError("approved_by must not be empty")
    if approved_at.tzinfo is None or approved_at.utcoffset() is None:
        raise InstagramIdentityBindingError("approved_at must be timezone-aware")

    return InstagramProjectBinding(
        project_key=normalized_project,
        instagram_professional_account_id=observation.instagram_professional_account_id,
        observation_sha256=observation_sha256,
        username_observed=observation.username_observed,
        approved_at=approved_at,
        approved_by=reviewer,
    )
