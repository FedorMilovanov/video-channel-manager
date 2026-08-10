from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Protocol

from video_channel_manager.youtube_provider_semantics import classify_boolean_readback, tags_equivalent
from video_channel_manager.youtube_release_plan import (
    build_release_plan,
    load_json_object,
    validate_absence_evidence,
    validate_execution_approval,
    validate_release_plan,
)
from video_channel_manager.youtube_release_provider import (
    ReleaseProviderResult,
    YouTubeReleaseProvider,
    YouTubeReleaseProviderError,
)
from video_channel_manager.youtube_release_state import (
    YouTubeReleaseStateError,
    build_release_state,
    child_by_id,
    mark_existing_target_absent,
    mark_existing_target_adopted,
    next_release_child,
    prepare_child,
    transition_child,
    validate_release_state,
)
from video_channel_manager.youtube_stable_state import (
    read_json,
    stable_key_mutation_lock,
    write_json_atomic,
    write_new_json,
)
from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    adopted_journal,
    canonical_sha256,
    journal_path,
    require_adoption_allowed,
    validate_intent,
    validate_journal,
    validate_live_state_evidence,
)


class ReadOnlyVideo(Protocol):
    title: str
    privacy_status: str | None
    revision: str
    ref: Any


class ReadOnlyYouTubeClient(Protocol):
    def get_video(self, video_id: str) -> ReadOnlyVideo: ...

    def close(self) -> None: ...


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

    def query_upload_status(self, *, session_url: str, media_size_bytes: int) -> ReleaseProviderResult: ...

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

    def insert_playlist_item(self, *, playlist_id: str, video_id: str) -> ReleaseProviderResult: ...

    def update_visibility(self, *, video_id: str, status: dict[str, Any]) -> ReleaseProviderResult: ...

    def create_top_level_comment(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        text: str,
    ) -> ReleaseProviderResult: ...


ProviderBuilder = Callable[[str], ReleaseProvider]


def _build_readonly_client(account_alias: str) -> ReadOnlyYouTubeClient:
    """Load OAuth material only after canonical project identity has passed."""

    from video_channel_manager.config import get_settings
    from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore, YouTubeApiClient

    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    return YouTubeApiClient(client_config=config, token_store=store, account_alias=account_alias)


def _build_release_provider(account_alias: str) -> ReleaseProvider:
    from video_channel_manager.config import get_settings
    from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore

    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    return YouTubeReleaseProvider(client_config=config, token_store=store, account_alias=account_alias)


def _verify_remote_against_evidence(*, evidence: dict[str, Any], remote: ReadOnlyVideo) -> None:
    video = evidence["video"]
    expected_title = video.get("title")
    if isinstance(expected_title, str) and expected_title and remote.title != expected_title:
        raise UploadPlanError("Provider video title does not match immutable live-state evidence.")
    expected_privacy = video.get("privacy_status")
    if isinstance(expected_privacy, str) and expected_privacy and remote.privacy_status != expected_privacy:
        raise UploadPlanError(
            f"Provider privacy mismatch: evidence={expected_privacy} provider={remote.privacy_status}."
        )


