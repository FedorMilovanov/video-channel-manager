from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from video_channel_manager.youtube_release_plan import (
    build_release_plan,
    load_json_object,
    validate_absence_evidence,
    validate_release_plan,
)
from video_channel_manager.youtube_release_state import (
    build_release_state,
    child_by_id,
    mark_existing_target_absent,
    mark_existing_target_adopted,
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


def build_readonly_client(account_alias: str) -> ReadOnlyYouTubeClient:
    """Load OAuth material only after the caller proves canonical project identity."""

    from video_channel_manager.config import get_settings
    from video_channel_manager.platforms.youtube import (
        InstalledClientConfig,
        TokenStore,
        YouTubeApiClient,
    )

    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    return YouTubeApiClient(
        client_config=config,
        token_store=store,
        account_alias=account_alias,
    )


def verify_remote_against_evidence(
    *,
    evidence: dict[str, Any],
    remote: ReadOnlyVideo,
) -> None:
    video = evidence.get("video")
    if not isinstance(video, dict):
        raise UploadPlanError("Live-state evidence video object is required.")
    expected_title = video.get("title")
    if isinstance(expected_title, str) and expected_title and remote.title != expected_title:
        raise UploadPlanError("Provider video title does not match immutable live-state evidence.")
    expected_privacy = video.get("privacy_status")
    if isinstance(expected_privacy, str) and expected_privacy and remote.privacy_status != expected_privacy:
        raise UploadPlanError(
            f"Provider privacy mismatch: evidence={expected_privacy} provider={remote.privacy_status}."
        )


def adopt_existing(
    args: argparse.Namespace,
    *,
    client_builder=build_readonly_client,
) -> int:
    evidence_path = Path(args.evidence).resolve()
    data_dir = Path(args.data_dir).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable adoption evidence: {output}")

    evidence = read_json(evidence_path)
    identity = validate_live_state_evidence(evidence)
    # Canonical identity is proven above before client/config/token material is loaded.
    client = client_builder(identity["account_alias"])
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
    verify_remote_against_evidence(evidence=evidence, remote=remote)

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


def release_from_journal(
    journal: dict[str, Any],
    *,
    plan: dict[str, Any],
) -> dict[str, Any]:
    release = journal.get("release")
    if not isinstance(release, dict):
        raise UploadPlanError("Stable journal has no initialized release state.")
    validate_release_state(release)
    if release.get("release_plan_sha256") != plan.get("release_plan_sha256"):
        raise UploadPlanError("Release state does not bind the exact release plan.")
    if release.get("upload_key_sha256") != plan.get("upload_key_sha256"):
        raise UploadPlanError("Release state stable identity differs from release plan.")
    return release


def video_id_from_release(journal: dict[str, Any], release: dict[str, Any]) -> str:
    upload = child_by_id(release, "upload")
    value = str(upload.get("remote_id") or journal.get("remote_video_id") or "").strip()
    if not value:
        raise UploadPlanError("Release has no verified provider video ID yet.")
    return value


def persist_release(
    stable_journal: Path,
    journal: dict[str, Any],
    release: dict[str, Any],
) -> None:
    journal["release"] = release
    write_json_atomic(stable_journal, journal)


def initialize_release(args: argparse.Namespace) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    stable_journal = journal_path(
        Path(args.data_dir).resolve(),
        str(plan["upload_key_sha256"]),
    )
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
            release = build_release_state(
                upload_key_sha256=str(plan["upload_key_sha256"]),
                release_plan_sha256=str(plan["release_plan_sha256"]),
                playlist_ids=[str(item) for item in plan["playlist_ids"]],
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
        "existing_target_mode": ("adopted" if journal.get("adopted_existing_target") else "confirmed_absent"),
        "existing_target_absence_evidence_sha256": absence_sha,
        "provider_writes": 0,
        "journal_path": str(stable_journal),
    }
    write_new_json(output, result)
    print("YOUTUBE RELEASE STATE INITIALIZED — PROVIDER WRITES 0.")
    return 0


def record_manual_evidence(args: argparse.Namespace) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    stable_journal = journal_path(
        Path(args.data_dir).resolve(),
        str(plan["upload_key_sha256"]),
    )
    evidence = load_json_object(Path(args.evidence).resolve())
    child_id = str(args.child)
    if child_id not in {"manual-pin-evidence", "metadata-status", "thumbnail"}:
        raise UploadPlanError(f"Manual evidence is not allowed for release child {child_id}.")
    if evidence.get("release_plan_sha256") != plan["release_plan_sha256"]:
        raise UploadPlanError("Manual evidence does not bind the exact release plan.")
    if evidence.get("child_id") != child_id or evidence.get("provider_effect") != "verified":
        raise UploadPlanError("Manual evidence must bind the exact child with provider_effect=verified.")
    if not str(evidence.get("reviewed_by") or "").strip() or not str(evidence.get("reviewed_at") or "").strip():
        raise UploadPlanError("Manual evidence requires reviewed_by and reviewed_at.")

    with stable_key_mutation_lock(stable_journal):
        journal = read_json(stable_journal)
        release = release_from_journal(journal, plan=plan)
        child = child_by_id(release, child_id)
        if child.get("payload_sha256") is None:
            video_id = video_id_from_release(journal, release)
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
        persist_release(stable_journal, journal, release)
    print(f"MANUAL YOUTUBE RELEASE EVIDENCE RECORDED FOR {child_id}; PROVIDER WRITES 0.")
    return 0


def status(args: argparse.Namespace) -> int:
    plan = load_json_object(Path(args.plan).resolve())
    validate_release_plan(plan, verify_files=False)
    stable_journal = journal_path(
        Path(args.data_dir).resolve(),
        str(plan["upload_key_sha256"]),
    )
    journal = read_json(stable_journal)
    release = release_from_journal(journal, plan=plan)
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0
