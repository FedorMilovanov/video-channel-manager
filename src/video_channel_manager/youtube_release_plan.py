from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from video_channel_manager.editorial import require_youtube_project_identity
from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    canonical_sha256,
    sha256_file,
    stable_upload_key,
    validate_intent,
    validate_sha256,
)

RELEASE_PLAN_SCHEMA = "video-manager.youtube-release-plan"
RELEASE_PLAN_VERSION = 1
EXECUTION_APPROVAL_SCHEMA = "video-manager.youtube-release-execution-approval"
EXECUTION_APPROVAL_VERSION = 1
ABSENCE_EVIDENCE_SCHEMA = "video-manager.youtube-existing-target-absence-evidence"
ABSENCE_EVIDENCE_VERSION = 1


def _digest_without(payload: dict[str, Any], field: str) -> str:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return canonical_sha256(unsigned)


def release_plan_digest(plan: dict[str, Any]) -> str:
    return _digest_without(plan, "release_plan_sha256")


def execution_approval_digest(approval: dict[str, Any]) -> str:
    return _digest_without(approval, "approval_sha256")


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise UploadPlanError(f"{field} is required.")
    return value.strip()


def _validate_local_file(path_value: object, digest_value: object, *, field: str) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise UploadPlanError(f"{field}_path is required.")
    expected = validate_sha256(digest_value, field=f"{field}_sha256")
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise UploadPlanError(f"{field} file not found: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise UploadPlanError(f"{field} SHA mismatch: expected {expected} actual {actual}")
    return path


def build_release_plan(
    intent: dict[str, Any],
    *,
    thumbnail_path: Path | None = None,
    playlist_ids: list[str] | None = None,
    final_privacy_status: str = "public",
    top_level_comment: str | None = None,
    manual_pin_evidence_required: bool = False,
) -> dict[str, Any]:
    validate_intent(intent)
    playlists = list(playlist_ids or [])
    if len(playlists) != len(set(playlists)) or any(not item.strip() for item in playlists):
        raise UploadPlanError("Release playlist IDs must be unique non-empty strings.")
    if final_privacy_status not in {"private", "unlisted", "public"}:
        raise UploadPlanError("final_privacy_status must be private, unlisted, or public.")
    if top_level_comment is not None and not top_level_comment.strip():
        raise UploadPlanError("top_level_comment cannot be blank when provided.")

    thumbnail: dict[str, Any] | None = None
    if thumbnail_path is not None:
        resolved_thumbnail = thumbnail_path.expanduser().resolve()
        if not resolved_thumbnail.is_file():
            raise UploadPlanError(f"Thumbnail file not found: {resolved_thumbnail}")
        suffix = resolved_thumbnail.suffix.casefold()
        mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in {".jpg", ".jpeg"} else None
        if mime is None:
            raise UploadPlanError("Thumbnail must be PNG or JPEG.")
        if resolved_thumbnail.stat().st_size > 2 * 1024 * 1024:
            raise UploadPlanError("Thumbnail exceeds YouTube's 2 MB upload limit.")
        thumbnail = {
            "path": str(resolved_thumbnail),
            "sha256": sha256_file(resolved_thumbnail),
            "size_bytes": resolved_thumbnail.stat().st_size,
            "mime_type": mime,
        }

    plan: dict[str, Any] = {
        "schema_name": RELEASE_PLAN_SCHEMA,
        "schema_version": RELEASE_PLAN_VERSION,
        "project_key": intent["project_key"],
        "account_alias": intent["account_alias"],
        "target_channel_id": intent["target_channel_id"],
        "upload_key_sha256": intent["upload_key_sha256"],
        "source_intent_sha256": intent["intent_sha256"],
        "media": {
            "path": intent["media_path"],
            "sha256": intent["media_sha256"],
            "size_bytes": intent["media_size_bytes"],
            "mime_type": intent["mime_type"],
        },
        "snippet": intent["snippet"],
        "initial_status": intent["status"],
        "thumbnail": thumbnail,
        "playlist_ids": playlists,
        "final_privacy_status": final_privacy_status,
        "top_level_comment": top_level_comment,
        "manual_pin_evidence_required": bool(manual_pin_evidence_required),
        "provider_write_authorized": False,
    }
    plan["release_plan_sha256"] = release_plan_digest(plan)
    validate_release_plan(plan)
    return plan


def validate_release_plan(plan: dict[str, Any], *, verify_files: bool = True) -> None:
    if plan.get("schema_name") != RELEASE_PLAN_SCHEMA or plan.get("schema_version") != RELEASE_PLAN_VERSION:
        raise UploadPlanError("Unsupported YouTube release-plan schema.")
    if plan.get("release_plan_sha256") != release_plan_digest(plan):
        raise UploadPlanError("Release plan SHA-256 does not match canonical content.")
    if plan.get("provider_write_authorized") is not False:
        raise UploadPlanError("Canonical release plans must remain provider_write_authorized=false.")
    project_key = _required_text(plan, "project_key")
    account_alias = _required_text(plan, "account_alias")
    channel_id = _required_text(plan, "target_channel_id")
    require_youtube_project_identity(project_key=project_key, account_alias=account_alias, channel_id=channel_id)

    media = plan.get("media")
    if not isinstance(media, dict):
        raise UploadPlanError("Release plan media object is required.")
    media_sha = validate_sha256(media.get("sha256"), field="Release media sha256")
    expected_key = stable_upload_key(
        project_key=project_key,
        target_channel_id=channel_id,
        media_sha256=media_sha,
    )
    if plan.get("upload_key_sha256") != expected_key:
        raise UploadPlanError("Release plan stable upload key does not match project/channel/media identity.")
    validate_sha256(plan.get("source_intent_sha256"), field="source_intent_sha256")
    size = media.get("size_bytes")
    if not isinstance(size, int) or size <= 0:
        raise UploadPlanError("Release media size_bytes must be positive.")
    if media.get("mime_type") != "video/mp4":
        raise UploadPlanError("Current guarded release transport supports video/mp4 only.")
    if verify_files:
        media_path = _validate_local_file(media.get("path"), media_sha, field="media")
        if media_path.stat().st_size != size:
            raise UploadPlanError("Release media size differs from immutable plan.")

    snippet = plan.get("snippet")
    status = plan.get("initial_status")
    if not isinstance(snippet, dict) or not str(snippet.get("title") or "").strip():
        raise UploadPlanError("Release snippet/title is required.")
    tags = snippet.get("tags")
    if not isinstance(tags, list) or not all(isinstance(item, str) and item.strip() for item in tags):
        raise UploadPlanError("Release tags must be non-empty strings.")
    if not isinstance(status, dict) or status.get("privacyStatus") != "private":
        raise UploadPlanError("Release initial_status must be private.")

    thumbnail = plan.get("thumbnail")
    if thumbnail is not None:
        if not isinstance(thumbnail, dict):
            raise UploadPlanError("Release thumbnail must be an object or null.")
        thumb_sha = validate_sha256(thumbnail.get("sha256"), field="thumbnail sha256")
        thumb_size = thumbnail.get("size_bytes")
        if not isinstance(thumb_size, int) or not 0 < thumb_size <= 2 * 1024 * 1024:
            raise UploadPlanError("Thumbnail size must be between 1 byte and 2 MB.")
        if thumbnail.get("mime_type") not in {"image/png", "image/jpeg"}:
            raise UploadPlanError("Thumbnail MIME type must be image/png or image/jpeg.")
        if verify_files:
            thumb_path = _validate_local_file(thumbnail.get("path"), thumb_sha, field="thumbnail")
            if thumb_path.stat().st_size != thumb_size:
                raise UploadPlanError("Thumbnail size differs from immutable plan.")

    playlists = plan.get("playlist_ids")
    if not isinstance(playlists, list) or not all(isinstance(item, str) and item.strip() for item in playlists):
        raise UploadPlanError("Release playlist_ids must be a list of non-empty strings.")
    if len(playlists) != len(set(playlists)):
        raise UploadPlanError("Release playlist IDs must be unique.")
    if plan.get("final_privacy_status") not in {"private", "unlisted", "public"}:
        raise UploadPlanError("Release final_privacy_status is invalid.")
    comment = plan.get("top_level_comment")
    if comment is not None and (not isinstance(comment, str) or not comment.strip()):
        raise UploadPlanError("Release top_level_comment must be non-empty or null.")
    if not isinstance(plan.get("manual_pin_evidence_required"), bool):
        raise UploadPlanError("manual_pin_evidence_required must be boolean.")


def validate_absence_evidence(evidence: dict[str, Any], *, plan: dict[str, Any]) -> str:
    validate_release_plan(plan, verify_files=False)
    if evidence.get("schema_name") != ABSENCE_EVIDENCE_SCHEMA or evidence.get("schema_version") != ABSENCE_EVIDENCE_VERSION:
        raise UploadPlanError("Unsupported existing-target absence evidence schema.")
    expected = {
        "project_key": plan["project_key"],
        "account_alias": plan["account_alias"],
        "target_channel_id": plan["target_channel_id"],
        "upload_key_sha256": plan["upload_key_sha256"],
        "media_sha256": plan["media"]["sha256"],
    }
    for field, value in expected.items():
        if evidence.get(field) != value:
            raise UploadPlanError(f"Existing-target absence evidence {field} does not match release plan.")
    if evidence.get("provider_effect") != "confirmed_absent":
        raise UploadPlanError("Existing-target evidence must explicitly prove provider_effect=confirmed_absent.")
    if evidence.get("provider_writes_performed") != 0:
        raise UploadPlanError("Existing-target absence evidence must be provider-read-only.")
    _required_text(evidence, "reviewed_by")
    _required_text(evidence, "reviewed_at")
    return canonical_sha256(evidence)


def validate_execution_approval(
    approval: dict[str, Any],
    *,
    plan: dict[str, Any],
    child_id: str,
    absence_evidence_sha256: str | None = None,
) -> None:
    validate_release_plan(plan, verify_files=False)
    if approval.get("schema_name") != EXECUTION_APPROVAL_SCHEMA or approval.get("schema_version") != EXECUTION_APPROVAL_VERSION:
        raise UploadPlanError("Unsupported YouTube execution approval schema.")
    if approval.get("approval_sha256") != execution_approval_digest(approval):
        raise UploadPlanError("YouTube execution approval SHA-256 does not match canonical content.")
    if approval.get("provider_writes_authorized") is not True:
        raise UploadPlanError("Execution approval does not authorize provider writes.")
    expected = {
        "release_plan_sha256": plan["release_plan_sha256"],
        "project_key": plan["project_key"],
        "account_alias": plan["account_alias"],
        "target_channel_id": plan["target_channel_id"],
        "upload_key_sha256": plan["upload_key_sha256"],
    }
    for field, value in expected.items():
        if approval.get(field) != value:
            raise UploadPlanError(f"Execution approval {field} does not match release plan.")
    approved = approval.get("approved_child_ids")
    if not isinstance(approved, list) or child_id not in approved:
        raise UploadPlanError(f"Execution approval does not authorize release child {child_id}.")
    if not all(isinstance(item, str) and item for item in approved):
        raise UploadPlanError("Execution approval approved_child_ids is invalid.")
    _required_text(approval, "approval_id")
    _required_text(approval, "reviewed_by")
    _required_text(approval, "reviewed_at")
    bound_absence = approval.get("existing_target_absence_evidence_sha256")
    if absence_evidence_sha256 is not None and bound_absence != absence_evidence_sha256:
        raise UploadPlanError("Execution approval does not bind the exact existing-target absence evidence.")


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadPlanError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UploadPlanError(f"Expected JSON object: {path}")
    return payload
