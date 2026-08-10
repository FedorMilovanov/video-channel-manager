from __future__ import annotations

import argparse
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from video_channel_manager.youtube_provider_semantics import (
    classify_boolean_readback,
    tags_equivalent,
)
from video_channel_manager.youtube_release_operations import (
    persist_release,
    release_from_journal,
    video_id_from_release,
)
from video_channel_manager.youtube_release_plan import (
    load_json_object,
    validate_execution_approval,
    validate_release_plan,
)
from video_channel_manager.youtube_release_provider import (
    ReleaseProviderResult,
    YouTubeReleaseProvider,
)
from video_channel_manager.youtube_release_state import (
    ProviderEffect,
    child_by_id,
    next_release_child,
    prepare_child,
    transition_child,
)
from video_channel_manager.youtube_stable_state import read_json, stable_key_mutation_lock
from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    canonical_sha256,
    journal_path,
)


class ReleaseProvider(Protocol):
    def close(self) -> None: ...

    def read_video(self, video_id: str) -> dict[str, Any]: ...

    def playlist_contains_video(self, playlist_id: str, video_id: str) -> bool: ...

    def start_upload_session(
        self,
        *,
        snippet: dict[str, Any],
        status: dict[str, Any],
        media_size_bytes: int,
        media_mime_type: str,
    ) -> ReleaseProviderResult: ...

    def upload_media(
        self,
        *,
        session_url: str,
        media_path: Path,
        media_size_bytes: int,
        media_mime_type: str,
        offset: int,
    ) -> ReleaseProviderResult: ...

    def query_upload_status(
        self,
        *,
        session_url: str,
        media_size_bytes: int,
    ) -> ReleaseProviderResult: ...

    def update_metadata_status(
        self,
        *,
        video_id: str,
        snippet: dict[str, Any],
        status: dict[str, Any],
    ) -> ReleaseProviderResult: ...

    def set_thumbnail(
        self,
        *,
        video_id: str,
        thumbnail_path: Path,
        mime_type: str,
    ) -> ReleaseProviderResult: ...

    def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
    ) -> ReleaseProviderResult: ...

    def update_visibility(
        self,
        *,
        video_id: str,
        status: dict[str, Any],
    ) -> ReleaseProviderResult: ...

    def create_top_level_comment(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        text: str,
    ) -> ReleaseProviderResult: ...


ProviderBuilder = Callable[[str], ReleaseProvider]


