#!/usr/bin/env python3
"""Prepare an immutable Wave handoff for the Lord God Charnock VK series.

Consumes the provider-inert post list built by
``build_lord_god_charnock_vk_posts.py`` and emits the same handoff layout
as ``prepare_lord_god_content_wave.py`` (00-08 + manifest), so the guarded
GitHub Actions prepare/apply stages verify and apply it unchanged. Posts
run Monday-Friday at 13:00 Europe/Moscow from ``--start-date``. Posts are
text-only: the community access key cannot upload wall photos
(``photos.getWallUploadServer`` is unavailable with group auth, VK
error 27, live-proven in apply run 40197033579); covers remain bound as
source evidence only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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

MOSCOW = ZoneInfo("Europe/Moscow")
PUBLISH_TIME = time(13, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--posts", type=Path, required=True)
    parser.add_argument("--article-queue", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--enable-provider-writes", action="store_true")
    return parser.parse_args()


def canonical_sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_guid(*parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return "vcm-lgw-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:28]


def schedule_dates(start: date, count: int) -> list[int]:
    epochs: list[int] = []
    cursor = start
    while len(epochs) < count:
        if cursor.weekday() < 5:
            moment = datetime.combine(cursor, PUBLISH_TIME, tzinfo=MOSCOW)
            epochs.append(int(moment.timestamp()))
        cursor += timedelta(days=1)
    return epochs


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repository_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.relative_to(root)
    if output_dir.exists():
        raise ValueError("output directory already exists; immutable handoff will not be overwritten")
    output_dir.mkdir(parents=True)

    posts_payload = json.loads(args.posts.read_text(encoding="utf-8-sig"))
    if posts_payload.get("schema_name") != "video-manager.lord-god-charnock-vk-posts":
        raise ValueError("unexpected Charnock VK posts schema")
    posts = posts_payload.get("posts")
    if not isinstance(posts, list) or not posts:
        raise ValueError("Charnock VK posts list is empty")

    backlog_copy = output_dir / "00-backlog.json"
    videos_copy = output_dir / "01-videos.json"
    queue_copy = output_dir / "02-telegram-quote-queue.json"
    covers_copy = output_dir / "03-telegram-quote-ledger.json"
    sources_copy = output_dir / "04-telegram-historical-release.json"
    schedule_copy = output_dir / "05-telegram-historical-ledger.json"
    shutil.copy2(args.posts.resolve(), backlog_copy)
    videos_copy.write_text("[]\n", encoding="utf-8")
    shutil.copy2((root / args.article_queue).resolve(), queue_copy)

    covers: dict[str, str] = {}
    sources: list[dict[str, Any]] = []
    for article in posts_payload.get("articles", []):
        cover_rel = str(article["cover_path"])
        cover_file = root / cover_rel
        digest = "sha256:" + hashlib.sha256(cover_file.read_bytes()).hexdigest()
        if digest != article["cover_sha256"]:
            raise ValueError(f"cover digest drift: {cover_rel}")
        covers[cover_rel] = digest
        md_rel = str(article["source_markdown"])
        md_digest = "sha256:" + hashlib.sha256((root / md_rel).read_bytes()).hexdigest()
        if md_digest != article["source_markdown_sha256"]:
            raise ValueError(f"article markdown digest drift: {md_rel}")
        sources.append(
            {
                "publication_id": article["publication_id"],
                "title": article["title"],
                "source_markdown": md_rel,
                "source_markdown_sha256": md_digest,
                "cover_path": cover_rel,
                "cover_sha256": digest,
                "parts": article["parts"],
            }
        )
    write_json_atomic(covers_copy, {"covers": covers})
    write_json_atomic(sources_copy, {"articles": sources})

    epochs = schedule_dates(args.start_date, len(posts))
    schedule: list[dict[str, Any]] = []
    specs: list[WaveOperationSpec] = []
    for post, publish_date in zip(posts, epochs, strict=True):
        message = str(post["message"])
        if canonical_sha(message) != post["message_sha256"]:
            raise ValueError(f"message digest drift: {post['source_id']}")
        if len(message) > 15_000:
            raise ValueError(f"message exceeds the VK wall limit: {post['source_id']}")
        payload: dict[str, Any] = {
            "content_kind": "text",
            "account_alias": LORD_GOD_ACCOUNT_ALIAS,
            "message": message,
            "message_sha256": post["message_sha256"],
            "publish_date": publish_date,
            "guid": deterministic_guid("charnock", post["source_id"], publish_date, post["message_sha256"]),
            "source_id": post["source_id"],
        }
        # Covers are recorded as evidence but are NOT attached: the
        # community access key cannot upload wall photos (VK error 27 on
        # photos.getWallUploadServer, live-proven in apply 40197033579).
        schedule.append({"source_id": post["source_id"], "publish_date": publish_date})
        specs.append(
            WaveOperationSpec(
                order_key=f"{publish_date:010d}-{post['source_id']}",
                operation_kind=LORD_GOD_WALL_OPERATION_KIND,
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload=payload,
            )
        )
    write_json_atomic(schedule_copy, {"start_date": args.start_date.isoformat(), "slots": schedule})

    project = ProjectBinding(
        project_key=LORD_GOD_PROJECT_KEY,
        community_id=LORD_GOD_COMMUNITY_ID,
        owner_id=LORD_GOD_OWNER_ID,
    )
    evidence_files = (backlog_copy, videos_copy, queue_copy, covers_copy, sources_copy, schedule_copy)
    source = WaveSourceEvidence.build(
        project=project,
        policy_version=LORD_GOD_WALL_POLICY_VERSION,
        artifacts=tuple(
            EvidenceArtifact(path=path.resolve().relative_to(root).as_posix(), sha256=file_sha256(path))
            for path in evidence_files
        ),
    )
    plan = WavePlan.build(source=source, specs=tuple(specs))

    source_path = output_dir / "06-source.json"
    plan_path = output_dir / "07-plan.json"
    intent_path = output_dir / "08-apply-intent.json"
    write_json_atomic(source_path, source.model_dump(mode="json"))
    write_json_atomic(plan_path, plan.model_dump(mode="json"))
    intent = WaveApplyIntent.build(
        source=source,
        source_path=source_path.resolve().relative_to(root).as_posix(),
        source_file_sha256=file_sha256(source_path),
        plan=plan,
        plan_path=plan_path.resolve().relative_to(root).as_posix(),
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
        "files": {path.name: file_sha256(path) for path in (*evidence_files, source_path, plan_path, intent_path)},
    }
    write_json_atomic(output_dir / "manifest.json", manifest)
    return manifest


def main() -> int:
    args = parse_args()
    manifest = prepare(args)
    print(
        "Prepared Lord God Charnock handoff: "
        f"operations={manifest['operation_count']} digest={manifest['plan_self_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
