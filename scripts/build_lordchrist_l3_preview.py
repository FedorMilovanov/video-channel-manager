#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Предпросмотр двухслойного выпуска L3 из готовых файлов выпуска.

Собирает ровно то, что уйдёт в Telegram и Telegra.ph, но ничего не публикует:
читает rich-документ статьи и черновик поста канала, печатает текстовые слои и
рисует автономную страницу предпросмотра (лента + книжный ридер).

    python3 scripts/build_lordchrist_l3_preview.py \
        --article content/.../lordchrist-rich-rabstvo-svobody.json \
        --post content/.../lordchrist-rich-rabstvo-svobody-пост.json \
        --cover content/.../media/заготовка-обложки-16x9.svg \
        --telegraph-url https://telegra.ph/Rabstvo-svobody \
        --out-html ...-превью.html \
        --out-post-html ...-пост.html \
        --out-post-plain ...-пост.txt

Обложка в предпросмотре подставляется как `data:`-URI, поэтому страница
автономна; на Telegra.ph уходит HTTPS-адрес из media_base_url, а не эта копия.
Байты контента считаются по компактному JSON узлов — так же, как их считает
`build_telegraph_payload`, — и сравниваются с потолками провайдера.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

from video_channel_manager.lordchrist_telegraph_publisher import (
    MAX_TELEGRAPH_CONTENT_UTF8_BYTES,
    MAX_TELEGRAM_POST_VISIBLE_CHARS,
    MIN_TELEGRAM_POST_VISIBLE_CHARS,
    SINGLE_PAGE_SOFT_UTF8_BYTES,
    ChannelPostSpec,
    ExpandablePoint,
    RichArticleDocument,
    RichBlockFooter,
    RichBlockHeading,
    RichBlockMedia,
    RichBlockParagraph,
    RichBlockQuote,
    RenderedChannelPost,
    TelegraphPayload,
    _apply_telegraph_layout_rules,
    _rich_text_to_telegraph_children,
    _validate_telegraph_nodes,
    iter_text_fragments,
    render_channel_post,
    render_preview_html_page,
)

COVER_MIME_OVERRIDES = {".svg": "image/svg+xml"}


def media_url(uri: str, media_base_url: str) -> str:
    """URL картинки для Telegra.ph: готовый HTTPS или путь репозитория поверх базы."""
    if uri.startswith("https://"):
        return uri
    return f"{media_base_url.rstrip('/')}/{uri}"


def build_nodes(document: RichArticleDocument, cover_url: str, media_base_url: str) -> list[dict[str, Any] | str]:
    """Тело Telegraph: обложка первой фигурой, H1 уходит в title страницы."""
    nodes: list[dict[str, Any] | str] = [{"tag": "figure", "children": [{"tag": "img", "attrs": {"src": cover_url}}]}]
    library = {item.media_id: item for item in document.media}
    for block in document.blocks:
        if isinstance(block, RichBlockHeading):
            if block.size == 1:
                continue
            tag = "h3" if block.size == 2 else "h4"
            nodes.append({"tag": tag, "children": ["".join(iter_text_fragments(block.text))]})
        elif isinstance(block, (RichBlockParagraph, RichBlockFooter)):
            nodes.append({"tag": "p", "children": _rich_text_to_telegraph_children(block.text)})
        elif isinstance(block, RichBlockQuote):
            children: list[dict[str, Any] | str] = []
            for index, inner in enumerate(block.blocks):
                if index:
                    children.extend([{"tag": "br"}, {"tag": "br"}])
                if isinstance(inner, (RichBlockParagraph, RichBlockFooter)):
                    children.extend(_rich_text_to_telegraph_children(inner.text))
                else:
                    children.append("".join(iter_text_fragments(inner)))
            nodes.append({"tag": "blockquote", "children": children})
            if block.credit is not None:
                credit = "".join(iter_text_fragments(block.credit)).strip()
                if not credit.startswith("—"):
                    credit = f"— {credit}"
                nodes.append({"tag": "p", "children": [{"tag": "em", "children": [credit]}]})
        elif isinstance(block, RichBlockMedia):
            item = library.get(block.media_id)
            if item is None:
                raise ValueError(f"нет медиа-элемента {block.media_id!r} в библиотеке документа")
            children: list[dict[str, Any] | str] = [
                {"tag": "img", "attrs": {"src": media_url(item.uri, media_base_url)}}
            ]
            if block.caption is not None:
                caption = _rich_text_to_telegraph_children(block.caption.text)
                if block.caption.credit is not None:
                    caption.extend([" — ", *_rich_text_to_telegraph_children(block.caption.credit)])
                children.append({"tag": "figcaption", "children": caption})
            nodes.append({"tag": "figure", "children": children})
    return _apply_telegraph_layout_rules(nodes)