def adopt_existing(args: argparse.Namespace) -> int:
    evidence_path = Path(args.evidence).resolve()
    data_dir = Path(args.data_dir).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable adoption evidence: {output}")

    evidence = read_json(evidence_path)
    identity = validate_live_state_evidence(evidence)
    client = _build_readonly_client(identity["account_alias"])
    try:
        remote = client.get_video(identity["video_id"])
    finally:
        client.close()
    if remote.ref.channel_id != identity["target_channel_id"]:
        raise UploadPlanError(
            f"Provider channel mismatch: expected {identity['target_channel_id']} got {remote.ref.channel_id}."
        )
    if remote.ref.remote_id != identity["video_id"]:
        raise UploadPlanError(f"Provider video mismatch: expected {identity['video_id']} got {remote.ref.remote_id}.")
    _verify_remote_against_evidence(evidence=evidence, remote=remote)

    proposed = adopted_journal(
        evidence,
        remote_video_id=remote.ref.remote_id,
        remote_channel_id=remote.ref.channel_id,
        remote_revision=remote.revision,
    )
    stable_journal = journal_path(data_dir, identity["upload_key_sha256"])
    with stable_key_mutation_lock(stable_journal):
        current = read_json(stable_journal) if stable_journal.is_file() else None
        write_needed = require_adoption_allowed(current, proposed=proposed)
        if write_needed:
            write_json_atomic(stable_journal, proposed)
            durable = proposed
        else:
            if current is None:
                raise UploadPlanError("Idempotent adoption unexpectedly lacks an existing durable journal.")
            durable = current

    result = {
        "schema_name": "video-manager.youtube-existing-target-adoption-result",
        "schema_version": 2,
        "project_key": identity["project_key"],
        "account_alias": identity["account_alias"],
        "target_channel_id": identity["target_channel_id"],
        "media_sha256": identity["media_sha256"],
        "upload_key_sha256": identity["upload_key_sha256"],
        "remote_video_id": remote.ref.remote_id,
        "remote_revision": remote.revision,
        "source_evidence_sha256": canonical_sha256(evidence),
        "journal_sha256": canonical_sha256(durable),
        "journal_path": str(stable_journal),
        "provider_reads": 1,
        "provider_writes": 0,
        "provider_effect": "verified",
        "adopted_existing_target": True,
        "journal_write_performed": write_needed,
    }
    write_new_json(output, result)
    print("YOUTUBE EXISTING TARGET ADOPTED — READ ONLY; PROVIDER WRITES 0.")
    print(f"Video ID: {remote.ref.remote_id}")
    print(f"Stable upload key: {identity['upload_key_sha256']}")
    print(f"Journal: {stable_journal}")
    return 0


def prepare_plan(args: argparse.Namespace) -> int:
    intent = read_json(Path(args.intent).resolve())
    validate_intent(intent)
    comment: str | None = None
    if args.comment_file:
        comment = Path(args.comment_file).resolve().read_text(encoding="utf-8")
    plan = build_release_plan(
        intent,
        thumbnail_path=Path(args.thumbnail).resolve() if args.thumbnail else None,
        playlist_ids=list(args.playlist or []),
        final_privacy_status=args.final_privacy,
        top_level_comment=comment,
        manual_pin_evidence_required=bool(args.manual_pin),
    )
    output = Path(args.output).resolve()
    write_new_json(output, plan)
    print("YOUTUBE RELEASE PLAN READY — LOCAL/PROVIDER-INERT.")
    print(f"Release plan SHA: {plan['release_plan_sha256']}")
    return 0


