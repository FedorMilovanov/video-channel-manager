from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from video_channel_manager.youtube_release_state import build_release_state, mark_existing_target_adopted
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


def _build_readonly_client(account_alias: str) -> ReadOnlyYouTubeClient:
    """Load OAuth material only after canonical project identity has passed."""

    from video_channel_manager.config import get_settings
    from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore, YouTubeApiClient

    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    return YouTubeApiClient(client_config=config, token_store=store, account_alias=account_alias)


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


def _verify_existing_journal_for_adoption(
    current: dict[str, Any] | None,
    *,
    proposed: dict[str, Any],
) -> None:
    if current is None:
        return
    if current.get("account_alias") != proposed.get("account_alias"):
        raise UploadPlanError("Existing stable upload journal OAuth alias conflicts with adoption evidence.")
    if current.get("adopted_existing_target") is True and current.get("remote_video_id") == proposed.get(
        "remote_video_id"
    ):
        if current.get("remote_revision") != proposed.get("remote_revision"):
            raise UploadPlanError(
                "Existing stable upload journal conflicts with existing-target adoption: provider revision drift."
            )
        if current.get("adoption_evidence_sha256") != proposed.get("adoption_evidence_sha256"):
            raise UploadPlanError(
                "Existing stable upload journal was adopted from different immutable evidence; refusing silent rebinding."
            )


def adopt_existing(args: argparse.Namespace) -> int:
    evidence_path = Path(args.evidence).resolve()
    data_dir = Path(args.data_dir).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable adoption evidence: {output}")

    evidence = read_json(evidence_path)
    identity = validate_live_state_evidence(evidence)
    # Identity validation above is intentionally before any client-secret/token access.
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
    release = build_release_state(upload_key_sha256=identity["upload_key_sha256"])
    proposed["release"] = mark_existing_target_adopted(
        release,
        video_id=remote.ref.remote_id,
        remote_revision=remote.revision,
        evidence=evidence,
    )
    stable_journal = journal_path(data_dir, identity["upload_key_sha256"])

    with stable_key_mutation_lock(stable_journal):
        current = read_json(stable_journal) if stable_journal.is_file() else None
        _verify_existing_journal_for_adoption(current, proposed=proposed)
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
        "schema_version": 1,
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
    print(f"OPEN/SEND THIS FILE: {output}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded current-main YouTube release state operations.")
    sub = root.add_subparsers(dest="command", required=True)
    adoption = sub.add_parser("adopt-existing")
    adoption.add_argument("--evidence", required=True)
    adoption.add_argument("--data-dir", required=True)
    adoption.add_argument("--output", required=True)
    adoption.set_defaults(func=adopt_existing)
    return root


def run() -> None:
    args = parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except (OSError, ValueError, UploadPlanError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    run()
