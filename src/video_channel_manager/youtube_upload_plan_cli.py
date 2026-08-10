from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.youtube_stable_state import (
    read_json,
    stable_key_mutation_lock,
    write_json_atomic as _write_json_atomic,
    write_new_json,
)
from video_channel_manager.youtube_upload_plan import (
    UploadPlanError,
    abandon_planned_journal,
    build_intent,
    journal_path,
    planned_journal,
    require_new_plan_allowed,
    validate_intent,
    validate_journal,
)


def plan(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec).resolve()
    media_path = Path(args.video).resolve()
    data_dir = Path(args.data_dir).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable intent evidence: {output}")

    spec = read_json(spec_path)
    intent = build_intent(spec, media_path)
    stable_journal = journal_path(data_dir, str(intent["upload_key_sha256"]))
    with stable_key_mutation_lock(stable_journal):
        existing = read_json(stable_journal) if stable_journal.is_file() else None
        require_new_plan_allowed(existing, intent=intent)
        write_new_json(output, intent)
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
    intent = read_json(Path(args.intent).resolve())
    validate_intent(intent)
    stable_journal = journal_path(Path(args.data_dir).resolve(), str(intent["upload_key_sha256"]))
    return intent, stable_journal


def _read_matching_journal(stable_journal: Path, *, intent: dict[str, Any]) -> dict[str, Any]:
    if not stable_journal.is_file():
        raise UploadPlanError("No durable journal exists for this project/channel/media identity.")
    journal = read_json(stable_journal)
    validate_journal(journal, intent=intent)
    return journal


def status(args: argparse.Namespace) -> int:
    intent, stable_journal = _load_intent(args)
    journal = _read_matching_journal(stable_journal, intent=intent)
    print(json.dumps(journal, ensure_ascii=False, indent=2))
    return 0


def abandon(args: argparse.Namespace) -> int:
    intent, stable_journal = _load_intent(args)
    with stable_key_mutation_lock(stable_journal):
        journal = _read_matching_journal(stable_journal, intent=intent)
        updated = abandon_planned_journal(journal, intent=intent)
        _write_json_atomic(stable_journal, updated)
    print("LOCAL UPLOAD PLAN ABANDONED — PROVIDER EFFECT CONFIRMED ABSENT.")
    print(f"Stable upload key: {intent['upload_key_sha256']}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Local-only YouTube upload stable-key planner.")
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