def build_release_provider(account_alias: str) -> ReleaseProvider:
    from video_channel_manager.config import get_settings
    from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore

    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    return YouTubeReleaseProvider(
        client_config=config,
        token_store=store,
        account_alias=account_alias,
    )


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def metadata_verdict(
    plan: dict[str, Any],
    raw: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    snippet = _dict_field(raw, "snippet")
    status = _dict_field(raw, "status")
    expected_snippet = _dict_field(plan, "snippet")
    expected_status = _dict_field(plan, "initial_status")
    raw_tags = snippet.get("tags")
    fields_match = (
        snippet.get("title") == expected_snippet.get("title")
        and snippet.get("description", "") == expected_snippet.get("description", "")
        and str(snippet.get("categoryId") or "")
        == str(expected_snippet.get("categoryId") or "")
        and tags_equivalent(
            [str(item) for item in expected_snippet.get("tags", [])],
            [str(item) for item in raw_tags] if isinstance(raw_tags, list) else [],
        )
        and status.get("privacyStatus") == expected_status.get("privacyStatus")
    )
    synthetic = classify_boolean_readback(
        payload=status,
        key="containsSyntheticMedia",
        expected=bool(expected_status.get("containsSyntheticMedia", False)),
    )
    made_for_kids = status.get("selfDeclaredMadeForKids")
    expected_kids = bool(expected_status.get("selfDeclaredMadeForKids", False))
    kids_match = made_for_kids is None or made_for_kids is expected_kids
    exact = fields_match and kids_match and synthetic.verdict == "verified"
    return exact, {
        "fields_match": fields_match,
        "self_declared_made_for_kids_match": kids_match,
        "contains_synthetic_media_verdict": synthetic.verdict,
        "contains_synthetic_media_actual": synthetic.actual,
        "provider_readback_sha256": canonical_sha256(raw),
    }


def processing_verdict(
    plan: dict[str, Any],
    raw: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    snippet = _dict_field(raw, "snippet")
    status = _dict_field(raw, "status")
    processing = _dict_field(raw, "processingDetails")
    channel_id = str(snippet.get("channelId") or "")
    privacy = str(status.get("privacyStatus") or "")
    processing_status = str(processing.get("processingStatus") or "")
    evidence = {
        "channel_id": channel_id,
        "privacy_status": privacy,
        "processing_status": processing_status or "unobserved",
        "provider_readback_sha256": canonical_sha256(raw),
    }
    if channel_id != plan["target_channel_id"] or processing_status == "failed":
        return "blocked", evidence
    if privacy == "private" and processing_status == "succeeded":
        return "verified", evidence
    return "not_ready", evidence


def _apply_result(
    release: dict[str, Any],
    *,
    child_id: str,
    result: ReleaseProviderResult,
) -> dict[str, Any]:
    return transition_child(
        release,
        child_id=child_id,
        provider_effect=result.provider_effect,
        remote_id=result.remote_id,
        evidence=result.evidence if result.evidence else None,
        runtime_updates=result.runtime,
    )


def _prepare_mutation(
    stable_journal: Path,
    journal: dict[str, Any],
    release: dict[str, Any],
    *,
    child_id: str,
    payload: object,
    runtime_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = prepare_child(
        release,
        child_id=child_id,
        payload=payload,
        attempt_id=uuid.uuid4().hex,
        runtime_updates=runtime_updates,
    )
    updated = transition_child(
        updated,
        child_id=child_id,
        provider_effect="may_exist",
    )
    persist_release(stable_journal, journal, updated)
    return updated


def _run_upload_session(
    plan: dict[str, Any],
    journal: dict[str, Any],
    release: dict[str, Any],
    stable_journal: Path,
    provider: ReleaseProvider,
) -> dict[str, Any]:
    payload = {
        "snippet": plan["snippet"],
        "status": plan["initial_status"],
        "media_sha256": plan["media"]["sha256"],
        "media_size_bytes": plan["media"]["size_bytes"],
        "media_mime_type": plan["media"]["mime_type"],
    }
    release = _prepare_mutation(
        stable_journal,
        journal,
        release,
        child_id="upload-session",
        payload=payload,
    )
    result = provider.start_upload_session(
        snippet=dict(plan["snippet"]),
        status=dict(plan["initial_status"]),
        media_size_bytes=int(plan["media"]["size_bytes"]),
        media_mime_type=str(plan["media"]["mime_type"]),
    )
    release = _apply_result(release, child_id="upload-session", result=result)
    persist_release(stable_journal, journal, release)
    return release


def _run_upload(
    plan: dict[str, Any],
    journal: dict[str, Any],
    release: dict[str, Any],
    stable_journal: Path,
    provider: ReleaseProvider,
) -> dict[str, Any]:
    session = child_by_id(release, "upload-session")
    session_runtime = _dict_field(session, "runtime")
    session_url = str(session_runtime.get("session_url") or "")
    if not session_url:
        raise UploadPlanError(
            "Verified upload-session child lacks its durable resumable session URL."
        )
    current = child_by_id(release, "upload")
    runtime = _dict_field(current, "runtime")
    if runtime.get("resume_requires_status_query") is True:
        raise UploadPlanError("Ambiguous media PUT requires reconcile before any resume attempt.")
    offset = int(runtime.get("next_offset", 0))
    payload = {
        "session_url_sha256": session_runtime.get("session_url_sha256"),
        "media_sha256": plan["media"]["sha256"],
        "media_size_bytes": plan["media"]["size_bytes"],
        "offset": offset,
    }
    release = _prepare_mutation(
        stable_journal,
        journal,
        release,
        child_id="upload",
        payload=payload,
        runtime_updates={"next_offset": offset},
    )
    result = provider.upload_media(
        session_url=session_url,
        media_path=Path(plan["media"]["path"]),
        media_size_bytes=int(plan["media"]["size_bytes"]),
        media_mime_type=str(plan["media"]["mime_type"]),
        offset=offset,
    )
    release = _apply_result(release, child_id="upload", result=result)
    persist_release(stable_journal, journal, release)
    return release


def _run_readback_child(
    child_id: str,
    plan: dict[str, Any],
    journal: dict[str, Any],
    release: dict[str, Any],
    stable_journal: Path,
    provider: ReleaseProvider,
) -> dict[str, Any] | None:
    video_id = video_id_from_release(journal, release)
    if child_id == "processing-private":
        release = prepare_child(
            release,
            child_id=child_id,
            payload={
                "video_id": video_id,
                "required_privacy": "private",
                "required_processing": "succeeded",
            },
        )
        verdict, evidence = processing_verdict(plan, provider.read_video(video_id))
        effect: ProviderEffect = (
            "verified"
            if verdict == "verified"
            else "confirmed_absent"
            if verdict == "not_ready"
            else "may_exist"
        )
        release = transition_child(
            release,
            child_id=child_id,
            provider_effect=effect,
            remote_id=video_id if effect == "verified" else None,
            evidence=evidence,
        )
        persist_release(stable_journal, journal, release)
        return release

    if child_id == "metadata-status":
        payload = {
            "video_id": video_id,
            "snippet": plan["snippet"],
            "status": plan["initial_status"],
        }
        release = prepare_child(release, child_id=child_id, payload=payload)
        already, evidence = metadata_verdict(plan, provider.read_video(video_id))
        if already:
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence=evidence,
            )
            persist_release(stable_journal, journal, release)
            return release
        release = transition_child(release, child_id=child_id, provider_effect="may_exist")
        persist_release(stable_journal, journal, release)
        result = provider.update_metadata_status(
            video_id=video_id,
            snippet=dict(plan["snippet"]),
            status=dict(plan["initial_status"]),
        )
        release = _apply_result(release, child_id=child_id, result=result)
        persist_release(stable_journal, journal, release)
        if result.provider_effect == "may_exist" and result.runtime.get("accepted_response") is True:
            verified, readback = metadata_verdict(plan, provider.read_video(video_id))
            if verified:
                release = transition_child(
                    release,
                    child_id=child_id,
                    provider_effect="verified",
                    remote_id=video_id,
                    evidence={"mutation": result.evidence, "readback": readback},
                )
                persist_release(stable_journal, journal, release)
        return release

    if child_id == "visibility-publication":
        final_privacy = str(plan["final_privacy_status"])
        release = prepare_child(
            release,
            child_id=child_id,
            payload={"video_id": video_id, "privacyStatus": final_privacy},
        )
        before = provider.read_video(video_id)
        if _dict_field(before, "status").get("privacyStatus") == final_privacy:
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={
                    "privacy_status": final_privacy,
                    "provider_readback_sha256": canonical_sha256(before),
                },
            )
            persist_release(stable_journal, journal, release)
            return release
        status = dict(plan["initial_status"])
        status["privacyStatus"] = final_privacy
        release = transition_child(release, child_id=child_id, provider_effect="may_exist")
        persist_release(stable_journal, journal, release)
        result = provider.update_visibility(video_id=video_id, status=status)
        release = _apply_result(release, child_id=child_id, result=result)
        persist_release(stable_journal, journal, release)
        if result.provider_effect == "may_exist" and result.evidence.get("accepted_response") is True:
            after = provider.read_video(video_id)
            if _dict_field(after, "status").get("privacyStatus") == final_privacy:
                release = transition_child(
                    release,
                    child_id=child_id,
                    provider_effect="verified",
                    remote_id=video_id,
                    evidence={
                        "mutation": result.evidence,
                        "provider_readback_sha256": canonical_sha256(after),
                    },
                )
                persist_release(stable_journal, journal, release)
        return release
    return None


def _run_auxiliary_child(
    child_id: str,
    plan: dict[str, Any],
    journal: dict[str, Any],
    release: dict[str, Any],
    stable_journal: Path,
    provider: ReleaseProvider,
) -> dict[str, Any]:
    video_id = video_id_from_release(journal, release)
    if child_id == "thumbnail":
        thumbnail = plan.get("thumbnail")
        release = prepare_child(
            release,
            child_id=child_id,
            payload={"video_id": video_id, "thumbnail": thumbnail},
        )
        if thumbnail is None:
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={"thumbnail_not_requested": True},
            )
        else:
            if not isinstance(thumbnail, dict):
                raise UploadPlanError("Release thumbnail must be an object or null.")
            release = transition_child(release, child_id=child_id, provider_effect="may_exist")
            persist_release(stable_journal, journal, release)
            release = _apply_result(
                release,
                child_id=child_id,
                result=provider.set_thumbnail(
                    video_id=video_id,
                    thumbnail_path=Path(str(thumbnail["path"])),
                    mime_type=str(thumbnail["mime_type"]),
                ),
            )
        persist_release(stable_journal, journal, release)
        return release

    if child_id.startswith("playlist:"):
        playlist_id = child_id.removeprefix("playlist:")
        release = prepare_child(
            release,
            child_id=child_id,
            payload={"video_id": video_id, "playlist_id": playlist_id},
        )
        if provider.playlist_contains_video(playlist_id, video_id):
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={
                    "playlist_id": playlist_id,
                    "video_id": video_id,
                    "preexisting_membership": True,
                },
            )
        else:
            release = transition_child(release, child_id=child_id, provider_effect="may_exist")
            persist_release(stable_journal, journal, release)
            result = provider.insert_playlist_item(playlist_id=playlist_id, video_id=video_id)
            release = _apply_result(release, child_id=child_id, result=result)
            persist_release(stable_journal, journal, release)
            if (
                result.provider_effect == "may_exist"
                and result.evidence.get("accepted_response") is True
                and provider.playlist_contains_video(playlist_id, video_id)
            ):
                release = transition_child(
                    release,
                    child_id=child_id,
                    provider_effect="verified",
                    remote_id=result.remote_id or video_id,
                    evidence={
                        "mutation": result.evidence,
                        "full_paginated_readback": True,
                        "video_id": video_id,
                    },
                )
        persist_release(stable_journal, journal, release)
        return release

    if child_id == "top-level-comment":
        comment = plan.get("top_level_comment")
        release = prepare_child(
            release,
            child_id=child_id,
            payload={"video_id": video_id, "text": comment},
        )
        if comment is None:
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={"top_level_comment_not_requested": True},
            )
        else:
            release = transition_child(release, child_id=child_id, provider_effect="may_exist")
            persist_release(stable_journal, journal, release)
            release = _apply_result(
                release,
                child_id=child_id,
                result=provider.create_top_level_comment(
                    video_id=video_id,
                    expected_channel_id=str(plan["target_channel_id"]),
                    text=str(comment),
                ),
            )
        persist_release(stable_journal, journal, release)
        return release

    if child_id == "manual-pin-evidence":
        release = prepare_child(
            release,
            child_id=child_id,
            payload={
                "video_id": video_id,
                "manual_pin_required": bool(plan["manual_pin_evidence_required"]),
            },
        )
        if plan["manual_pin_evidence_required"]:
            persist_release(stable_journal, journal, release)
            raise UploadPlanError(
                "Manual pin evidence is required; provider automation will not attempt pinning."
            )
        release = transition_child(
            release,
            child_id=child_id,
            provider_effect="verified",
            remote_id=video_id,
            evidence={"manual_pin_not_requested": True, "provider_write_performed": False},
        )
        persist_release(stable_journal, journal, release)
        return release
    raise UploadPlanError(f"Unsupported release child: {child_id}")