def build_payload(article: Path, post: dict[str, Any], cover_url: str, media_base_url: str) -> TelegraphPayload:
    document = RichArticleDocument.model_validate(json.loads(article.read_text(encoding="utf-8")))
    nodes = build_nodes(document, cover_url, media_base_url)
    _validate_telegraph_nodes(nodes)
    compact = json.dumps(nodes, ensure_ascii=False, separators=(",", ":"))
    title = document.metadata.title
    return TelegraphPayload(
        publication_id=str(post.get("publication_id") or document.document_id),
        title=title,
        author_name="Господь Бог",
        author_url="https://t.me/lordchrist",
        cover_url=cover_url,
        nodes=nodes,
        inline_media_urls=(),
        compact_content_json=compact,
        content_utf8_bytes=len(compact.encode("utf-8")),
        article_sha256=hashlib.sha256(article.read_bytes()).hexdigest(),
        cover_sha256="",
    )


def parse_post(post: dict[str, Any]) -> ChannelPostSpec:
    raw = post.get("channel_post")
    if not isinstance(raw, dict):
        raise ValueError("в файле поста нет объекта channel_post")
    points = raw.get("expandable_points")
    if not isinstance(points, list) or not points:
        raise ValueError("channel_post.expandable_points пуст")
    return ChannelPostSpec(
        headline=str(raw["headline"]).strip(),
        lead_paragraphs=tuple(str(p).strip() for p in raw.get("lead_paragraphs") or ()),
        quote_text=str(raw["quote_text"]).strip(),
        quote_attribution=str(raw["quote_attribution"]).strip(),
        expandable_header=str(raw["expandable_header"]).strip(),
        expandable_points=tuple(
            ExpandablePoint(lead=str(p["lead"]).strip(), body=str(p["body"]).strip()) for p in points
        ),
        cta_prefix=str(raw["cta_prefix"]).strip(),
        cta_link_label=str(raw["cta_link_label"]).strip(),
    )


def data_uri(path: Path) -> str:
    payload = path.read_bytes()
    mime = COVER_MIME_OVERRIDES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
    if not mime:
        raise ValueError(f"не удалось определить MIME для {path}")
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


def series_label(payload: TelegraphPayload, post: dict[str, Any]) -> str:
    return str(post.get("series_label") or payload.title)


def check_post(post: RenderedChannelPost) -> list[str]:
    warnings: list[str] = []
    if post.visible_char_count > MAX_TELEGRAM_POST_VISIBLE_CHARS:
        warnings.append(f"пост {post.visible_char_count} зн. > {MAX_TELEGRAM_POST_VISIBLE_CHARS} допустимых")
    if post.visible_char_count < MIN_TELEGRAM_POST_VISIBLE_CHARS:
        warnings.append(
            f"пост {post.visible_char_count} зн. < {MIN_TELEGRAM_POST_VISIBLE_CHARS}: лента не любит пустых постов"
        )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", type=Path, required=True)
    parser.add_argument("--post", type=Path, required=True)
    parser.add_argument("--cover", type=Path, required=True)
    parser.add_argument("--telegraph-url", required=True)
    parser.add_argument("--out-html", type=Path, required=True)
    parser.add_argument("--out-post-html", type=Path, required=True)
    parser.add_argument("--out-post-plain", type=Path, required=True)
    parser.add_argument("--media-base-url", default="https://telegra.ph/file", help="база для URL обложки")
    args = parser.parse_args()

    post_raw = json.loads(args.post.read_text(encoding="utf-8"))
    cover_url = f"{args.media_base_url.rstrip('/')}/{args.cover.as_posix()}"
    payload = build_payload(args.article, post_raw, cover_url, args.media_base_url)
    spec = parse_post(post_raw)
    rendered = render_channel_post(spec, args.telegraph_url)

    for problem in check_post(rendered):
        print(f"предупреждение: {problem}", file=sys.stderr)

    page = render_preview_html_page(payload, rendered, data_uri(args.cover))
    label = html.escape(series_label(payload, post_raw), quote=False)
    page = page.replace("· Серия «Стивен Чарнок. О бытии Бога»", f"· {label}")
    page = page.replace(
        f"{payload.content_utf8_bytes:,} байт UTF-8 / 60 000",
        f"{payload.content_utf8_bytes:,} байт UTF-8 / {MAX_TELEGRAPH_CONTENT_UTF8_BYTES:,}".replace(",", " "),
    )

    # Автономность предпросмотра: внутренние картинки подставляются как data:,
    # а байты контента уже посчитаны по «публикационным» HTTPS-адресам.
    document = RichArticleDocument.model_validate(json.loads(args.article.read_text(encoding="utf-8")))
    for item in document.media:
        local = Path(item.uri)
        if item.uri.startswith("https://") or not local.is_file():
            continue
        page = page.replace(html.escape(media_url(item.uri, args.media_base_url), quote=True), data_uri(local))

    args.out_html.write_text(page, encoding="utf-8")
    args.out_post_html.write_text(rendered.html_text, encoding="utf-8")
    args.out_post_plain.write_text(rendered.plain_text, encoding="utf-8")

    print(f"пост: {rendered.visible_char_count} зн. видимого текста")
    print(
        f"статья Telegra.ph: {payload.content_utf8_bytes} байт UTF-8 / "
        f"{MAX_TELEGRAPH_CONTENT_UTF8_BYTES} (мягкий порог одной страницы "
        f"{SINGLE_PAGE_SOFT_UTF8_BYTES}, узлов {len(payload.nodes)})"
    )
    for path in (args.out_html, args.out_post_html, args.out_post_plain):
        print(f"→ {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
