from __future__ import annotations

import re
import statistics
from collections import Counter
from copy import deepcopy
from typing import Any

from video_channel_manager.platforms.vk.catalog import canonical_sha256, text_sha256
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

_URL_RE = re.compile(r"https?://[^\s]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё]+")
_BAD_POEM_MARKERS = (
    "Источник",
    "История создания",
    "Разбор образа",
    "Почему это важно",
    "Основные идеи",
    "Стихотворение стало",
    "Автор текста",
    "Хроника",
    "Плейлист",
    "Подписывайтесь",
    "The Legendary Poet",
)


def _paragraphs(text: str) -> list[str]:
    return [value.strip() for value in re.split(r"\n\s*\n", canonical_vk_text(text)) if value.strip()]


def _is_poem_block(value: str) -> bool:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    if any(_URL_RE.search(line) or _HASHTAG_RE.search(line) for line in lines):
        return False
    if any(any(marker.casefold() in line.casefold() for marker in _BAD_POEM_MARKERS) for line in lines[:5]):
        return False
    lengths = [len(line) for line in lines]
    short_ratio = sum(length <= 88 for length in lengths) / len(lines)
    colon_ratio = sum(":" in line for line in lines) / len(lines)
    bullet_ratio = sum(line.startswith(("➛", "•", "— ", "- ", "➡️", "▶")) for line in lines) / len(lines)
    return statistics.median(lengths) <= 68 and short_ratio >= 0.78 and colon_ratio < 0.18 and bullet_ratio < 0.20


def extract_poem_blocks(text: str) -> list[str]:
    result: list[str] = []
    for paragraph in _paragraphs(text):
        if _is_poem_block(paragraph) and paragraph not in result:
            result.append(paragraph)
    return result


def _hashtag(value: str) -> str:
    cleaned = re.sub(r"[^\wА-Яа-яЁё]", "", value, flags=re.UNICODE)
    return f"#{cleaned}" if cleaned else ""


def _canonical_hashtags(policy: dict[str, Any], target: dict[str, Any]) -> list[str]:
    work_name = str(policy["work_metadata"][target["work_key"]]["name"]).strip("«»")
    tags = ["#TheLegendaryPoet"]
    if target["format"] == "experiment":
        tags.extend(["#AIMusic", "#AICover", "#Эксперименты"])
    else:
        tags.extend(["#РусскаяПоэзия", "#ПоющиеПоэты", "#AIMusic"])
    tags.extend(str(value) for value in policy.get("author_hashtags", {}).get(target["author_key"], []))
    tags.append(_hashtag(work_name))
    if target["format"] == "short":
        tags.append("#Shorts")
    return list(dict.fromkeys(tag for tag in tags if tag))


def _video_url(remote_id: str) -> str:
    return f"https://vkvideo.ru/video{remote_id}"


def _collection_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["ref"]["remote_id"]): item for item in snapshot.get("collections", [])}


def _video_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["ref"]["remote_id"]): item for item in snapshot.get("videos", [])}


def _membership_pairs(snapshot: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(item["collection_ref"]["remote_id"]), str(item["video_ref"]["remote_id"]))
        for item in snapshot.get("memberships", [])
    }


