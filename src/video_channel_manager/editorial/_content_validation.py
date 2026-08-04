from __future__ import annotations

from typing import Any

from video_channel_manager.editorial._content_validation_evidence import validate_evidence
from video_channel_manager.editorial._content_validation_identity import validate_identity
from video_channel_manager.editorial._content_validation_links import validate_links
from video_channel_manager.editorial._content_validation_support import _validate_platform_metadata


def validate_content_record(
    payload: dict[str, Any],
    *,
    expected_channel_id: str | None = None,
    expected_project_key: str | None = None,
) -> list[str]:
    errors, schema_is_canonical = validate_identity(
        payload,
        expected_channel_id=expected_channel_id,
        expected_project_key=expected_project_key,
    )
    evidence_errors, source_urls = validate_evidence(payload)
    errors.extend(evidence_errors)
    errors.extend(validate_links(payload, source_urls=source_urls))
    errors.extend(_validate_platform_metadata(payload, schema_is_canonical=schema_is_canonical))
    return errors


__all__ = ["validate_content_record"]
