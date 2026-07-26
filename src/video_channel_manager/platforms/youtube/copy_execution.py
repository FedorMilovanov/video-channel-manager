from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from video_channel_manager.platforms.youtube.writer import (
    YouTubeRevisionConflictError,
    descriptions_equivalent,
)


@dataclass(frozen=True)
class CopyPreflight:
    prepared: list[dict[str, Any]]
    already_applied: int
    revision_drift_tolerated: int


def required_text(operation: dict[str, Any], field: str) -> str:
    value = operation.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Copy-fix operation is missing required string field: {field}")
    return value


def preflight_copy_operations(
    operations: list[dict[str, Any]],
    *,
    confirm_channel: str,
    writer: Any,
) -> CopyPreflight:
    """Classify every operation by live description state.

    Full-record revisions are diagnostic only. YouTube can refresh etags and
    other server-managed fields while the description remains unchanged. A
    mutation is allowed only when the live description canonically matches the
    plan's before-state; a live after-state is idempotently counted as already
    applied. Any third state is a hard conflict.
    """

    prepared: list[dict[str, Any]] = []
    already_applied = 0
    revision_drift_tolerated = 0

    for operation in operations:
        video_id = required_text(operation, "video_id")
        channel_id = required_text(operation, "channel_id")
        expected_revision = required_text(operation, "expected_revision")
        before = required_text(operation, "before_description")
        after = required_text(operation, "after_description")

        if channel_id != confirm_channel:
            raise ValueError(
                f"Plan operation {video_id} targets {channel_id}, not confirmed channel {confirm_channel}."
            )

        current = writer.read_description(video_id)
        if current.channel_id != confirm_channel:
            raise YouTubeRevisionConflictError(
                f"Live video {video_id} belongs to {current.channel_id}, not {confirm_channel}."
            )

        if descriptions_equivalent(current.description, after):
            already_applied += 1
            continue

        if not descriptions_equivalent(current.description, before):
            raise YouTubeRevisionConflictError(
                f"Live video {video_id} matches neither the plan before-state nor after-state; "
                "refusing to overwrite a manual or concurrent edit."
            )

        if current.revision != expected_revision:
            revision_drift_tolerated += 1

        prepared.append(
            {
                "video_id": video_id,
                "channel_id": channel_id,
                "title": current.title,
                "expected_revision": expected_revision,
                "live_revision": current.revision,
                "revision_drift": current.revision != expected_revision,
                "before_description": before,
                "after_description": after,
            }
        )

    return CopyPreflight(
        prepared=prepared,
        already_applied=already_applied,
        revision_drift_tolerated=revision_drift_tolerated,
    )


def verify_copy_operations(
    operations: list[dict[str, Any]],
    *,
    confirm_channel: str,
    writer: Any,
) -> list[dict[str, str]]:
    """Re-read the whole batch after mutation and return any mismatches."""

    failures: list[dict[str, str]] = []
    for operation in operations:
        video_id = str(operation["video_id"])
        current = writer.read_description(video_id)
        if current.channel_id != confirm_channel:
            failures.append(
                {
                    "video_id": video_id,
                    "reason": f"channel changed to {current.channel_id}",
                }
            )
            continue
        if not descriptions_equivalent(current.description, str(operation["after_description"])):
            failures.append(
                {
                    "video_id": video_id,
                    "reason": "live description does not match the planned after-state",
                }
            )
    return failures
