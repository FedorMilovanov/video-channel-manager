from __future__ import annotations

import re
import statistics
from typing import Any

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import text_sha256
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
)


def _paragraphs(text: str) -> list[str]:
    return [value.strip() for value in re.split(r"\n\s*\n", text.strip()) if value.strip()]


def _is_hashtag_block(value: str) -> bool:
    hashtags = _HASHTAG_RE.findall(value)
    if not hashtags:
        return False
    return not re.sub(_HASHTAG_RE, "", value).strip()


def _is_metadata_link_block(value: str) -> bool:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines or not _URL_RE.search(value):
        return False
    if len(value) > 1000:
        return False
    return all(len(_URL_RE.sub("", line).strip()) <= 120 for line in lines)


def is_poem_like_block(value: str) -> bool:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    if any(_URL_RE.search(line) or _HASHTAG_RE.search(line) for line in lines):
        return False
    if any(any(marker in line for marker in _BAD_POEM_MARKERS) for line in lines[:4]):
        return False
    lengths = [len(line) for line in lines]
    short_ratio = sum(length <= 85 for length in lengths) / len(lengths)
    colon_ratio = sum(":" in line for line in lines) / len(lines)
    bullet_ratio = sum(line.startswith(("➛", "•", "— ", "- ")) for line in lines) / len(lines)
    return statistics.median(lengths) <= 65 and short_ratio >= 0.75 and colon_ratio < 0.20 and bullet_ratio < 0.25


def _preserve_service_content(paragraph: str) -> tuple[list[str], list[str]]:
    if paragraph.startswith("🎧 The Legendary Poet"):
        return [paragraph], ["channel_footer"]
    if is_poem_like_block(paragraph):
        return [paragraph], ["poem_like_block"]
    if _is_metadata_link_block(paragraph):
        return [paragraph], ["metadata_link_block"]
    if _is_hashtag_block(paragraph):
        return [paragraph], ["hashtag_block"]

    blocks: list[str] = []
    kinds: list[str] = []
    urls = _URL_RE.findall(paragraph)
    if urls:
        blocks.append("🔗 Источники:\n" + "\n".join(urls))
        kinds.append("extracted_urls")
    hashtags = _HASHTAG_RE.findall(paragraph)
    if hashtags:
        blocks.append(" ".join(hashtags))
        kinds.append("extracted_hashtags")
    return blocks, kinds


def build_evidence_safe_description(description: str, title: str) -> tuple[str, dict[str, Any]]:
    source = canonical_vk_text(description)
    kept: list[str] = []
    kept_kinds: list[str] = []
    for paragraph in _paragraphs(source):
        blocks, kinds = _preserve_service_content(paragraph)
        kept.extend(blocks)
        kept_kinds.extend(kinds)

    intro = (
        f"🎧 Перед вами музыкальная и визуальная интерпретация: {title}.\n"
        "Описание сосредоточено на тексте, образах и звучании произведения."
    )
    caveat = (
        "📖 Биографические, исторические, психологические и духовные параллели здесь "
        "рассматриваются только как интерпретации. Они не выдаются за документированное "
        "признание автора, медицинский диагноз, пророчество или установленный замысел "
        "без прямого источника."
    )
    rendered = canonical_vk_text("\n\n".join([intro, caveat, *kept]))
    if rendered == source:
        raise ValueError(f"Evidence-safe rewrite makes no change: {title}")
    if len(rendered) > 5000:
        raise ValueError(f"Evidence-safe rewrite exceeds 5000 characters: {title}")
    if _URL_RE.findall(source) != _URL_RE.findall(rendered):
        raise ValueError(f"Evidence-safe rewrite changes URLs: {title}")
    if _HASHTAG_RE.findall(source) != _HASHTAG_RE.findall(rendered):
        raise ValueError(f"Evidence-safe rewrite changes hashtags: {title}")

    return rendered, {
        "before_length": len(source),
        "after_length": len(rendered),
        "preserved_blocks": len(kept),
        "preserved_block_kinds": kept_kinds,
        "before_description_sha256": text_sha256(source),
        "after_description_sha256": text_sha256(rendered),
        "urls_unchanged": True,
        "hashtags_unchanged": True,
    }