def render_final_description(
    source_description: str,
    *,
    policy: dict[str, Any],
    target: dict[str, Any],
    collections: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    work = policy["work_metadata"][target["work_key"]]
    author_name = str(policy["author_names"][target["author_key"]])
    blocks: list[str] = [f"🎧 {work['name']} — {work['lead']}"]
    if target["format"] == "short":
        blocks.append("⚡ Это сокращённая версия музыкально-визуальной интерпретации.")
    elif target["format"] == "experiment":
        blocks.append("🎛️ Формат: самостоятельный музыкальный и визуальный эксперимент проекта The Legendary Poet.")
    else:
        blocks.append("🎼 Формат: музыкальная и визуальная интерпретация произведения.")

    full_version_id = target.get("full_version_video_id")
    if full_version_id:
        blocks.append(f"▶ Полная версия в VK: {_video_url(str(full_version_id))}")

    blocks.append(
        "📖 Редакционный принцип: факты, авторские свидетельства и литературная интерпретация "
        "не смешиваются. Биографические, психологические, медицинские, пророческие и духовные "
        "утверждения не выдаются за доказанные без прямого источника."
    )

    rights = target.get("rights")
    if isinstance(rights, dict):
        rights_lines = [f"ℹ️ {rights['notice']}"]
        source_url = str(rights.get("source_url") or "").strip()
        if source_url:
            rights_lines.append(f"Оригинал / указанный источник: {source_url}")
        blocks.append("\n".join(rights_lines))
    else:
        blocks.append(
            f"✍️ Автор текста: {author_name}. Музыкальная и визуальная интерпретация: The Legendary Poet "
            "(с использованием инструментов искусственного интеллекта)."
        )

    poem_blocks = extract_poem_blocks(source_description)
    playlist_lines = ["🎬 VK-плейлисты:"]
    playlist_urls: list[str] = []
    for collection_id in target["expected_collection_ids"]:
        collection = collections.get(str(collection_id))
        if collection is None:
            raise ValueError(f"Missing expected VK collection {collection_id}")
        url = str(collection.get("metadata", {}).get("share_url") or "").strip()
        if not url.startswith("https://vkvideo.ru/playlist/"):
            raise ValueError(f"Collection {collection_id} has no canonical VK playlist URL")
        label = str(policy["collection_labels"][str(collection_id)])
        playlist_lines.append(f"• {label}: {url}")
        playlist_urls.append(url)

    brand = policy["brand"]
    site_lines = ["🌐 The Legendary Poet:"]
    slug = policy.get("site_author_slugs", {}).get(target["author_key"])
    if slug:
        site_lines.append(f"• Материалы об авторе: {brand['site_url'].rstrip('/')}/poets/{slug}")
    site_lines.extend([f"• Музыка и видеопроекты: {brand['music_url']}", f"• Главная: {brand['site_url']}"])
    channel_lines = [
        "📡 Каналы проекта:",
        f"• VK: {brand['vk_url']}",
        f"• Telegram: {brand['telegram_url']}",
        f"• RUTUBE: {brand['rutube_url']}",
        f"• YouTube: {brand['youtube_url']}",
    ]
    footer_blocks = [
        "━━━━━━━━━━━━━━━",
        "\n".join(playlist_lines),
        "\n".join(site_lines),
        "\n".join(channel_lines),
        " ".join(_canonical_hashtags(policy, target)),
    ]

    maximum = int(policy["rules"]["max_description_length"])
    rendered_without_poem = canonical_vk_text("\n\n".join([*blocks, *footer_blocks]))
    chosen_poems: list[str] = []
    for poem in poem_blocks:
        candidate = canonical_vk_text(
            "\n\n".join([*blocks, "🪶 Текст / фрагмент произведения:", *chosen_poems, poem, *footer_blocks])
        )
        if len(candidate) <= maximum:
            chosen_poems.append(poem)
    if chosen_poems:
        rendered = canonical_vk_text(
            "\n\n".join([*blocks, "🪶 Текст / фрагмент произведения:", *chosen_poems, *footer_blocks])
        )
    else:
        rendered = rendered_without_poem

    if len(rendered) > maximum:
        raise ValueError(f"Final description exceeds {maximum}: {target['video_id']}")
    if rendered == canonical_vk_text(source_description):
        raise ValueError(f"Final description makes no change: {target['video_id']}")

    all_urls = _URL_RE.findall(rendered)
    required_urls = [
        *playlist_urls,
        str(brand["music_url"]),
        str(brand["site_url"]),
        str(brand["vk_url"]),
        str(brand["telegram_url"]),
        str(brand["rutube_url"]),
        str(brand["youtube_url"]),
    ]
    if full_version_id:
        required_urls.append(_video_url(str(full_version_id)))
    if slug:
        required_urls.append(f"{brand['site_url'].rstrip('/')}/poets/{slug}")
    if isinstance(rights, dict) and rights.get("source_url"):
        required_urls.append(str(rights["source_url"]))
    missing = [url for url in required_urls if url not in all_urls]
    if missing:
        raise ValueError(f"Final description is missing canonical URLs for {target['video_id']}: {missing}")

    return rendered, {
        "before_length": len(canonical_vk_text(source_description)),
        "after_length": len(rendered),
        "poem_blocks_preserved": len(chosen_poems),
        "playlist_urls": playlist_urls,
        "hashtags": _canonical_hashtags(policy, target),
        "all_legacy_links_replaced": True,
    }


def build_final_megawave_plan(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    inventory = policy["expected_inventory"]
    if len(snapshot.get("videos", [])) != int(inventory["videos"]):
        raise ValueError("Unexpected source video inventory")
    if len(snapshot.get("collections", [])) != int(inventory["collections"]):
        raise ValueError("Unexpected source collection inventory")
    if len(snapshot.get("memberships", [])) != int(inventory["memberships"]):
        raise ValueError("Unexpected source membership inventory")
    if int(snapshot["channel"]["ref"]["channel_id"]) != int(policy["target_community_id"]):
        raise ValueError("Final megawave policy targets another VK community")

    videos = _video_map(snapshot)
    collections = _collection_map(snapshot)
    memberships = _membership_pairs(snapshot)
    targets = [item for item in policy.get("targets", []) if isinstance(item, dict)]
    if len(targets) != 42 or len({item["video_id"] for item in targets}) != 42:
        raise ValueError("Final megawave policy must contain exactly 42 unique targets")

    video_operations: list[dict[str, Any]] = []
    placement_operations: list[dict[str, Any]] = []
    target_ids: list[str] = []
    for target in targets:
        remote_id = str(target["video_id"])
        target_ids.append(remote_id)
        video = videos.get(remote_id)
        if video is None:
            raise ValueError(f"Missing target video: {remote_id}")
        before_title = canonical_vk_text(str(video.get("title") or ""))
        if before_title != str(target["expected_title"]):
            raise ValueError(f"Title guard mismatch: {remote_id}")
        before_description = canonical_vk_text(str(video.get("description") or ""))
        after_title = canonical_vk_text(str(target.get("title_override") or before_title))
        after_description, metadata = render_final_description(
            before_description,
            policy=policy,
            target=target,
            collections=collections,
        )
        video_operations.append(
            {
                "operation_id": f"video-text:final-megawave:{remote_id}",
                "target_video_id": remote_id,
                "before_title": before_title,
                "after_title": after_title,
                "before_description": before_description,
                "after_description": after_description,
                "before_title_sha256": text_sha256(before_title),
                "after_title_sha256": text_sha256(after_title),
                "before_description_sha256": text_sha256(before_description),
                "after_description_sha256": text_sha256(after_description),
                "title_changed": before_title != after_title,
                "description_changed": True,
                "metadata": metadata,
            }
        )
        for collection_id in target["expected_collection_ids"]:
            collection_id = str(collection_id)
            if collection_id.startswith("-"):
                raise ValueError("Final megawave cannot mutate system albums")
            if collection_id not in collections:
                raise ValueError(f"Missing expected target collection: {collection_id}")
            if (collection_id, remote_id) not in memberships:
                placement_operations.append(
                    {
                        "operation_id": f"placement:add:{collection_id}:{remote_id}",
                        "target_collection_id": collection_id,
                        "target_video_id": remote_id,
                        "before_present": False,
                        "after_present": True,
                    }
                )

    album_operations: list[dict[str, Any]] = []
    for collection_id, requested_title in dict(policy.get("album_title_overrides") or {}).items():
        collection = collections.get(str(collection_id))
        if collection is None:
            raise ValueError(f"Missing album-title target: {collection_id}")
        before_title = canonical_vk_text(str(collection.get("title") or ""))
        after_title = canonical_vk_text(str(requested_title))
        if before_title != after_title:
            album_operations.append(
                {
                    "operation_id": f"album-title:final-megawave:{collection_id}",
                    "target_collection_id": str(collection_id),
                    "before_title": before_title,
                    "after_title": after_title,
                    "before_title_sha256": text_sha256(before_title),
                    "after_title_sha256": text_sha256(after_title),
                }
            )

    video_operations.sort(key=lambda item: item["operation_id"])
    album_operations.sort(key=lambda item: item["operation_id"])
    placement_operations.sort(key=lambda item: item["operation_id"])

    plan: dict[str, Any] = {
        "schema_name": "video-manager.vk-p1-final-megawave-plan",
        "schema_version": 1,
        "decision_set_id": str(policy["decision_set_id"]),
        "target_community_id": int(policy["target_community_id"]),
        "source_snapshot_id": str(snapshot["snapshot_id"]),
        "source_video_ids_sha256": canonical_sha256(sorted(videos)),
        "source_memberships_sha256": canonical_sha256(sorted(memberships)),
        "source_snapshot_sha256": canonical_sha256(snapshot),
        "source_apply_bundle_sha256": str(policy["source_apply_bundle_sha256"]),
        "source_review_bundle_sha256": str(policy["source_review_bundle_sha256"]),
        "policy": deepcopy(policy),
        "policy_sha256": canonical_sha256(policy),
        "target_video_ids": sorted(target_ids),
        "video_text_operations": video_operations,
        "album_title_operations": album_operations,
        "placement_operations": placement_operations,
        "placement_removals": [],
        "video_deletions": [],
    }
    plan["summary"] = {
        "videos_in_snapshot": len(videos),
        "target_videos": len(video_operations),
        "descriptions_to_update": len(video_operations),
        "titles_to_update": sum(bool(item["title_changed"]) for item in video_operations),
        "albums_to_rename": len(album_operations),
        "placements_to_add": len(placement_operations),
        "placements_to_remove": 0,
        "videos_to_delete": 0,
        "total_operations": len(video_operations) + len(album_operations) + len(placement_operations),
    }
    plan["plan_sha256"] = canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})
    verify_final_megawave_plan(snapshot, policy, plan)
    return plan


