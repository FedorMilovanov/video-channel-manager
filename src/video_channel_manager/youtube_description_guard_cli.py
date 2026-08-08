from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.editorial import validate_youtube_description
from video_channel_manager.platforms.youtube import (
    InstalledClientConfig,
    TokenStore,
    YOUTUBE_FORCE_SSL_SCOPE,
    YouTubeDescriptionWriter,
    descriptions_equivalent,
)
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock

SCHEMA_NAME = "video-manager.youtube-description-exact-plan"
SCHEMA_VERSION = 1


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _plan_digest(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "plan_sha256"}
    return _sha256_bytes(_canonical_json(unsigned))


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite immutable evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _writer(account: str) -> tuple[TokenStore, YouTubeDescriptionWriter]:
    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    writer = YouTubeDescriptionWriter(client_config=config, token_store=store, account_alias=account)
    return store, writer


def _validate_description(text: str) -> None:
    findings = validate_youtube_description(text)
    errors = [item for item in findings if item.severity == "error"]
    for item in findings:
        print(f"LINT {item.severity.upper()} {item.code}: {item.message}")
    if errors:
        raise ValueError(f"Description lint failed with {len(errors)} error(s).")


def _load_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Plan JSON must be an object.")
    if payload.get("schema_name") != SCHEMA_NAME or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported exact-description plan schema.")
    actual = str(payload.get("plan_sha256") or "")
    expected = _plan_digest(payload)
    if actual != expected:
        raise ValueError(f"Plan digest mismatch: expected {expected}, got {actual}")
    return payload


def plan(args: argparse.Namespace) -> int:
    os.chdir(args.repo)
    description_path = Path(args.description).resolve()
    output = Path(args.output).resolve()
    after = description_path.read_text(encoding="utf-8")
    _validate_description(after)

    _, writer = _writer(args.account)
    current = writer.read_description(args.video)
    if current.channel_id != args.channel:
        raise ValueError(f"Target channel mismatch: expected {args.channel}, got {current.channel_id}")

    payload: dict[str, Any] = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "account_alias": args.account,
        "target_channel_id": args.channel,
        "video_id": args.video,
        "title_at_plan": current.title,
        "source_description_path": str(description_path),
        "source_description_sha256": _sha256_text(after),
        "before_revision": current.revision,
        "before_description": current.description,
        "before_description_sha256": _sha256_text(current.description),
        "after_description": after,
        "after_description_sha256": _sha256_text(after),
        "writes": ["snippet.description"],
        "preserve": ["snippet.title", "snippet.tags", "snippet.categoryId", "status", "thumbnail", "playlists"],
    }
    payload["plan_sha256"] = _plan_digest(payload)
    _write_new_json(output, payload)
    print("YOUTUBE DESCRIPTION PLAN READY — NO PROVIDER WRITE.")
    print(f"Channel: {args.channel}")
    print(f"Video: {args.video}")
    print(f"Title: {current.title}")
    print(f"Before SHA: {payload['before_description_sha256']}")
    print(f"After SHA: {payload['after_description_sha256']}")
    print(f"Plan: {payload['plan_sha256']}")
    print(f"Authorization phrase: YTDESC:{payload['plan_sha256']}")
    print(f"OPEN/SEND THIS FILE: {output}")
    return 0


def execute(args: argparse.Namespace) -> int:
    os.chdir(args.repo)
    plan_path = Path(args.plan).resolve()
    payload = _load_plan(plan_path)
    expected_phrase = f"YTDESC:{payload['plan_sha256']}"
    if args.confirm != expected_phrase:
        raise ValueError("Execution confirmation does not match this immutable plan.")

    after = str(payload["after_description"])
    before = str(payload["before_description"])
    _validate_description(after)

    store, writer = _writer(str(payload["account_alias"]))
    token = store.load_token(str(payload["account_alias"]))
    if YOUTUBE_FORCE_SSL_SCOPE not in token.scopes:
        raise ValueError("Stored OAuth token does not have guarded write scope.")

    settings = get_settings()
    channel = str(payload["target_channel_id"])
    video = str(payload["video_id"])
    lock_path = settings.data_dir / "locks" / f"youtube-{payload['account_alias']}-{channel}.lock"

    with local_youtube_write_lock(lock_path, account=str(payload["account_alias"]), channel_id=channel):
        current = writer.read_description(video)
        if current.channel_id != channel:
            raise ValueError(f"Live channel mismatch: expected {channel}, got {current.channel_id}")
        if descriptions_equivalent(current.description, after):
            print("DESCRIPTION ALREADY APPLIED — NO PROVIDER WRITE.")
            print(f"Video: {video}")
            return 0
        if not descriptions_equivalent(current.description, before):
            raise ValueError("Live description matches neither immutable before-state nor after-state; refusing overwrite.")

        verified = writer.replace_description(
            video_id=video,
            expected_channel_id=channel,
            expected_revision=str(payload["before_revision"]),
            expected_description=before,
            new_description=after,
        )

        if not descriptions_equivalent(verified.description, after):
            raise ValueError("Post-write description readback mismatch.")

    result = {
        "schema_name": "video-manager.youtube-description-exact-result",
        "schema_version": 1,
        "finished_at": datetime.now(UTC).isoformat(),
        "plan_sha256": payload["plan_sha256"],
        "target_channel_id": channel,
        "video_id": video,
        "title": verified.title,
        "after_description_sha256": _sha256_text(verified.description),
        "verified": True,
        "provider_effect": "description_updated",
    }
    result_path = Path(args.result).resolve()
    _write_new_json(result_path, result)
    print("YOUTUBE DESCRIPTION UPDATED AND VERIFIED.")
    print(f"Video: {video}")
    print(f"Result: {result_path}")
    print("Only snippet.description was intentionally changed; title/tags/category were preserved from live state.")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded exact-target YouTube description plan/apply workflow.")
    sub = root.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--repo", required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--channel", required=True)
    p.add_argument("--video", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=plan)

    e = sub.add_parser("execute")
    e.add_argument("--repo", required=True)
    e.add_argument("--plan", required=True)
    e.add_argument("--confirm", required=True)
    e.add_argument("--result", required=True)
    e.set_defaults(func=execute)
    return root


def run() -> None:
    args = parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    run()