def build_vk_p1_megawave_decisions(
    target: AuditPackage,
    queue: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if target.channel.ref.platform.value != "vk":
        raise ValueError("Megawave target must be VK")
    community_id = int(target.channel.ref.channel_id)
    if int(policy.get("target_community_id", 0)) != community_id:
        raise ValueError("Megawave policy targets another community")
    if policy.get("mode") != "single_megawave":
        raise ValueError("Megawave policy mode must be single_megawave")
    if queue.get("mode") != "review_only" or int(queue.get("remote_writes", -1)) != 0:
        raise ValueError("Megawave source queue is not review-only")

    target_items = [item for item in policy.get("targets", []) if isinstance(item, dict)]
    expected_count = int(policy.get("target_count", 0))
    if expected_count != 42 or len(target_items) != expected_count:
        raise ValueError("Megawave policy must contain exactly 42 targets")
    target_ids = [str(item.get("video_id") or "") for item in target_items]
    if any(not value for value in target_ids) or len(set(target_ids)) != len(target_ids):
        raise ValueError("Megawave target IDs are empty or duplicated")

    videos = {video.ref.remote_id: video for video in target.videos}
    if len(videos) != 111:
        raise ValueError("Megawave source snapshot must contain 111 videos")

    unit_by_video: dict[str, dict[str, Any]] = {}
    for unit in queue.get("research_units", []):
        if not isinstance(unit, dict):
            continue
        for item in unit.get("videos", []):
            if not isinstance(item, dict):
                continue
            remote_id = str(item.get("video_id") or "")
            if remote_id in target_ids:
                if remote_id in unit_by_video:
                    raise ValueError(f"Target appears in more than one research unit: {remote_id}")
                unit_by_video[remote_id] = unit
    missing = sorted(set(target_ids) - set(unit_by_video))
    if missing:
        raise ValueError(f"Targets missing from source review queue: {missing}")

    for item in target_items:
        remote_id = str(item["video_id"])
        video = videos.get(remote_id)
        if video is None:
            raise ValueError(f"Target missing from VK snapshot: {remote_id}")
        if canonical_vk_text(video.title) != str(item.get("expected_title") or ""):
            raise ValueError(f"Target title guard mismatch: {remote_id}")
        unit = unit_by_video[remote_id]
        if unit.get("priority") != "P1":
            raise ValueError(f"Target is not active P1: {remote_id}")
        if canonical_vk_text(video.description) != canonical_vk_text(str(unit.get("description") or "")):
            raise ValueError(f"Target description differs from reviewed research unit: {remote_id}")

    ordered_units: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    for remote_id in target_ids:
        unit = unit_by_video[remote_id]
        unit_id = str(unit.get("research_unit_id") or "")
        if not unit_id:
            raise ValueError(f"Research unit has no ID: {remote_id}")
        if unit_id not in seen_units:
            seen_units.add(unit_id)
            ordered_units.append(unit)
    expected_units = int(policy.get("expected_research_units", 0))
    if len(ordered_units) != expected_units or expected_units != 37:
        raise ValueError("Megawave must contain exactly 37 unique research units")

    shared_replacements: list[dict[str, Any]] = []
    replacement_by_unit: dict[str, str] = {}
    for index, unit in enumerate(ordered_units, start=1):
        unit_id = str(unit["research_unit_id"])
        unit_targets = [
            remote_id for remote_id in target_ids if str(unit_by_video[remote_id].get("research_unit_id")) == unit_id
        ]
        first_video = videos[unit_targets[0]]
        before = canonical_vk_text(first_video.description)
        after, metadata = build_evidence_safe_description(before, canonical_vk_text(first_video.title))
        replacement_id = f"mega-safe-{index:02d}-{unit_id.split(':')[-1]}"
        replacement_by_unit[unit_id] = replacement_id
        shared_replacements.append(
            {
                "replacement_id": replacement_id,
                "old": before,
                "new": after,
                "expected_count": 1,
                "reason": (
                    "Replace the full active-P1 legacy description with a conservative evidence-safe "
                    "version. Preserve poem-like blocks, URLs, hashtags, playlists, and the channel footer; "
                    "remove unsupported biographical, psychological, medical, prophetic, and theological claims."
                ),
                "research_unit_id": unit_id,
                "priority": "P1",
                "target_video_ids": unit_targets,
                **metadata,
            }
        )

    sources = [item for item in policy.get("sources", []) if isinstance(item, dict)]
    source_ids = [str(item.get("source_id") or "") for item in sources]
    if not source_ids or any(not value for value in source_ids) or len(set(source_ids)) != len(source_ids):
        raise ValueError("Megawave source definitions are invalid")

    decisions: list[dict[str, Any]] = []
    for item in target_items:
        remote_id = str(item["video_id"])
        video = videos[remote_id]
        unit_id = str(unit_by_video[remote_id]["research_unit_id"])
        decisions.append(
            {
                "decision_id": f"correct-{remote_id.split('_')[-1]}",
                "target_video_id": remote_id,
                "expected_title": canonical_vk_text(video.title),
                "expected_description_sha256": text_sha256(canonical_vk_text(video.description)),
                "replacement_ids": [replacement_by_unit[unit_id]],
                "source_ids": source_ids,
            }
        )

    return {
        "schema_name": "video-manager.vk-reviewed-correction-decisions",
        "schema_version": 1,
        "decision_set_id": str(policy.get("decision_set_id") or ""),
        "target_community_id": community_id,
        "source_plan_sha256": str(policy.get("source_plan_sha256") or ""),
        "source_review_bundle_sha256": str(policy.get("source_review_bundle_sha256") or ""),
        "source_apply_bundle_sha256": str(policy.get("source_apply_bundle_sha256") or ""),
        "editorial_rule": str(policy.get("rule") or ""),
        "megawave_mode": "single_command_build_verify_apply_postflight",
        "target_count": len(decisions),
        "unique_description_count": len(shared_replacements),
        "editorial_profile": policy.get("editorial_profile"),
        "stance_source_ids": policy.get("stance_source_ids"),
        "shared_replacements": shared_replacements,
        "sources": sources,
        "decisions": decisions,
        "description_guard_hash_algorithm": str(policy.get("description_guard_hash_algorithm") or ""),
    }


__all__ = [
    "build_evidence_safe_description",
    "build_vk_p1_megawave_decisions",
    "is_poem_like_block",
]