def execute_child(
    *,
    child_id: str,
    plan: dict[str, Any],
    journal: dict[str, Any],
    release: dict[str, Any],
    stable_journal: Path,
    provider: ReleaseProvider,
) -> dict[str, Any]:
    if child_id == "upload-session":
        return _run_upload_session(plan, journal, release, stable_journal, provider)
    if child_id == "upload":
        return _run_upload(plan, journal, release, stable_journal, provider)
    readback = _run_readback_child(
        child_id,
        plan,
        journal,
        release,
        stable_journal,
        provider,
    )
    if readback is not None:
        return readback
    return _run_auxiliary_child(
        child_id,
        plan,
        journal,
        release,
        stable_journal,
        provider,
    )


def execute_next(
    args: argparse.Namespace,
    *,
    provider_builder: ProviderBuilder = build_release_provider,
) -> int:
    if not args.execute:
        raise UploadPlanError(
            "Provider execution requires explicit --execute in addition to an exact approval file."
        )
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    approval = load_json_object(Path(args.approval).resolve())
    stable_journal = journal_path(
        Path(args.data_dir).resolve(),
        str(plan["upload_key_sha256"]),
    )
    with stable_key_mutation_lock(stable_journal):
        journal = read_json(stable_journal)
        release = release_from_journal(journal, plan=plan)
        child = next_release_child(release)
        if child is None:
            print("YOUTUBE RELEASE COMPLETE — ALL CHILD OPERATIONS VERIFIED.")
            return 0
        child_id = str(child["child_id"])
        absence_sha = journal.get("release_absence_evidence_sha256")
        validate_execution_approval(
            approval,
            plan=plan,
            child_id=child_id,
            absence_evidence_sha256=(
                str(absence_sha) if isinstance(absence_sha, str) else None
            ),
        )
        # Exact identity/approval is proven before config/token material is loaded.
        provider = provider_builder(str(plan["account_alias"]))
        try:
            release = execute_child(
                child_id=child_id,
                plan=plan,
                journal=journal,
                release=release,
                stable_journal=stable_journal,
                provider=provider,
            )
        finally:
            provider.close()
    next_child = next_release_child(release)
    if next_child is None:
        print("YOUTUBE RELEASE COMPLETE — ALL CHILD OPERATIONS VERIFIED.")
    else:
        print(
            f"YOUTUBE RELEASE CHILD PROCESSED: {child_id}; "
            f"NEXT: {next_child['child_id']}"
        )
    return 0


