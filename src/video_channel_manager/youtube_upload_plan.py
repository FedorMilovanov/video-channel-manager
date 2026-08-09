from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.editorial import require_youtube_project_identity

SPEC_SCHEMA = "video-manager.youtube-video-upload-spec"
SPEC_VERSION = "2.0"
INTENT_SCHEMA = "video-manager.youtube-video-upload-intent"
INTENT_VERSION = "2.0"
JOURNAL_SCHEMA = "video-manager.youtube-video-upload-journal"
JOURNAL_VERSION = "2.0"
LIVE_STATE_EVIDENCE_SCHEMA = "video-manager.youtube-live-state-evidence"


class UploadPlanError(RuntimeError):
    pass


def canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _validate_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise UploadPlanError(f"{field} is invalid.")
    try:
        int(value.removeprefix("sha256:"), 16)
    except ValueError as exc:
        raise UploadPlanError(f"{field} is invalid.") from exc
    return value


def stable_upload_key(*, project_key: str, target_channel_id: str, media_sha256: str) -> str:
    return canonical_sha256(
        {
            "media_sha256": media_sha256,
            "project_key": project_key,
            "target_channel_id": target_channel_id,
        }
    )


def journal_path(data_dir: Path, upload_key_sha256: str) -> Path:
    key = upload_key_sha256.removeprefix("sha256:")
    return data_dir.expanduser().resolve() / "youtube" / "upload-keys" / f"{key}.json"


def validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("schema_name") != SPEC_SCHEMA or spec.get("schema_version") != SPEC_VERSION:
        raise UploadPlanError("Unsupported upload spec schema; rebuild it with the current v2 format.")
    project_key = spec.get("project_key")
    account_alias = spec.get("account_alias")
    target_channel_id = spec.get("target_channel_id")
    media_sha = spec.get("expected_media_sha256")
    if not isinstance(project_key, str) or not project_key:
        raise UploadPlanError("Spec project_key is required.")
    if not isinstance(account_alias, str) or not account_alias:
        raise UploadPlanError("Spec account_alias is required.")
    if not isinstance(target_channel_id, str) or not target_channel_id.startswith("UC"):
        raise UploadPlanError("Spec target_channel_id is invalid.")
    _validate_sha256(media_sha, field="Spec expected_media_sha256")
    if spec.get("privacy_status") != "private":
        raise UploadPlanError("Guarded first-upload planning is private-only.")
    if not isinstance(spec.get("title"), str) or not str(spec["title"]).strip():
        raise UploadPlanError("Spec title is blank.")
    if not isinstance(spec.get("description"), str):
        raise UploadPlanError("Spec description must be a string.")
    tags = spec.get("tags")
    if not isinstance(tags, list) or not all(isinstance(item, str) and item.strip() for item in tags):
        raise UploadPlanError("Spec tags must contain non-empty strings.")


def intent_digest(intent: dict[str, Any]) -> str:
    unsigned = dict(intent)
    unsigned.pop("intent_sha256", None)
    return canonical_sha256(unsigned)