def initialize_release(args: argparse.Namespace) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    data_dir = Path(args.data_dir).resolve()
    stable_journal = journal_path(data_dir, str(plan["upload_key_sha256"]))
    output = Path(args.output).resolve()
    if output.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable release initialization evidence: {output}")

    with stable_key_mutation_lock(stable_journal):
        if not stable_journal.is_file():
            raise UploadPlanError("Release initialization requires an existing planned or adopted stable journal.")
        journal = read_json(stable_journal)
        existing_release = journal.get("release")
        if isinstance(existing_release, dict):
            validate_release_state(existing_release)
            if existing_release.get("release_plan_sha256") != plan["release_plan_sha256"]:
                raise UploadPlanError("Stable journal already contains a different immutable release plan.")
            release = existing_release
            absence_sha = journal.get("release_absence_evidence_sha256")
        else:
            playlist_ids = [str(item) for item in plan["playlist_ids"]]
            release = build_release_state(
                upload_key_sha256=str(plan["upload_key_sha256"]),
                release_plan_sha256=str(plan["release_plan_sha256"]),
                playlist_ids=playlist_ids,
            )
            if journal.get("adopted_existing_target") is True and journal.get("provider_effect") == "verified":
                remote_video_id = str(journal.get("remote_video_id") or "")
                remote_revision = str(journal.get("remote_revision") or "")
                if not remote_video_id or not remote_revision:
                    raise UploadPlanError("Adopted stable journal lacks exact remote video/revision evidence.")
                release = mark_existing_target_adopted(
                    release,
                    video_id=remote_video_id,
                    remote_revision=remote_revision,
                    evidence={"adopted_journal_sha256": canonical_sha256(journal)},
                )
                absence_sha = None
                validate_release_plan(plan, verify_files=False)
            else:
                if not args.intent or not args.absence_evidence:
                    raise UploadPlanError(
                        "New upload initialization requires --intent and exact reviewed --absence-evidence."
                    )
                intent = read_json(Path(args.intent).resolve())
                validate_intent(intent)
                validate_journal(journal, intent=intent)
                if plan.get("source_intent_sha256") != intent.get("intent_sha256"):
                    raise UploadPlanError("Release plan does not bind the exact planned upload intent.")
                validate_release_plan(plan, verify_files=True)
                absence = read_json(Path(args.absence_evidence).resolve())
                absence_sha = validate_absence_evidence(absence, plan=plan)
                release = mark_existing_target_absent(release, evidence=absence)
            journal["release"] = release
            journal["release_plan_sha256"] = plan["release_plan_sha256"]
            journal["release_absence_evidence_sha256"] = absence_sha
            write_json_atomic(stable_journal, journal)

    result = {
        "schema_name": "video-manager.youtube-release-initialization-result",
        "schema_version": 1,
        "upload_key_sha256": plan["upload_key_sha256"],
        "release_plan_sha256": plan["release_plan_sha256"],
        "release_state_sha256": canonical_sha256(release),
        "existing_target_mode": "adopted" if journal.get("adopted_existing_target") else "confirmed_absent",
        "existing_target_absence_evidence_sha256": absence_sha,
        "provider_writes": 0,
        "journal_path": str(stable_journal),
    }
    write_new_json(output, result)
    print("YOUTUBE RELEASE STATE INITIALIZED — PROVIDER WRITES 0.")
    return 0


def _release_from_journal(journal: dict[str, Any], *, plan: dict[str, Any]) -> dict[str, Any]:
    release = journal.get("release")
    if not isinstance(release, dict):
        raise UploadPlanError("Stable journal has no initialized release state.")
    validate_release_state(release)
    if release.get("release_plan_sha256") != plan.get("release_plan_sha256"):
        raise UploadPlanError("Release state does not bind the exact release plan.")
    if release.get("upload_key_sha256") != plan.get("upload_key_sha256"):
        raise UploadPlanError("Release state stable identity differs from release plan.")
    return release


def _video_id(journal: dict[str, Any], release: dict[str, Any]) -> str:
    upload = child_by_id(release, "upload")
    value = str(upload.get("remote_id") or journal.get("remote_video_id") or "").strip()
    if not value:
        raise UploadPlanError("Release has no verified provider video ID yet.")
    return value


