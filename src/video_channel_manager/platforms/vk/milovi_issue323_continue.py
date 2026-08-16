from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    initialize_promotion_journal,
    load_promotion_journal,
    preflight_with_promotion_journal,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    promotion_observation_from_mapping,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import load_reviewed_promotion_spec
from video_channel_manager.platforms.vk.milovi_issue323_status_probe import run_issue_323_status_probe
from video_channel_manager.platforms.vk.milovi_rollout_sources import write_json_atomic

CONTINUE_PREVIEW_SCHEMA = "video-manager.milovi-issue-323-continue-preview"
CONTINUE_PREVIEW_VERSION = 1
PROMOTION_JOURNAL_INIT_CONFIRMATION = "INITIALIZE_REVIEWED_PROMOTION_JOURNAL"


def _blocked_payload(
    *,
    status_output_path: Path,
    status_payload: Mapping[str, Any],
    blocker: str,
    spec_digest: str | None = None,
    observation_digest: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": CONTINUE_PREVIEW_SCHEMA,
        "schema_version": CONTINUE_PREVIEW_VERSION,
        "continuation_status": "blocked",
        "provider_mutation_authorized": False,
        "provider_writes_executed": 0,
        "status_evidence_path": str(status_output_path),
        "status_probe_status": status_payload.get("status"),
        "promotion_spec_digest": spec_digest,
        "promotion_observation_digest": observation_digest,
        "promotion_journal_digest": None,
        "promotion_journal_initialized": False,
        "promotion_preflight": None,
        "promotion_preflight_digest": None,
        "blockers": [blocker],
    }


def run_issue_323_continue_preview(
    *,
    output_path: Path,
    status_output_path: Path,
    rollout_journal_path: Path,
    schedule_path: Path,
    prepared_manifest_path: Path,
    promotion_spec_path: Path,
    promotion_journal_path: Path,
    journal_init_confirmation: str | None = None,
    journal_created_at: str | None = None,
) -> dict[str, Any]:
    """Run one fresh read-only observation and build the exact continuation plan; never call a provider writer."""

    status_payload = run_issue_323_status_probe(
        output_path=status_output_path,
        journal_path=rollout_journal_path,
        schedule_path=schedule_path,
        prepared_manifest_path=prepared_manifest_path,
    )
    raw_observation = status_payload.get("promotion_observation")
    if not isinstance(raw_observation, Mapping):
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker="Status evidence lost typed promotion_observation",
        )
        write_json_atomic(output_path, payload)
        return payload

    try:
        observation = promotion_observation_from_mapping(raw_observation)
        spec = load_reviewed_promotion_spec(promotion_spec_path)
    except (OSError, ValueError) as exc:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=f"Reviewed promotion inputs are invalid: {exc}",
        )
        write_json_atomic(output_path, payload)
        return payload

    journal_initialized = False
    if promotion_journal_path.is_file():
        if journal_init_confirmation is not None:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker="Promotion journal already exists; initialization confirmation is not accepted for an existing journal",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
            )
            write_json_atomic(output_path, payload)
            return payload
        try:
            journal = load_promotion_journal(promotion_journal_path)
        except (OSError, ValueError) as exc:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=f"Promotion journal is invalid: {exc}",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
            )
            write_json_atomic(output_path, payload)
            return payload
    else:
        if journal_init_confirmation != PROMOTION_JOURNAL_INIT_CONFIRMATION:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=(
                    "Promotion journal is missing. Review the exact 12x2 PromotionSpec, then explicitly initialize "
                    f"with confirmation {PROMOTION_JOURNAL_INIT_CONFIRMATION!r}."
                ),
                spec_digest=spec.digest,
                observation_digest=observation.digest,
            )
            write_json_atomic(output_path, payload)
            return payload
        try:
            journal = initialize_promotion_journal(
                spec=spec,
                observation=observation,
                created_at=journal_created_at or datetime.now(UTC).isoformat(),
            )
        except ValueError as exc:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=f"Promotion journal initialization refused: {exc}",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
            )
            write_json_atomic(output_path, payload)
            return payload
        write_json_atomic(promotion_journal_path, journal.as_dict())
        journal_initialized = True

    try:
        preflight = preflight_with_promotion_journal(
            spec=spec,
            observation=observation,
            journal=journal,
        )
    except ValueError as exc:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=f"Promotion journal/spec binding is invalid: {exc}",
            spec_digest=spec.digest,
            observation_digest=observation.digest,
        )
        write_json_atomic(output_path, payload)
        return payload

    preflight_payload = preflight.as_dict()
    payload = {
        "schema_name": CONTINUE_PREVIEW_SCHEMA,
        "schema_version": CONTINUE_PREVIEW_VERSION,
        "continuation_status": "ready_for_digest_confirmation" if preflight.executable else "blocked",
        "provider_mutation_authorized": False,
        "provider_writes_executed": 0,
        "status_evidence_path": str(status_output_path),
        "status_probe_status": status_payload.get("status"),
        "promotion_spec_digest": spec.digest,
        "promotion_observation_digest": observation.digest,
        "promotion_journal_digest": journal.digest,
        "promotion_journal_initialized": journal_initialized,
        "promotion_preflight": preflight_payload,
        "promotion_preflight_digest": preflight.digest,
        "blockers": list(preflight.blockers),
    }
    write_json_atomic(output_path, payload)
    return payload


__all__ = [
    "CONTINUE_PREVIEW_SCHEMA",
    "CONTINUE_PREVIEW_VERSION",
    "PROMOTION_JOURNAL_INIT_CONFIRMATION",
    "run_issue_323_continue_preview",
]
