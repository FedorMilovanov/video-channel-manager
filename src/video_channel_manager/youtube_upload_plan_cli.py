from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from video_channel_manager.youtube_release_state import build_release_state, mark_existing_target_adopted
from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    abandon_planned_journal,
    adopted_journal,
    build_intent,
    canonical_sha256,
    journal_path,
    planned_journal,
    require_adoption_allowed,
    require_new_plan_allowed,
    validate_intent,
    validate_journal,
    validate_live_state_evidence,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadPlanError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UploadPlanError(f"Expected JSON object: {path}")
    return payload


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable intent evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def _stable_key_mutation_lock(stable_journal: Path) -> Iterator[Path]:
    lock_path = stable_journal.with_suffix(stable_journal.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("x", encoding="utf-8") as handle:
            handle.write("local upload-plan mutation in progress\n")
    except FileExistsError as exc:
        raise UploadPlanError(
            f"Stable upload identity is already locked: {lock_path}. "
            "Inspect the existing journal/lock; do not bypass concurrent or interrupted mutation."
        ) from exc
    try:
        yield lock_path
    finally:
        lock_path.unlink(missing_ok=True)


def plan(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec).resolve()
    media_path = Path(args.video).resolve()
    data_dir = Path(args.data_dir).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable intent evidence: {output}")

    spec = _read_json(spec_path)
    intent = build_intent(spec, media_path)
    stable_journal = journal_path(data_dir, str(intent["upload_key_sha256"]))
    with _stable_key_mutation_lock(stable_journal):
        existing = _read_json(stable_journal) if stable_journal.is_file() else None
        require_new_plan_allowed(existing, intent=intent)
        _write_new_json(output, intent)
        try:
            _write_json_atomic(stable_journal, planned_journal(intent))
        except OSError:
            output.unlink(missing_ok=True)
            raise

    print("YOUTUBE UPLOAD PLAN READY — LOCAL ONLY; PROVIDER EXECUTION UNAVAILABLE.")
    print(f"Project: {intent['project_key']}")
    print(f"Channel: {intent['target_channel_id']}")
    print(f"Media SHA: {intent['media_sha256']}")
    print(f"Stable upload key: {intent['upload_key_sha256']}")
    print(f"Intent: {intent['intent_sha256']}")
    print(f"Journal: {stable_journal}")
    print(f"OPEN/SEND THIS FILE: {output}")
    return 0


def _load_intent(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    intent = _read_json(Path(args.intent).resolve())
    validate_intent(intent)
    stable_journal = journal_path(Path(args.data_dir).resolve(), str(intent["upload_key_sha256"]))
    return intent, stable_journal


def _read_matching_journal(stable_journal: Path, *, intent: dict[str, Any]) -> dict[str, Any]:
    if not stable_journal.is_file():
        raise UploadPlanError("No durable journal exists for this project/channel/media identity.")
    journal = _read_json(stable_journal)
    validate_journal(journal, intent=intent)
    return journal


def status(args: argparse.Namespace) -> int:
    intent, stable_journal = _load_intent(args)
    journal = _read_matching_journal(stable_journal, intent=intent)
    print(json.dumps(journal, ensure_ascii=False, indent=2))
    return 0


def abandon(args: argparse.Namespace) -> int:
    intent, stable_journal = _load_intent(args)
    with _stable_key_mutation_lock(stable_journal):
        journal = _read_matching_journal(stable_journal, intent=intent)
        updated = abandon_planned_journal(journal, intent=intent)
        _write_json_atomic(stable_journal, updated)
    print("LOCAL UPLOAD PLAN ABANDONED — PROVIDER EFFECT CONFIRMED ABSENT.")
    print(f"Stable upload key: {intent['upload_key_sha256']}")
    return 0


def _build_readonly_client(account_alias: str):
    """Load local OAuth material only after canonical project identity has already passed."""

    from video_channel_manager.config import get_settings
    from video_channel_manager.platforms.youtube import InstalledClientConfig, TokenStore, YouTubeApiClient

    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    return YouTubeApiClient(client_config=config, token_store=store, account_alias=account_alias)


def _verify_remote_against_evidence(*, evidence: dict[str, Any], remote) -> None:
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

    evidence = _read_json(evidence_path)
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

    with _stable_key_mutation_lock(stable_journal):
        current = _read_json(stable_journal) if stable_journal.is_file() else None
        write_needed = require_adoption_allowed(current, proposed=proposed)
        if write_needed:
            _write_json_atomic(stable_journal, proposed)
            durable = proposed
        else:
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
    _write_new_json(output, result)
    print("YOUTUBE EXISTING TARGET ADOPTED — READ ONLY; PROVIDER WRITES 0.")
    print(f"Video ID: {remote.ref.remote_id}")
    print(f"Stable upload key: {identity['upload_key_sha256']}")
    print(f"Journal: {stable_journal}")
    print(f"OPEN/SEND THIS FILE: {output}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded YouTube stable-key planning and read-only adoption.")
    sub = root.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--spec", required=True)
    p.add_argument("--video", required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=plan)

    for name, handler in (("status", status), ("abandon", abandon)):
        command = sub.add_parser(name)
        command.add_argument("--intent", required=True)
        command.add_argument("--data-dir", required=True)
        command.set_defaults(func=handler)

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