def _provider_payload_result(
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


def _persist_release(stable_journal: Path, journal: dict[str, Any], release: dict[str, Any]) -> None:
    journal["release"] = release
    write_json_atomic(stable_journal, journal)


def _metadata_verdict(plan: dict[str, Any], raw: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    snippet = raw.get("snippet") if isinstance(raw.get("snippet"), dict) else {}
    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    expected_snippet = plan["snippet"]
    expected_status = plan["initial_status"]
    fields_match = (
        snippet.get("title") == expected_snippet.get("title")
        and snippet.get("description", "") == expected_snippet.get("description", "")
        and str(snippet.get("categoryId") or "") == str(expected_snippet.get("categoryId") or "")
        and tags_equivalent(
            [str(item) for item in expected_snippet.get("tags", [])],
            [str(item) for item in snippet.get("tags", [])] if isinstance(snippet.get("tags"), list) else [],
        )
        and status.get("privacyStatus") == expected_status.get("privacyStatus")
    )
    synthetic = classify_boolean_readback(
        payload=status,
        key="containsSyntheticMedia",
        expected=bool(expected_status.get("containsSyntheticMedia", False)),
    )
    made_for_kids = status.get("selfDeclaredMadeForKids")
    kids_match = made_for_kids is None or made_for_kids is bool(expected_status.get("selfDeclaredMadeForKids", False))
    exact = fields_match and kids_match and synthetic.verdict == "verified"
    return exact, {
        "fields_match": fields_match,
        "self_declared_made_for_kids_match": kids_match,
        "contains_synthetic_media_verdict": synthetic.verdict,
        "contains_synthetic_media_actual": synthetic.actual,
        "provider_readback_sha256": canonical_sha256(raw),
    }


def _processing_verdict(plan: dict[str, Any], raw: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    snippet = raw.get("snippet") if isinstance(raw.get("snippet"), dict) else {}
    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    processing = raw.get("processingDetails") if isinstance(raw.get("processingDetails"), dict) else {}
    channel_id = str(snippet.get("channelId") or "")
    privacy = str(status.get("privacyStatus") or "")
    processing_status = str(processing.get("processingStatus") or "")
    evidence = {
        "channel_id": channel_id,
        "privacy_status": privacy,
        "processing_status": processing_status or "unobserved",
        "provider_readback_sha256": canonical_sha256(raw),
    }
    if channel_id != plan["target_channel_id"]:
        return "blocked", evidence
    if processing_status == "failed":
        return "blocked", evidence
    if privacy == "private" and processing_status == "succeeded":
        return "verified", evidence
    return "not_ready", evidence


def _prepare_mutation(
    stable_journal: Path,
    journal: dict[str, Any],
    release: dict[str, Any],
    *,
    child_id: str,
    payload: object,
    runtime_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attempt_id = uuid.uuid4().hex
    updated = prepare_child(
        release,
        child_id=child_id,
        payload=payload,
        attempt_id=attempt_id,
        runtime_updates=runtime_updates,
    )
    updated = transition_child(updated, child_id=child_id, provider_effect="may_exist")
    _persist_release(stable_journal, journal, updated)
    return updated


def _execute_child(
    *,
    child_id: str,
    plan: dict[str, Any],
    journal: dict[str, Any],
    release: dict[str, Any],
    stable_journal: Path,
    provider: ReleaseProvider,
) -> dict[str, Any]:
    if child_id == "upload-session":
        payload = {
            "snippet": plan["snippet"],
            "status": plan["initial_status"],
            "media_sha256": plan["media"]["sha256"],
            "media_size_bytes": plan["media"]["size_bytes"],
            "media_mime_type": plan["media"]["mime_type"],
        }
        release = _prepare_mutation(stable_journal, journal, release, child_id=child_id, payload=payload)
        result = provider.start_upload_session(
            snippet=dict(plan["snippet"]),
            status=dict(plan["initial_status"]),
            media_size_bytes=int(plan["media"]["size_bytes"]),
            media_mime_type=str(plan["media"]["mime_type"]),
        )
        release = _provider_payload_result(release, child_id=child_id, result=result)
        _persist_release(stable_journal, journal, release)
        return release

    if child_id == "upload":
        session = child_by_id(release, "upload-session")
        session_url = str(session.get("runtime", {}).get("session_url") or "")
        if not session_url:
            raise UploadPlanError("Verified upload-session child lacks its durable resumable session URL.")
        current = child_by_id(release, "upload")
        runtime = current.get("runtime") if isinstance(current.get("runtime"), dict) else {}
        if runtime.get("resume_requires_status_query") is True:
            raise UploadPlanError("Ambiguous media PUT requires reconcile before any resume attempt.")
        offset = int(runtime.get("next_offset", 0))
        payload = {
            "session_url_sha256": session["runtime"].get("session_url_sha256"),
            "media_sha256": plan["media"]["sha256"],
            "media_size_bytes": plan["media"]["size_bytes"],
            "offset": offset,
        }
        release = _prepare_mutation(
            stable_journal,
            journal,
            release,
            child_id=child_id,
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
        release = _provider_payload_result(release, child_id=child_id, result=result)
        _persist_release(stable_journal, journal, release)
        return release

    video_id = _video_id(journal, release)

    if child_id == "processing-private":
        payload = {"video_id": video_id, "required_privacy": "private", "required_processing": "succeeded"}
        release = prepare_child(release, child_id=child_id, payload=payload)
        raw = provider.read_video(video_id)
        verdict, evidence = _processing_verdict(plan, raw)
        if verdict == "verified":
            release = transition_child(release, child_id=child_id, provider_effect="verified", remote_id=video_id, evidence=evidence)
        elif verdict == "not_ready":
            release = transition_child(release, child_id=child_id, provider_effect="confirmed_absent", evidence=evidence)
        else:
            release = transition_child(release, child_id=child_id, provider_effect="may_exist", evidence=evidence)
        _persist_release(stable_journal, journal, release)
        return release

    if child_id == "metadata-status":
        payload = {"video_id": video_id, "snippet": plan["snippet"], "status": plan["initial_status"]}
        release = prepare_child(release, child_id=child_id, payload=payload)
        before = provider.read_video(video_id)
        already, evidence = _metadata_verdict(plan, before)
        if already:
            release = transition_child(release, child_id=child_id, provider_effect="verified", remote_id=video_id, evidence=evidence)
            _persist_release(stable_journal, journal, release)
            return release
        release = transition_child(release, child_id=child_id, provider_effect="may_exist")
        _persist_release(stable_journal, journal, release)
        result = provider.update_metadata_status(
            video_id=video_id,
            snippet=dict(plan["snippet"]),
            status=dict(plan["initial_status"]),
        )
        release = _provider_payload_result(release, child_id=child_id, result=result)
        _persist_release(stable_journal, journal, release)
        if result.provider_effect == "may_exist" and result.runtime.get("accepted_response") is True:
            after = provider.read_video(video_id)
            verified, readback = _metadata_verdict(plan, after)
            if verified:
                release = transition_child(
                    release,
                    child_id=child_id,
                    provider_effect="verified",
                    remote_id=video_id,
                    evidence={"mutation": result.evidence, "readback": readback},
                )
                _persist_release(stable_journal, journal, release)
        return release

    if child_id == "thumbnail":
        thumbnail = plan.get("thumbnail")
        payload = {"video_id": video_id, "thumbnail": thumbnail}
        release = prepare_child(release, child_id=child_id, payload=payload)
        if thumbnail is None:
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={"thumbnail_not_requested": True},
            )
            _persist_release(stable_journal, journal, release)
            return release
        release = transition_child(release, child_id=child_id, provider_effect="may_exist")
        _persist_release(stable_journal, journal, release)
        result = provider.set_thumbnail(
            video_id=video_id,
            thumbnail_path=Path(str(thumbnail["path"])),
            mime_type=str(thumbnail["mime_type"]),
        )
        release = _provider_payload_result(release, child_id=child_id, result=result)
        _persist_release(stable_journal, journal, release)
        return release

    if child_id.startswith("playlist:"):
        playlist_id = child_id.removeprefix("playlist:")
        payload = {"video_id": video_id, "playlist_id": playlist_id}
        release = prepare_child(release, child_id=child_id, payload=payload)
        if provider.playlist_contains_video(playlist_id, video_id):
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={"playlist_id": playlist_id, "video_id": video_id, "preexisting_membership": True},
            )
            _persist_release(stable_journal, journal, release)
            return release
        release = transition_child(release, child_id=child_id, provider_effect="may_exist")
        _persist_release(stable_journal, journal, release)
        result = provider.insert_playlist_item(playlist_id=playlist_id, video_id=video_id)
        release = _provider_payload_result(release, child_id=child_id, result=result)
        _persist_release(stable_journal, journal, release)
        if result.provider_effect == "may_exist" and result.evidence.get("accepted_response") is True:
            if provider.playlist_contains_video(playlist_id, video_id):
                release = transition_child(
                    release,
                    child_id=child_id,
                    provider_effect="verified",
                    remote_id=result.remote_id or video_id,
                    evidence={"mutation": result.evidence, "full_paginated_readback": True, "video_id": video_id},
                )
                _persist_release(stable_journal, journal, release)
        return release

    if child_id == "visibility-publication":
        final_privacy = str(plan["final_privacy_status"])
        payload = {"video_id": video_id, "privacyStatus": final_privacy}
        release = prepare_child(release, child_id=child_id, payload=payload)
        before = provider.read_video(video_id)
        current_status = before.get("status") if isinstance(before.get("status"), dict) else {}
        if current_status.get("privacyStatus") == final_privacy:
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={"privacy_status": final_privacy, "provider_readback_sha256": canonical_sha256(before)},
            )
            _persist_release(stable_journal, journal, release)
            return release
        status = dict(plan["initial_status"])
        status["privacyStatus"] = final_privacy
        release = transition_child(release, child_id=child_id, provider_effect="may_exist")
        _persist_release(stable_journal, journal, release)
        result = provider.update_visibility(video_id=video_id, status=status)
        release = _provider_payload_result(release, child_id=child_id, result=result)
        _persist_release(stable_journal, journal, release)
        if result.provider_effect == "may_exist" and result.evidence.get("accepted_response") is True:
            after = provider.read_video(video_id)
            after_status = after.get("status") if isinstance(after.get("status"), dict) else {}
            if after_status.get("privacyStatus") == final_privacy:
                release = transition_child(
                    release,
                    child_id=child_id,
                    provider_effect="verified",
                    remote_id=video_id,
                    evidence={"mutation": result.evidence, "provider_readback_sha256": canonical_sha256(after)},
                )
                _persist_release(stable_journal, journal, release)
        return release

    if child_id == "top-level-comment":
        comment = plan.get("top_level_comment")
        payload = {"video_id": video_id, "text": comment}
        release = prepare_child(release, child_id=child_id, payload=payload)
        if comment is None:
            release = transition_child(
                release,
                child_id=child_id,
                provider_effect="verified",
                remote_id=video_id,
                evidence={"top_level_comment_not_requested": True},
            )
            _persist_release(stable_journal, journal, release)
            return release
        release = transition_child(release, child_id=child_id, provider_effect="may_exist")
        _persist_release(stable_journal, journal, release)
        result = provider.create_top_level_comment(
            video_id=video_id,
            expected_channel_id=str(plan["target_channel_id"]),
            text=str(comment),
        )
        release = _provider_payload_result(release, child_id=child_id, result=result)
        _persist_release(stable_journal, journal, release)
        return release

    if child_id == "manual-pin-evidence":
        payload = {"video_id": video_id, "manual_pin_required": bool(plan["manual_pin_evidence_required"])}
        release = prepare_child(release, child_id=child_id, payload=payload)
        if plan["manual_pin_evidence_required"]:
            _persist_release(stable_journal, journal, release)
            raise UploadPlanError("Manual pin evidence is required; provider automation will not attempt pinning.")
        release = transition_child(
            release,
            child_id=child_id,
            provider_effect="verified",
            remote_id=video_id,
            evidence={"manual_pin_not_requested": True, "provider_write_performed": False},
        )
        _persist_release(stable_journal, journal, release)
        return release

    raise UploadPlanError(f"Unsupported release child: {child_id}")


def execute_next(args: argparse.Namespace, *, provider_builder: ProviderBuilder = _build_release_provider) -> int:
    if not args.execute:
        raise UploadPlanError("Provider execution requires explicit --execute in addition to an exact approval file.")
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    approval = load_json_object(Path(args.approval).resolve())
    stable_journal = journal_path(Path(args.data_dir).resolve(), str(plan["upload_key_sha256"]))

    with stable_key_mutation_lock(stable_journal):
        journal = read_json(stable_journal)
        release = _release_from_journal(journal, plan=plan)
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
            absence_evidence_sha256=str(absence_sha) if isinstance(absence_sha, str) else None,
        )
        # Exact identity/approval is proven above before config/token material is loaded.
        provider = provider_builder(str(plan["account_alias"]))
        try:
            release = _execute_child(
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
        print(f"YOUTUBE RELEASE CHILD PROCESSED: {child_id}; NEXT: {next_child['child_id']}")
    return 0


def reconcile(args: argparse.Namespace, *, provider_builder: ProviderBuilder = _build_release_provider) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    stable_journal = journal_path(Path(args.data_dir).resolve(), str(plan["upload_key_sha256"]))
    with stable_key_mutation_lock(stable_journal):
        journal = read_json(stable_journal)
        release = _release_from_journal(journal, plan=plan)
        ambiguous = [child for child in release["children"] if child.get("provider_effect") == "may_exist"]
        if len(ambiguous) != 1:
            raise UploadPlanError(f"Expected exactly one unresolved release child, found {len(ambiguous)}.")
        child_id = str(ambiguous[0]["child_id"])
        provider = provider_builder(str(plan["account_alias"]))
        try:
            if child_id == "upload":
                session = child_by_id(release, "upload-session")
                session_url = str(session.get("runtime", {}).get("session_url") or "")
                if not session_url:
                    raise UploadPlanError("Cannot reconcile upload without the exact persisted resumable session URL.")
                result = provider.query_upload_status(
                    session_url=session_url,
                    media_size_bytes=int(plan["media"]["size_bytes"]),
                )
                release = _provider_payload_result(release, child_id=child_id, result=result)
            elif child_id in {"processing-private", "metadata-status", "visibility-publication"}:
                video_id = _video_id(journal, release)
                raw = provider.read_video(video_id)
                if child_id == "processing-private":
                    verdict, evidence = _processing_verdict(plan, raw)
                    effect = "verified" if verdict == "verified" else "may_exist"
                    release = transition_child(
                        release,
                        child_id=child_id,
                        provider_effect=effect,
                        remote_id=video_id if effect == "verified" else None,
                        evidence=evidence,
                    )
                elif child_id == "metadata-status":
                    verified, evidence = _metadata_verdict(plan, raw)
                    release = transition_child(
                        release,
                        child_id=child_id,
                        provider_effect="verified" if verified else "may_exist",
                        remote_id=video_id if verified else None,
                        evidence=evidence,
                    )
                else:
                    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}
                    verified = status.get("privacyStatus") == plan["final_privacy_status"]
                    release = transition_child(
                        release,
                        child_id=child_id,
                        provider_effect="verified" if verified else "may_exist",
                        remote_id=video_id if verified else None,
                        evidence={
                            "privacy_status": status.get("privacyStatus"),
                            "provider_readback_sha256": canonical_sha256(raw),
                        },
                    )
            elif child_id.startswith("playlist:"):
                video_id = _video_id(journal, release)
                playlist_id = child_id.removeprefix("playlist:")
                if provider.playlist_contains_video(playlist_id, video_id):
                    release = transition_child(
                        release,
                        child_id=child_id,
                        provider_effect="verified",
                        remote_id=ambiguous[0].get("remote_id") or video_id,
                        evidence={"full_paginated_readback": True, "playlist_id": playlist_id, "video_id": video_id},
                    )
            else:
                raise UploadPlanError(
                    f"Release child {child_id} cannot be safely auto-reconciled; preserve may_exist and use exact manual evidence."
                )
        finally:
            provider.close()
        _persist_release(stable_journal, journal, release)
    print(f"YOUTUBE RELEASE RECONCILIATION COMPLETE FOR {child_id}.")
    return 0


def record_manual_evidence(args: argparse.Namespace) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    stable_journal = journal_path(Path(args.data_dir).resolve(), str(plan["upload_key_sha256"]))
    evidence = load_json_object(Path(args.evidence).resolve())
    child_id = str(args.child)
    allowed = {"manual-pin-evidence", "metadata-status", "thumbnail"}
    if child_id not in allowed:
        raise UploadPlanError(f"Manual evidence is not allowed for release child {child_id}.")
    if evidence.get("release_plan_sha256") != plan["release_plan_sha256"]:
        raise UploadPlanError("Manual evidence does not bind the exact release plan.")
    if evidence.get("child_id") != child_id or evidence.get("provider_effect") != "verified":
        raise UploadPlanError("Manual evidence must bind the exact child with provider_effect=verified.")
    if not str(evidence.get("reviewed_by") or "").strip() or not str(evidence.get("reviewed_at") or "").strip():
        raise UploadPlanError("Manual evidence requires reviewed_by and reviewed_at.")

    with stable_key_mutation_lock(stable_journal):
        journal = read_json(stable_journal)
        release = _release_from_journal(journal, plan=plan)
        child = child_by_id(release, child_id)
        if child.get("payload_sha256") is None:
            video_id = _video_id(journal, release)
            release = prepare_child(
                release,
                child_id=child_id,
                payload={"video_id": video_id, "manual_evidence": True},
            )
        release = transition_child(
            release,
            child_id=child_id,
            provider_effect="verified",
            remote_id=str(evidence.get("remote_id") or "") or None,
            evidence=evidence,
        )
        _persist_release(stable_journal, journal, release)
    print(f"MANUAL YOUTUBE RELEASE EVIDENCE RECORDED FOR {child_id}; PROVIDER WRITES 0.")
    return 0


def status(args: argparse.Namespace) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    stable_journal = journal_path(Path(args.data_dir).resolve(), str(plan["upload_key_sha256"]))
    journal = read_json(stable_journal)
    release = _release_from_journal(journal, plan=plan)
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded current-main YouTube release operations.")
    sub = root.add_subparsers(dest="command", required=True)

    adoption = sub.add_parser("adopt-existing")
    adoption.add_argument("--evidence", required=True)
    adoption.add_argument("--data-dir", required=True)
    adoption.add_argument("--output", required=True)
    adoption.set_defaults(func=adopt_existing)

    plan = sub.add_parser("prepare-plan")
    plan.add_argument("--intent", required=True)
    plan.add_argument("--output", required=True)
    plan.add_argument("--thumbnail")
    plan.add_argument("--playlist", action="append", default=[])
    plan.add_argument("--final-privacy", choices=("private", "unlisted", "public"), default="public")
    plan.add_argument("--comment-file")
    plan.add_argument("--manual-pin", action="store_true")
    plan.set_defaults(func=prepare_plan)

    initialize = sub.add_parser("initialize")
    initialize.add_argument("--plan", required=True)
    initialize.add_argument("--data-dir", required=True)
    initialize.add_argument("--output", required=True)
    initialize.add_argument("--intent")
    initialize.add_argument("--absence-evidence")
    initialize.set_defaults(func=initialize_release)

    execute = sub.add_parser("execute-next")
    execute.add_argument("--plan", required=True)
    execute.add_argument("--approval", required=True)
    execute.add_argument("--data-dir", required=True)
    execute.add_argument("--execute", action="store_true")
    execute.set_defaults(func=execute_next)

    recovery = sub.add_parser("reconcile")
    recovery.add_argument("--plan", required=True)
    recovery.add_argument("--data-dir", required=True)
    recovery.set_defaults(func=reconcile)

    manual = sub.add_parser("record-manual-evidence")
    manual.add_argument("--plan", required=True)
    manual.add_argument("--data-dir", required=True)
    manual.add_argument("--child", required=True)
    manual.add_argument("--evidence", required=True)
    manual.set_defaults(func=record_manual_evidence)

    show = sub.add_parser("status")
    show.add_argument("--plan", required=True)
    show.add_argument("--data-dir", required=True)
    show.set_defaults(func=status)
    return root


def run() -> None:
    args = parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except (OSError, ValueError, UploadPlanError, YouTubeReleaseStateError, YouTubeReleaseProviderError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    run()
