from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, Literal

from video_channel_manager.youtube_upload_plan import UploadPlanError, canonical_sha256

RELEASE_SCHEMA = "video-manager.youtube-release-state"
RELEASE_VERSION = 1
ProviderEffect = Literal["not_dispatched", "confirmed_absent", "may_exist", "verified"]

_FIXED_CHILDREN: tuple[tuple[str, str], ...] = (
    ("existing-target", "existing_target_reconciliation"),
    ("upload", "upload"),
    ("processing-private", "processing_private_readback"),
    ("metadata-description", "metadata_description"),
    ("thumbnail", "thumbnail"),
)
_TAIL_CHILDREN: tuple[tuple[str, str], ...] = (
    ("visibility-publication", "visibility_publication"),
    ("top-level-comment", "top_level_comment"),
    ("manual-pin-evidence", "manual_pin_evidence"),
)
_EFFECTS = frozenset({"not_dispatched", "confirmed_absent", "may_exist", "verified"})
_TERMINAL_PROOF_EFFECTS = frozenset({"confirmed_absent", "verified"})


class YouTubeReleaseStateError(UploadPlanError):
    pass


def _now(value: str | None = None) -> str:
    return value or datetime.now(UTC).isoformat()


def _child(child_id: str, kind: str, *, target_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "child_id": child_id,
        "kind": kind,
        "provider_effect": "not_dispatched",
        "payload_sha256": None,
        "remote_id": None,
        "evidence_sha256": None,
        "updated_at": None,
    }
    if target_id is not None:
        payload["target_id"] = target_id
    return payload


