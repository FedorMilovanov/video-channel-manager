#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Привязать присланные изображения к документу статьи как media-блоки.

`build_l2_rich_document.py` пересобирает `blocks` из Markdown, поэтому картинки
не могут жить в Markdown: они привязываются отдельным шагом после сборки.
Шаг идемпотентен: слот `media_slots[i]`, у которого есть файл в `media`
(совпадение по `media_id` = `slot_id`), получает блок `img-NN` сразу после
блока, указанного в `placement.after`.

    python3 scripts/attach_lordchrist_media_blocks.py статья.json [--dry-run]

Обложка сюда не входит: она не элемент тела статьи, а фигура страницы
Telegra.ph и поле `cover` очереди выпуска, и в библиотеке `media` ей места нет
(валидатор rich-документа запрещает неиспользуемые элементы библиотеки).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

IMAGE_BLOCK_PREFIX = "img-"


def attach(document: dict) -> tuple[dict, list[str]]:
    blocks: list[dict] = document.get("blocks") or []
    media_ids = {str(m.get("media_id")) for m in document.get("media") or []}
    slots = document.get("media_slots") or []
    used = {str(b.get("media_id")) for b in blocks if b.get("type") == "media"}
    log: list[str] = []

    for slot in slots:
        media_id = str(slot.get("slot_id") or "")
        if media_id not in media_ids:
            continue
        if media_id in used:
            continue
        placement = slot.get("placement") or {}
        after = str(placement.get("after") or "")
        target = next((i for i, b in enumerate(blocks) if b.get("block_id") == after), None)
        if target is None:
            log.append(f"{media_id}: не найден блок {after!r} — пропущен")
            continue
        index = sum(1 for b in blocks if str(b.get("block_id", "")).startswith(IMAGE_BLOCK_PREFIX)) + 1
        block: dict = {"type": "media", "block_id": f"{IMAGE_BLOCK_PREFIX}{index:02d}", "media_id": media_id}
        caption = str(slot.get("caption") or "").strip()
        if caption:
            block["caption"] = {"text": caption}
        blocks.insert(target + 1, block)
        used.add(media_id)
        log.append(f"{block['block_id']}: {media_id} после {after}")

    document["blocks"] = blocks
    return document, log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("article", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    document = json.loads(args.article.read_text(encoding="utf-8"))
    document, log = attach(document)
    for line in log or ["нечего привязывать: у слотов нет файлов"]:
        print(line)
    if not args.dry_run and log:
        args.article.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