def reconcile(
    args: argparse.Namespace,
    *,
    provider_builder: ProviderBuilder = build_release_provider,
) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    stable_journal = journal_path(
        Path(args.data_dir).resolve(),
        str(plan["upload_key_sha256"]),
    )
    with stable_key_mutation_lock(stable_journal):
        journal = read_json(stable_journal)
        release = release_from_journal(journal, plan=plan)
        ambiguous = [
            child
            for child in release["children"]
            if isinstance(child, dict) and child.get("provider_effect") == "may_exist"
        ]
        if len(ambiguous) != 1:
            raise UploadPlanError(
                f"Expected exactly one unresolved release child, found {len(ambiguous)}."
            )
        child_id = str(ambiguous[0]["child_id"])
        provider = provider_builder(str(plan["account_alias"]))
        try:
            if child_id == "upload":
                session = child_by_id(release, "upload-session")
                session_url = str(_dict_field(session, "runtime").get("session_url") or "")
                if not session_url:
                    raise UploadPlanError(
                        "Cannot reconcile upload without the exact persisted resumable session URL."
                    )
                release = _apply_result(
                    release,
                    child_id=child_id,
                    result=provider.query_upload_status(
                        session_url=session_url,
                        media_size_bytes=int(plan["media"]["size_bytes"]),
                    ),
                )
            elif child_id in {
                "processing-private",
                "metadata-status",
                "visibility-publication",
            }:
                video_id = video_id_from_release(journal, release)
                raw = provider.read_video(video_id)
                if child_id == "processing-private":
                    verdict, evidence = processing_verdict(plan, raw)
                    effect: ProviderEffect = (
                        "verified" if verdict == "verified" else "may_exist"
                    )
                elif child_id == "metadata-status":
                    verified, evidence = metadata_verdict(plan, raw)
                    effect = "verified" if verified else "may_exist"
                else:
                    status = _dict_field(raw, "status")
                    verified = status.get("privacyStatus") == plan["final_privacy_status"]
                    effect = "verified" if verified else "may_exist"
                    evidence = {
                        "privacy_status": status.get("privacyStatus"),
                        "provider_readback_sha256": canonical_sha256(raw),
                    }
                release = transition_child(
                    release,
                    child_id=child_id,
                    provider_effect=effect,
                    remote_id=video_id if effect == "verified" else None,
                    evidence=evidence,
                )
            elif child_id.startswith("playlist:"):
                video_id = video_id_from_release(journal, release)
                playlist_id = child_id.removeprefix("playlist:")
                if provider.playlist_contains_video(playlist_id, video_id):
                    release = transition_child(
                        release,
                        child_id=child_id,
                        provider_effect="verified",
                        remote_id=str(ambiguous[0].get("remote_id") or video_id),
                        evidence={
                            "full_paginated_readback": True,
                            "playlist_id": playlist_id,
                            "video_id": video_id,
                        },
                    )
            else:
                raise UploadPlanError(
                    f"Release child {child_id} cannot be safely auto-reconciled; "
                    "preserve may_exist and use exact manual evidence."
                )
        finally:
            provider.close()
        persist_release(stable_journal, journal, release)
    print(f"YOUTUBE RELEASE RECONCILIATION COMPLETE FOR {child_id}.")
    return 0