def build_intent(
    spec: dict[str, Any],
    media: Path,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_spec(spec)
    project_key = str(spec["project_key"])
    account_alias = str(spec["account_alias"])
    target_channel_id = str(spec["target_channel_id"])
    require_youtube_project_identity(
        project_key=project_key,
        account_alias=account_alias,
        channel_id=target_channel_id,
    )

    resolved = media.expanduser().resolve()
    if not resolved.is_file():
        raise UploadPlanError(f"Media file not found: {resolved}")
    media_sha = sha256_file(resolved)
    if media_sha != spec["expected_media_sha256"]:
        raise UploadPlanError(f"Media SHA mismatch: expected {spec['expected_media_sha256']} actual {media_sha}")
    upload_key = stable_upload_key(
        project_key=project_key,
        target_channel_id=target_channel_id,
        media_sha256=media_sha,
    )
    intent: dict[str, Any] = {
        "schema_name": INTENT_SCHEMA,
        "schema_version": INTENT_VERSION,
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "project_key": project_key,
        "account_alias": account_alias,
        "target_channel_id": target_channel_id,
        "upload_key_sha256": upload_key,
        "media_path": str(resolved),
        "media_sha256": media_sha,
        "media_size_bytes": resolved.stat().st_size,
        "mime_type": "video/mp4",
        "snippet": {
            "title": spec["title"],
            "description": spec["description"],
            "tags": list(spec["tags"]),
            "categoryId": str(spec.get("category_id", "10")),
            "defaultLanguage": str(spec.get("default_language", "ru")),
        },
        "status": {
            "privacyStatus": "private",
            "embeddable": bool(spec.get("embeddable", True)),
            "license": str(spec.get("license", "youtube")),
            "selfDeclaredMadeForKids": bool(spec.get("self_declared_made_for_kids", False)),
            "containsSyntheticMedia": bool(spec.get("contains_synthetic_media", True)),
        },
        "notify_subscribers": False,
        "provider_write_authorized": False,
        "provider_effect": "not_dispatched",
    }
    intent["intent_sha256"] = intent_digest(intent)
    return intent


def validate_intent(intent: dict[str, Any]) -> None:
    if intent.get("schema_name") != INTENT_SCHEMA or intent.get("schema_version") != INTENT_VERSION:
        raise UploadPlanError("Unsupported upload intent schema; rebuild it from current code.")
    if intent.get("intent_sha256") != intent_digest(intent):
        raise UploadPlanError("Upload intent SHA-256 does not match canonical content.")
    project_key = str(intent.get("project_key") or "")
    account_alias = str(intent.get("account_alias") or "")
    target_channel_id = str(intent.get("target_channel_id") or "")
    media_sha = _validate_sha256(intent.get("media_sha256"), field="Intent media_sha256")
    expected_key = stable_upload_key(
        project_key=project_key,
        target_channel_id=target_channel_id,
        media_sha256=media_sha,
    )
    if intent.get("upload_key_sha256") != expected_key:
        raise UploadPlanError("Upload stable key does not match project/channel/media identity.")
    require_youtube_project_identity(
        project_key=project_key,
        account_alias=account_alias,
        channel_id=target_channel_id,
    )
    if intent.get("provider_write_authorized") is not False:
        raise UploadPlanError("Current v2 upload intents must remain provider_write_authorized=false.")


def planned_journal(intent: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    validate_intent(intent)
    return {
        "schema_name": JOURNAL_SCHEMA,
        "schema_version": JOURNAL_VERSION,
        "updated_at": now or datetime.now(UTC).isoformat(),
        "project_key": intent["project_key"],
        "account_alias": intent["account_alias"],
        "target_channel_id": intent["target_channel_id"],
        "media_sha256": intent["media_sha256"],
        "upload_key_sha256": intent["upload_key_sha256"],
        "active_intent_sha256": intent["intent_sha256"],
        "state": "planned",
        "provider_effect": "not_dispatched",
    }


def _validate_journal_identity(
    journal: dict[str, Any],
    *,
    project_key: str,
    account_alias: str,
    target_channel_id: str,
    media_sha256: str,
    upload_key_sha256: str,
) -> None:
    if journal.get("schema_name") != JOURNAL_SCHEMA or journal.get("schema_version") != JOURNAL_VERSION:
        raise UploadPlanError("Unsupported upload journal schema; do not bypass it.")
    expected = {
        "project_key": project_key,
        "account_alias": account_alias,
        "target_channel_id": target_channel_id,
        "media_sha256": media_sha256,
        "upload_key_sha256": upload_key_sha256,
    }
    for field, value in expected.items():
        if journal.get(field) != value:
            raise UploadPlanError(f"Upload journal {field} does not match the stable upload identity.")


def validate_journal(journal: dict[str, Any], *, intent: dict[str, Any]) -> None:
    validate_intent(intent)
    _validate_journal_identity(
        journal,
        project_key=str(intent["project_key"]),
        account_alias=str(intent["account_alias"]),
        target_channel_id=str(intent["target_channel_id"]),
        media_sha256=str(intent["media_sha256"]),
        upload_key_sha256=str(intent["upload_key_sha256"]),
    )


def require_new_plan_allowed(journal: dict[str, Any] | None, *, intent: dict[str, Any]) -> None:
    if journal is None:
        return
    validate_journal(journal, intent=intent)
    if journal.get("provider_effect") == "confirmed_absent" and journal.get("state") == "abandoned":
        return
    raise UploadPlanError(
        "Existing stable upload journal blocks a new plan for the same project/channel/media: "
        f"state={journal.get('state')} provider_effect={journal.get('provider_effect')}."
    )


def abandon_planned_journal(
    journal: dict[str, Any],
    *,
    intent: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    validate_journal(journal, intent=intent)
    if journal.get("state") != "planned" or journal.get("provider_effect") != "not_dispatched":
        raise UploadPlanError("Only an undispatched planned intent can be abandoned locally.")
    if journal.get("active_intent_sha256") != intent["intent_sha256"]:
        raise UploadPlanError("Journal active intent differs; refusing to abandon another attempt.")
    updated = dict(journal)
    updated["updated_at"] = now or datetime.now(UTC).isoformat()
    updated["state"] = "abandoned"
    updated["provider_effect"] = "confirmed_absent"
    return updated


def validate_live_state_evidence(evidence: dict[str, Any]) -> dict[str, str]:
    if evidence.get("schema_name") != LIVE_STATE_EVIDENCE_SCHEMA or evidence.get("schema_version") != 1:
        raise UploadPlanError("Unsupported YouTube live-state evidence schema.")
    if evidence.get("execution_authority") is not False or evidence.get("provider_writes_authorized") is not False:
        raise UploadPlanError("Live-state evidence must be non-authorizing.")

    project_key = str(evidence.get("project_key") or "").strip()
    account_alias = str(evidence.get("account_alias") or "").strip()
    target_channel_id = str(evidence.get("channel_id") or "").strip()
    video = evidence.get("video")
    if not isinstance(video, dict):
        raise UploadPlanError("Live-state evidence video object is required.")
    video_id = str(video.get("video_id") or "").strip()
    media_sha = _validate_sha256(video.get("uploaded_media_sha256"), field="Live-state uploaded_media_sha256")
    if not video_id:
        raise UploadPlanError("Live-state video_id is required.")
    require_youtube_project_identity(
        project_key=project_key,
        account_alias=account_alias,
        channel_id=target_channel_id,
    )
    return {
        "project_key": project_key,
        "account_alias": account_alias,
        "target_channel_id": target_channel_id,
        "video_id": video_id,
        "media_sha256": media_sha,
        "upload_key_sha256": stable_upload_key(
            project_key=project_key,
            target_channel_id=target_channel_id,
            media_sha256=media_sha,
        ),
    }


def adopted_journal(
    evidence: dict[str, Any],
    *,
    remote_video_id: str,
    remote_channel_id: str,
    remote_revision: str,
    now: str | None = None,
) -> dict[str, Any]:
    identity = validate_live_state_evidence(evidence)
    if remote_video_id != identity["video_id"]:
        raise UploadPlanError(
            f"Provider video mismatch: evidence={identity['video_id']} provider={remote_video_id}."
        )
    if remote_channel_id != identity["target_channel_id"]:
        raise UploadPlanError(
            "Provider channel does not match the canonical target in the live-state evidence."
        )
    _validate_sha256(remote_revision, field="Provider remote revision")
    return {
        "schema_name": JOURNAL_SCHEMA,
        "schema_version": JOURNAL_VERSION,
        "updated_at": now or datetime.now(UTC).isoformat(),
        "project_key": identity["project_key"],
        "account_alias": identity["account_alias"],
        "target_channel_id": identity["target_channel_id"],
        "media_sha256": identity["media_sha256"],
        "upload_key_sha256": identity["upload_key_sha256"],
        "active_intent_sha256": None,
        "state": "verified",
        "provider_effect": "verified",
        "adopted_existing_target": True,
        "remote_video_id": remote_video_id,
        "remote_revision": remote_revision,
        "adoption_evidence_sha256": canonical_sha256(evidence),
    }


def require_adoption_allowed(
    current: dict[str, Any] | None,
    *,
    proposed: dict[str, Any],
) -> bool:
    """Return True for first adoption; False only for byte-for-byte-equivalent durable adoption identity."""

    _validate_journal_identity(
        proposed,
        project_key=str(proposed["project_key"]),
        account_alias=str(proposed["account_alias"]),
        target_channel_id=str(proposed["target_channel_id"]),
        media_sha256=str(proposed["media_sha256"]),
        upload_key_sha256=str(proposed["upload_key_sha256"]),
    )
    if current is None:
        return True
    _validate_journal_identity(
        current,
        project_key=str(proposed["project_key"]),
        account_alias=str(proposed["account_alias"]),
        target_channel_id=str(proposed["target_channel_id"]),
        media_sha256=str(proposed["media_sha256"]),
        upload_key_sha256=str(proposed["upload_key_sha256"]),
    )
    if (
        current.get("state") == "verified"
        and current.get("provider_effect") == "verified"
        and current.get("adopted_existing_target") is True
        and current.get("remote_video_id") == proposed.get("remote_video_id")
        and current.get("remote_revision") == proposed.get("remote_revision")
        and current.get("adoption_evidence_sha256") == proposed.get("adoption_evidence_sha256")
    ):
        return False
    raise UploadPlanError(
        "Existing stable upload journal conflicts with existing-target adoption: "
        f"state={current.get('state')} provider_effect={current.get('provider_effect')} "
        f"remote_video_id={current.get('remote_video_id')}. "
        "Remote revision, evidence, or canonical account drift requires explicit read-only reconciliation."
    )