def build_release_state(
    *,
    upload_key_sha256: str,
    playlist_ids: list[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    playlists = playlist_ids or []
    if len(playlists) != len(set(playlists)):
        raise YouTubeReleaseStateError("Playlist IDs in one release state must be unique.")
    if any(not isinstance(item, str) or not item.strip() for item in playlists):
        raise YouTubeReleaseStateError("Playlist IDs must be non-empty strings.")

    children = [_child(child_id, kind) for child_id, kind in _FIXED_CHILDREN]
    children.extend(
        _child(
            f"playlist:{playlist_id}",
            "playlist_membership",
            target_id=playlist_id,
        )
        for playlist_id in playlists
    )
    children.extend(_child(child_id, kind) for child_id, kind in _TAIL_CHILDREN)
    state = {
        "schema_name": RELEASE_SCHEMA,
        "schema_version": RELEASE_VERSION,
        "upload_key_sha256": upload_key_sha256,
        "created_at": _now(now),
        "updated_at": _now(now),
        "release_plan_sha256": None,
        "children": children,
    }
    validate_release_state(state)
    return state


def validate_release_state(state: dict[str, Any]) -> None:
    if state.get("schema_name") != RELEASE_SCHEMA or state.get("schema_version") != RELEASE_VERSION:
        raise YouTubeReleaseStateError("Unsupported YouTube release-state schema.")
    upload_key = state.get("upload_key_sha256")
    if not isinstance(upload_key, str) or not upload_key.startswith("sha256:") or len(upload_key) != 71:
        raise YouTubeReleaseStateError("Release state upload_key_sha256 is invalid.")
    children = state.get("children")
    if not isinstance(children, list) or not children:
        raise YouTubeReleaseStateError("Release state must contain ordered child operations.")
    if len(children) < len(_FIXED_CHILDREN) + len(_TAIL_CHILDREN):
        raise YouTubeReleaseStateError("Release state is missing required child operations.")

    child_ids: list[str] = []
    child_pairs: list[tuple[str, str]] = []
    for item in children:
        if not isinstance(item, dict):
            raise YouTubeReleaseStateError("Release child must be an object.")
        child_id = item.get("child_id")
        kind = item.get("kind")
        effect = item.get("provider_effect")
        if not isinstance(child_id, str) or not child_id:
            raise YouTubeReleaseStateError("Release child_id is required.")
        if not isinstance(kind, str) or not kind:
            raise YouTubeReleaseStateError(f"Release child {child_id} kind is required.")
        if effect not in _EFFECTS:
            raise YouTubeReleaseStateError(f"Release child {child_id} has invalid provider_effect={effect}.")
        for digest_field in ("payload_sha256", "evidence_sha256"):
            digest = item.get(digest_field)
            if digest is not None and (
                not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71
            ):
                raise YouTubeReleaseStateError(f"Release child {child_id} {digest_field} is invalid.")
        if effect != "not_dispatched" and item.get("payload_sha256") is None:
            raise YouTubeReleaseStateError(
                f"Release child {child_id} has provider effect {effect} without an immutable payload digest."
            )
        if effect in _TERMINAL_PROOF_EFFECTS and item.get("evidence_sha256") is None:
            raise YouTubeReleaseStateError(
                f"Release child {child_id} has terminal provider effect {effect} without immutable proof evidence."
            )
        remote_id = item.get("remote_id")
        if remote_id is not None and (not isinstance(remote_id, str) or not remote_id):
            raise YouTubeReleaseStateError(f"Release child {child_id} remote_id is invalid.")
        child_ids.append(child_id)
        child_pairs.append((child_id, kind))

    if len(child_ids) != len(set(child_ids)):
        raise YouTubeReleaseStateError("Release child IDs must be unique.")
    if child_pairs[: len(_FIXED_CHILDREN)] != list(_FIXED_CHILDREN):
        raise YouTubeReleaseStateError("Release state fixed child identity/kind order is invalid.")
    if child_pairs[-len(_TAIL_CHILDREN) :] != list(_TAIL_CHILDREN):
        raise YouTubeReleaseStateError("Release state tail child identity/kind order is invalid.")

    middle = children[len(_FIXED_CHILDREN) : len(children) - len(_TAIL_CHILDREN)]
    for item in middle:
        child_id = str(item["child_id"])
        if item["kind"] != "playlist_membership" or not child_id.startswith("playlist:"):
            raise YouTubeReleaseStateError(
                "Release state middle children must be exact playlist membership operations."
            )
        playlist_id = child_id.removeprefix("playlist:")
        if not playlist_id or item.get("target_id") != playlist_id:
            raise YouTubeReleaseStateError(
                f"Release playlist child {child_id} must bind target_id to its exact playlist ID."
            )


def _index(state: dict[str, Any], child_id: str) -> int:
    for index, child in enumerate(state["children"]):
        if child["child_id"] == child_id:
            return index
    raise YouTubeReleaseStateError(f"Unknown release child: {child_id}")


def _prerequisite_satisfied(child: dict[str, Any]) -> bool:
    if child["provider_effect"] == "verified":
        return True
    return bool(child["kind"] == "existing_target_reconciliation" and child["provider_effect"] == "confirmed_absent")


def _require_prerequisites(state: dict[str, Any], index: int) -> None:
    for prior in state["children"][:index]:
        if not _prerequisite_satisfied(prior):
            raise YouTubeReleaseStateError(
                f"Release child {state['children'][index]['child_id']} is blocked by "
                f"{prior['child_id']} provider_effect={prior['provider_effect']}."
            )


def prepare_child(
    state: dict[str, Any],
    *,
    child_id: str,
    payload: object,
    now: str | None = None,
) -> dict[str, Any]:
    validate_release_state(state)
    index = _index(state, child_id)
    _require_prerequisites(state, index)
    updated = copy.deepcopy(state)
    child = updated["children"][index]
    digest = canonical_sha256(payload)
    current_digest = child.get("payload_sha256")
    if current_digest not in (None, digest):
        raise YouTubeReleaseStateError(f"Release child {child_id} already has a different immutable payload digest.")
    if child["provider_effect"] != "not_dispatched" and current_digest is None:
        raise YouTubeReleaseStateError(f"Release child {child_id} cannot be prepared after provider effect exists.")
    child["payload_sha256"] = digest
    child["updated_at"] = _now(now)
    updated["updated_at"] = _now(now)
    return updated


def transition_child(
    state: dict[str, Any],
    *,
    child_id: str,
    provider_effect: ProviderEffect,
    remote_id: str | None = None,
    evidence: object | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    validate_release_state(state)
    if provider_effect not in _EFFECTS:
        raise YouTubeReleaseStateError(f"Invalid provider effect: {provider_effect}")
    index = _index(state, child_id)
    _require_prerequisites(state, index)
    updated = copy.deepcopy(state)
    child = updated["children"][index]
    current = child["provider_effect"]
    allowed = {
        "not_dispatched": {"not_dispatched", "confirmed_absent", "may_exist", "verified"},
        "confirmed_absent": {"confirmed_absent", "may_exist", "verified"},
        "may_exist": {"may_exist", "confirmed_absent", "verified"},
        "verified": {"verified"},
    }[current]
    if provider_effect not in allowed:
        raise YouTubeReleaseStateError(f"Invalid release transition for {child_id}: {current} -> {provider_effect}.")
    if provider_effect != "not_dispatched" and child.get("payload_sha256") is None:
        raise YouTubeReleaseStateError(
            f"Release child {child_id} must persist its immutable payload before provider effect {provider_effect}."
        )
    if provider_effect in _TERMINAL_PROOF_EFFECTS and evidence is None:
        raise YouTubeReleaseStateError(
            f"Release child {child_id} must persist immutable proof evidence before provider effect {provider_effect}."
        )
    if current == "verified":
        if remote_id is not None and child.get("remote_id") not in (None, remote_id):
            raise YouTubeReleaseStateError(f"Verified release child {child_id} remote_id is immutable.")
        if evidence is not None:
            new_evidence = canonical_sha256(evidence)
            if child.get("evidence_sha256") not in (None, new_evidence):
                raise YouTubeReleaseStateError(f"Verified release child {child_id} evidence is immutable.")

    child["provider_effect"] = provider_effect
    if remote_id is not None:
        child["remote_id"] = remote_id
    if evidence is not None:
        child["evidence_sha256"] = canonical_sha256(evidence)
    child["updated_at"] = _now(now)
    updated["updated_at"] = _now(now)
    validate_release_state(updated)
    return updated


def next_release_child(state: dict[str, Any]) -> dict[str, Any] | None:
    validate_release_state(state)
    for child in state["children"]:
        if child["provider_effect"] == "may_exist":
            raise YouTubeReleaseStateError(
                f"Release is blocked by unresolved provider effect for {child['child_id']}; reconcile read-only first."
            )
    for child in state["children"]:
        if _prerequisite_satisfied(child):
            continue
        result: dict[str, Any] = copy.deepcopy(child)
        return result
    return None


def mark_existing_target_adopted(
    state: dict[str, Any],
    *,
    video_id: str,
    remote_revision: str,
    evidence: object,
    now: str | None = None,
) -> dict[str, Any]:
    payload = {"video_id": video_id, "remote_revision": remote_revision, "mode": "read_only_adoption"}
    updated = prepare_child(state, child_id="existing-target", payload=payload, now=now)
    updated = transition_child(
        updated,
        child_id="existing-target",
        provider_effect="verified",
        remote_id=video_id,
        evidence=evidence,
        now=now,
    )
    upload_payload = {"video_id": video_id, "mode": "adopted_existing_no_upload"}
    updated = prepare_child(updated, child_id="upload", payload=upload_payload, now=now)
    return transition_child(
        updated,
        child_id="upload",
        provider_effect="verified",
        remote_id=video_id,
        evidence={"adopted_existing_target": True, "remote_revision": remote_revision},
        now=now,
    )
