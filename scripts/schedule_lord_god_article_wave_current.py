#!/usr/bin/env python3
"""Current guarded entrypoint for the theological article wall queue.

The original immutable plan referenced one superseded social image and one
article that exists only as a publication-hold draft without a public route.
This entrypoint applies two exact reviewed corrections in memory before the
normal policy, source, VK-card, duplicate, canary, and postflight guards run.

VK ``wall.parseAttachedLink`` returns an array of generic wall attachments. In
current production behavior it may return the prepared image as a ``photo``
attachment without a separate ``link`` attachment. This wrapper accepts that
exact response shape only when a valid VK photo token exists, then combines the
photo token with the exact reviewed article URL for ``wall.post``. Empty or
otherwise unusable parse results remain blocking.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

MODULE_PATH = Path(__file__).with_name("schedule_lord_god_article_wave.py")
MODULE_NAME = "schedule_lord_god_article_wave_guarded"

HERMENEUTICS_ID = "lord-god-article-wave-202608-05-hermenevtika"
HERMENEUTICS_IMAGE = (
    "https://gospod-bog.ru/images/"
    "og-hermenevtika-hristotsentrichnaya-otsenka.webp"
)

DIOTROPHES_ID = "lord-god-article-wave-202608-06-diotrefy"
KRAJNE_OPERATION: dict[str, Any] = {
    "id": "krajne-isporcheno",
    "title": "Крайне ли испорчено сердце верующего?",
    "url": "https://gospod-bog.ru/articles/krajne-li-isporcheno-serdce/",
    "og_image": "https://gospod-bog.ru/images/og-krajne-isporcheno.webp",
    "source_path": "src/components/article-pilots/krajne/KrajneBody.astro",
    "message": (
        "🫀 Крайне ли испорчено сердце верующего?\n\n"
        "«Неверный диагноз превращает лечение в бесконечную суету вокруг "
        "симптомов: человек хлопочет о внешних проявлениях болезни, тогда как "
        "сама болезнь продолжает жить глубже».\n\n"
        "Иеремия 17:9 говорит о сердце резко и беспощадно. Но как применять "
        "этот диагноз к человеку, которому Бог дал новое сердце? Подробная "
        "статья удерживает обе истины: реальность обновления во Христе и "
        "способность остаточного греха оправдывать самого себя.\n\n"
        "💬 Как одновременно исповедовать реальность нового сердца и не "
        "недооценивать самообман остаточного греха?\n\n"
        "Читать полную статью:\n"
        "https://gospod-bog.ru/articles/krajne-li-isporcheno-serdce/"
    ),
    "ordinal": 6,
    "operation_id": "lord-god-article-wave-202608-06-krajne-isporcheno",
    "publish_at": "2026-08-08T14:00:00+03:00",
    "publish_date": 1786186800,
}


def load_guarded_module() -> Any:
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load guarded article scheduler: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def install_reviewed_policy_corrections(module: Any) -> None:
    original_load_policy = module.load_policy

    def load_current_policy(repo: Path) -> dict[str, Any]:
        original = original_load_policy(repo)
        policy = copy.deepcopy(original)
        operations = policy.get("operations")
        if not isinstance(operations, list) or len(operations) != 10:
            raise RuntimeError("Unexpected article policy operation set")

        hermeneutics_seen = False
        diotrophes_seen = False
        corrected: list[dict[str, Any]] = []
        for raw_operation in operations:
            if not isinstance(raw_operation, dict):
                raise RuntimeError("Article policy contains a non-object operation")
            operation = copy.deepcopy(raw_operation)
            operation_id = str(operation.get("operation_id") or "")

            if operation_id == HERMENEUTICS_ID:
                expected_old_image = (
                    "https://gospod-bog.ru/images/hermenevtika-preview.webp"
                )
                if module.normalize_url(operation.get("og_image")) != expected_old_image:
                    raise RuntimeError("Hermeneutics policy no longer matches reviewed source")
                operation["og_image"] = HERMENEUTICS_IMAGE
                hermeneutics_seen = True

            if operation_id == DIOTROPHES_ID:
                if module.normalize_url(operation.get("url")) != (
                    "https://gospod-bog.ru/articles/diotrefy-nashego-vremeni/"
                ):
                    raise RuntimeError("Diotrophes policy no longer matches reviewed draft")
                operation = copy.deepcopy(KRAJNE_OPERATION)
                operation["message_sha256"] = module.message_sha(operation["message"])
                diotrophes_seen = True

            corrected.append(operation)

        if not hermeneutics_seen or not diotrophes_seen:
            raise RuntimeError("Reviewed article corrections could not be applied exactly")

        policy["operations"] = corrected
        policy["policy_sha256"] = module.canonical_sha(
            {key: value for key, value in policy.items() if key != "policy_sha256"}
        )
        module.EXPECTED_SHA = policy["policy_sha256"]
        return policy

    module.load_policy = load_current_policy


def install_vk_link_parse_compatibility(module: Any) -> None:
    def parse_attached_link(client: Any, article_url: str) -> dict[str, Any]:
        normalized = module.normalize_url(article_url)
        links_json = json.dumps(
            [{"type": "link", "link": normalized}],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = client._call(
            "wall.parseAttachedLink",
            params={"links": links_json, "extended": False},
        )
        data = response.get("data") if isinstance(response, dict) else None
        attachments = (
            [item for item in data if isinstance(item, dict)]
            if isinstance(data, list)
            else []
        )
        attachment_types = [str(item.get("type") or "unknown") for item in attachments]
        links = [module.link_payload_from_attachment(item) for item in attachments]
        links = [item for item in links if isinstance(item, dict)]
        if len(links) > 1:
            raise RuntimeError(
                f"wall.parseAttachedLink returned {len(links)} link cards for {normalized}"
            )

        link = links[0] if links else {}
        photo_tokens = module.parsed_photo_tokens(attachments, link)

        if link:
            resolved = module.normalize_url(
                link.get("url") or link.get("target_url") or normalized
            )
            if resolved != normalized:
                raise RuntimeError(
                    f"VK resolved a different article URL: {normalized} -> {resolved}"
                )
            if not module.link_has_image(link) and not photo_tokens:
                raise RuntimeError(f"VK parsed the article without an image: {normalized}")
            parse_mode = "link_card"
            title = str(link.get("title") or "")
            description_length = len(str(link.get("description") or ""))
        else:
            if not photo_tokens:
                shape = ",".join(attachment_types) or "empty"
                raise RuntimeError(
                    "wall.parseAttachedLink returned no usable image attachment "
                    f"for {normalized}; attachment_types={shape}"
                )
            resolved = normalized
            parse_mode = "photo_tokens_plus_external_url"
            title = ""
            description_length = 0

        attachment_parts = [*photo_tokens, normalized]
        return {
            "article_url": normalized,
            "resolved_url": resolved,
            "attachment_type": "link" if link else "photo+external-link",
            "parse_mode": parse_mode,
            "attachment_types": attachment_types,
            "response_data_sha256": module.canonical_sha(attachments),
            "title": title,
            "description_length": description_length,
            "link_card_has_image": True,
            "photo_tokens": photo_tokens,
            "wall_post_attachments": ",".join(attachment_parts),
            "status": "verified",
        }

    module.parse_attached_link = parse_attached_link


def main() -> int:
    module = load_guarded_module()
    install_reviewed_policy_corrections(module)
    install_vk_link_parse_compatibility(module)
    return int(module.main())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(2) from exc