def verify_final_megawave_plan(
    snapshot: dict[str, Any],
    policy: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    if plan.get("schema_name") != "video-manager.vk-p1-final-megawave-plan":
        raise ValueError("Unexpected final megawave plan schema")
    expected_sha = canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})
    if plan.get("plan_sha256") != expected_sha:
        raise ValueError("Final megawave plan SHA mismatch")
    if plan.get("policy_sha256") != canonical_sha256(policy):
        raise ValueError("Final megawave policy SHA mismatch")
    if plan.get("source_snapshot_sha256") != canonical_sha256(snapshot):
        raise ValueError("Final megawave source snapshot SHA mismatch")

    operation_ids: list[str] = []
    for operation in plan.get("video_text_operations", []):
        operation_ids.append(str(operation["operation_id"]))
        for side in ("before", "after"):
            title = str(operation[f"{side}_title"])
            description = str(operation[f"{side}_description"])
            if operation[f"{side}_title_sha256"] != text_sha256(title):
                raise ValueError(f"Title SHA mismatch: {operation['operation_id']} {side}")
            if operation[f"{side}_description_sha256"] != text_sha256(description):
                raise ValueError(f"Description SHA mismatch: {operation['operation_id']} {side}")
        if len(str(operation["after_description"])) > int(policy["rules"]["max_description_length"]):
            raise ValueError(f"Description too long: {operation['operation_id']}")
    for operation in plan.get("album_title_operations", []):
        operation_ids.append(str(operation["operation_id"]))
    for operation in plan.get("placement_operations", []):
        operation_ids.append(str(operation["operation_id"]))
        if str(operation["target_collection_id"]).startswith("-"):
            raise ValueError("System collection placement is forbidden")
    duplicates = [item for item, count in Counter(operation_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate operation IDs: {duplicates}")

    summary = plan["summary"]
    if int(summary["target_videos"]) != 42 or int(summary["descriptions_to_update"]) != 42:
        raise ValueError("Final megawave does not cover all 42 targets")
    if int(summary["placements_to_add"]) != len(plan["placement_operations"]):
        raise ValueError("Final megawave placement summary mismatch")
    if plan.get("placement_removals") or plan.get("video_deletions"):
        raise ValueError("Final megawave cannot remove memberships or videos")

    return {
        "status": "verified",
        "plan_sha256": plan["plan_sha256"],
        "targets": 42,
        "description_updates": 42,
        "title_updates": int(summary["titles_to_update"]),
        "album_renames": int(summary["albums_to_rename"]),
        "placements_to_add": int(summary["placements_to_add"]),
        "total_operations": int(summary["total_operations"]),
    }


__all__ = [
    "build_final_megawave_plan",
    "extract_poem_blocks",
    "render_final_description",
    "verify_final_megawave_plan",
]
