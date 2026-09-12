#!/usr/bin/env python3
"""Prepare an immutable Wave 6 handoff for Lord God VK postponed content."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.telegram_models import TelegramLedger, TelegramQueue
from video_channel_manager.wave_engine.canonical import file_sha256, write_json_atomic
from video_channel_manager.wave_engine.models import (
    EvidenceArtifact,
    MutationClass,
    ProjectBinding,
    WaveApplyIntent,
    WaveOperationSpec,
    WavePlan,
    WaveSourceEvidence,
)
from video_channel_manager.wave_engine.vk_lord_god_wall_provider import (
    LORD_GOD_ACCOUNT_ALIAS,
    LORD_GOD_COMMUNITY_ID,
    LORD_GOD_OWNER_ID,
    LORD_GOD_PROJECT_KEY,
    LORD_GOD_WALL_OPERATION_KIND,
    LORD_GOD_WALL_POLICY_VERSION,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--backlog", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--quote-queue", type=Path, required=True)
    parser.add_argument("--quote-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--enable-provider-writes", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_guid(*parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return "vcm-lgw-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:28]


def repository_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def build_video_index(videos: list[object]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in videos:
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        if not isinstance(ref, dict):
            continue
        remote_id = str(ref.get("remote_id") or "")
        if remote_id:
            index[remote_id] = item
    return index


def title_key(value: object) -> str:
    return " ".join(canonical_vk_text(str(value or "")).split())


def video_message(title: str) -> str:
    return canonical_vk_text(
        f"🎬 {title}\n\n"
        "▶ Смотреть видео — во вложении.\n\n"
        "🌐 https://gospod-bog.ru/\n"
        "📨 https://t.me/lordchrist\n"
        "🎬 https://vkvideo.ru/@the_lord_god_is_my_strength\n\n"
        "#ГосподьБогСилаМоя"
    )


def text_message(slot: dict[str, Any]) -> str:
    text = canonical_vk_text(str(slot.get("text") or ""))
    if not text:
        raise ValueError("text backlog slot has an empty message")
    source_url = canonical_vk_text(str(slot.get("source_url") or ""))
    suffix = "\n\n🌐 https://gospod-bog.ru/\n📨 https://t.me/lordchrist"
    if source_url:
        suffix = f"\n\nПервоисточник: {source_url}" + suffix
    return canonical_vk_text(text + suffix)


def verify_quote_slots(
    backlog: dict[str, Any],
    queue: TelegramQueue,
    ledger: TelegramLedger,
) -> None:
    if backlog.get("telegram_quote_queue_digest") != queue.digest:
        raise ValueError("Telegram quote queue digest differs from the backlog evidence")
    if ledger.queue_digest != queue.digest:
        raise ValueError("Telegram quote ledger is not bound to the immutable queue")
    posts = {post.publication_id: post for post in queue.posts}
    for slot in backlog.get("slots", []):
        if not isinstance(slot, dict) or slot.get("kind") != "telegram_quote":
            continue
        publication_id = str(slot.get("publication_id") or "")
        post = posts.get(publication_id)
        entry = ledger.entries.get(publication_id)
        if post is None or entry is None:
            raise ValueError(f"Telegram quote evidence is missing: {publication_id}")
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"Telegram quote ledger payload drift: {publication_id}")
        if slot.get("telegram_payload_sha256") != entry.payload_sha256:
            raise ValueError(f"Telegram quote backlog payload drift: {publication_id}")
        if entry.state != "published" or entry.provider_effect != "verified":
            raise ValueError(f"Telegram quote was not published+verified: {publication_id}")
        if slot.get("telegram_message_id") != entry.message_id:
            raise ValueError(f"Telegram quote message_id mismatch: {publication_id}")
        if slot.get("telegram_message_url") != entry.message_url:
            raise ValueError(f"Telegram quote message_url mismatch: {publication_id}")


def build_specs(backlog: dict[str, Any], videos: dict[str, dict[str, Any]]) -> tuple[WaveOperationSpec, ...]:
    if backlog.get("project_key") != LORD_GOD_PROJECT_KEY:
        raise ValueError("backlog project_key mismatch")
    if backlog.get("community_id") != LORD_GOD_COMMUNITY_ID or backlog.get("owner_id") != LORD_GOD_OWNER_ID:
        raise ValueError("backlog community/owner mismatch")
    if backlog.get("mode") != "provider-inert" or backlog.get("live_revalidation_required") is not True:
        raise ValueError("backlog must be provider-inert and require live revalidation")

    slots = backlog.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("backlog slots must be a non-empty list")
    specs: list[WaveOperationSpec] = []
    seen_dates: set[int] = set()
    for slot in slots:
        if not isinstance(slot, dict):
            raise ValueError("backlog slot must be an object")
        publish_date = slot.get("publish_date")
        if type(publish_date) is not int or publish_date <= 0 or publish_date in seen_dates:
            raise ValueError("backlog publish_date values must be positive and unique")
        seen_dates.add(publish_date)
        kind = str(slot.get("kind") or "")
        if kind == "vk_video":
            remote_id = str(slot.get("video_id") or "")
            video = videos.get(remote_id)
            if video is None:
                raise ValueError(f"video snapshot lacks backlog candidate {remote_id}")
            expected_title = canonical_vk_text(str(video.get("title") or ""))
            display_title = canonical_vk_text(str(slot.get("title") or ""))
            if not expected_title or title_key(expected_title) != title_key(display_title):
                raise ValueError(f"video title mismatch for {remote_id}")
            description = canonical_vk_text(str(video.get("description") or ""))
            owner_text, separator, id_text = remote_id.partition("_")
            if not separator or int(owner_text) != LORD_GOD_OWNER_ID or int(id_text) <= 0:
                raise ValueError(f"invalid Lord God video identity: {remote_id}")
            message = video_message(display_title)
            payload = {
                "content_kind": "video",
                "account_alias": LORD_GOD_ACCOUNT_ALIAS,
                "message": message,
                "message_sha256": canonical_sha(message),
                "publish_date": publish_date,
                "guid": deterministic_guid(kind, remote_id, publish_date, canonical_sha(message)),
                "source_id": remote_id,
                "video_owner_id": LORD_GOD_OWNER_ID,
                "video_id": int(id_text),
                "video_remote_id": remote_id,
                "expected_video_title": expected_title,
                "expected_video_description_sha256": canonical_sha(description),
            }
            source_id = remote_id
        elif kind in {"telegram_quote", "telegram_editorial"}:
            publication_id = str(slot.get("publication_id") or "")
            if not publication_id:
                raise ValueError("text slot lacks publication_id")
            message = text_message(slot)
            payload = {
                "content_kind": "text",
                "account_alias": LORD_GOD_ACCOUNT_ALIAS,
                "message": message,
                "message_sha256": canonical_sha(message),
                "publish_date": publish_date,
                "guid": deterministic_guid(kind, publication_id, publish_date, canonical_sha(message)),
                "source_id": publication_id,
            }
            source_id = publication_id
        else:
            raise ValueError(f"unsupported backlog kind: {kind}")
        specs.append(
            WaveOperationSpec(
                order_key=f"{publish_date:010d}-{kind}-{source_id}",
                operation_kind=LORD_GOD_WALL_OPERATION_KIND,
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload=payload,
            )
        )
    return tuple(specs)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repository_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.relative_to(root)
    if output_dir.exists():
        raise ValueError("output directory already exists; immutable handoff will not be overwritten")
    output_dir.mkdir(parents=True)

    backlog_copy = output_dir / "00-backlog.json"
    videos_copy = output_dir / "01-videos.json"
    quote_queue_copy = output_dir / "02-telegram-quote-queue.json"
    quote_ledger_copy = output_dir / "03-telegram-quote-ledger.json"
    shutil.copy2(args.backlog.resolve(), backlog_copy)
    shutil.copy2(args.videos.resolve(), videos_copy)
    shutil.copy2(args.quote_queue.resolve(), quote_queue_copy)
    shutil.copy2(args.quote_ledger.resolve(), quote_ledger_copy)

    backlog = read_json(backlog_copy)
    raw_videos = read_json(videos_copy)
    if not isinstance(backlog, dict) or not isinstance(raw_videos, list):
        raise ValueError("backlog/videos evidence has an invalid root type")
    if backlog.get("telegram_quote_queue_sha256") != file_sha256(quote_queue_copy):
        raise ValueError("Telegram quote queue SHA differs from the backlog evidence")
    if backlog.get("telegram_quote_ledger_sha256") != file_sha256(quote_ledger_copy):
        raise ValueError("Telegram quote ledger SHA differs from the backlog evidence")
    quote_queue = TelegramQueue.model_validate(read_json(quote_queue_copy))
    quote_ledger = TelegramLedger.model_validate(read_json(quote_ledger_copy))
    verify_quote_slots(backlog, quote_queue, quote_ledger)
    video_index = build_video_index(raw_videos)
    specs = build_specs(backlog, video_index)

    project = ProjectBinding(
        project_key=LORD_GOD_PROJECT_KEY,
        community_id=LORD_GOD_COMMUNITY_ID,
        owner_id=LORD_GOD_OWNER_ID,
    )
    source = WaveSourceEvidence.build(
        project=project,
        policy_version=LORD_GOD_WALL_POLICY_VERSION,
        artifacts=(
            EvidenceArtifact(path=repository_relative(root, backlog_copy), sha256=file_sha256(backlog_copy)),
            EvidenceArtifact(path=repository_relative(root, videos_copy), sha256=file_sha256(videos_copy)),
            EvidenceArtifact(path=repository_relative(root, quote_queue_copy), sha256=file_sha256(quote_queue_copy)),
            EvidenceArtifact(path=repository_relative(root, quote_ledger_copy), sha256=file_sha256(quote_ledger_copy)),
        ),
    )
    plan = WavePlan.build(source=source, specs=specs)


    source_path = output_dir / "04-source.json"
    plan_path = output_dir / "05-plan.json"
    intent_path = output_dir / "06-apply-intent.json"
    manifest_path = output_dir / "manifest.json"

    write_json_atomic(source_path, source.model_dump(mode="json"))
    write_json_atomic(plan_path, plan.model_dump(mode="json"))
    intent = WaveApplyIntent.build(
        source=source,
        source_path=repository_relative(root, source_path),
        source_file_sha256=file_sha256(source_path),
        plan=plan,
        plan_path=repository_relative(root, plan_path),
        plan_file_sha256=file_sha256(plan_path),
        enable_provider_writes=bool(args.enable_provider_writes),
    )
    write_json_atomic(intent_path, intent.model_dump(mode="json"))

    source.verify_artifacts(root)
    intent.assert_matches(plan, source)
    manifest = {
        "schema_name": "video-manager.lord-god-content-wave-handoff",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "project": project.model_dump(mode="json"),
        "policy_version": LORD_GOD_WALL_POLICY_VERSION,
        "operation_count": len(plan.operations),
        "operation_set_digest": plan.operation_set_digest,
        "source_self_digest": source.self_digest,
        "plan_self_digest": plan.self_digest,
        "apply_intent_self_digest": intent.self_digest,
        "enable_provider_writes": intent.enable_provider_writes,
        "files": {
            path.name: file_sha256(path)
            for path in (
                backlog_copy,
                videos_copy,
                quote_queue_copy,
                quote_ledger_copy,
                source_path,
                plan_path,
                intent_path,
            )
        },
    }
    write_json_atomic(manifest_path, manifest)
    return manifest


def main() -> int:
    args = parse_args()
    try:
        manifest = prepare(args)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(
        "Prepared Lord God Wave handoff: "
        f"operations={manifest['operation_count']} "
        f"provider_writes={manifest['enable_provider_writes']} "
        f"digest={manifest['operation_set_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
