"""LordChrist two-layer Telegraph + Instant View channel publisher.

Publishes each long Charnock article in two coordinated layers:

1. Full book-grade longread (30 000+ chars, cover image first node, ``h3``/``h4``
   sections, ``strong``/``em`` emphasis, ``blockquote`` quotations with italic
   attribution) published via the official ``https://api.telegra.ph`` API using
   raw UTF-8 ``multipart/form-data`` so Cyrillic payloads stay under the 64 KB
   API ceiling without percent-encoding bloat.
2. Compact channel post in ``@lordchrist`` via ``sendMessage`` (HTML mode) with:
   - bold headline + short lead hook,
   - one open quotation block (``<blockquote>``),
   - a collapsible digest (``<blockquote expandable>``) for fast readers,
   - explicit large-media Instant View preview card (``prefer_large_media=True``)
     showing the ``16:9`` cover and the ``⚡ ПОСМОТРЕТЬ`` button while keeping
     full Telegram Stories repost support.

Security note (public repository invariant):
``FedorMilovanov/video-channel-manager`` is public, so ``access_token`` and
``auth_url`` are NEVER persisted into git state files or workflow logs. Only
public URLs, message IDs, and SHA-256 digests are recorded in the ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import httpx

from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpOperationClass,
    execute_http_request,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_rich_models import (
    RichArticleDocument,
    RichBlockFooter,
    RichBlockHeading,
    RichBlockParagraph,
    RichBlockQuote,
    RichTextBold,
    RichTextCode,
    RichTextContent,
    RichTextItalic,
    RichTextStrikethrough,
    RichTextUnderline,
    RichTextUrl,
    iter_text_fragments,
)
from video_channel_manager.telegram_target_binding import load_target_binding

TELEGRAPH_QUEUE_SCHEMA = "video-channel-manager.lordchrist-telegraph-article-queue"
PROJECT_KEY = "lord-god-strength"
CHANNEL_USERNAME = "@lordchrist"
DEFAULT_AUTHOR_NAME = "Господь Бог"
DEFAULT_AUTHOR_URL = "https://t.me/lordchrist"
DEFAULT_SHORT_NAME = "lordchrist"
DEFAULT_TELEGRAPH_API_BASE = "https://api.telegra.ph"
DEFAULT_TELEGRAM_API_BASE = "https://api.telegram.org"

DEFAULT_QUEUE_PATH = Path("content/telegram/lordchrist/telegraph-v1/article-queue.json")
DEFAULT_PROFILE_PATH = Path("content/telegram/channels/lordchrist-rich.json")
DEFAULT_BINDING_PATH = Path("content/telegram/channels/lordchrist-rich-target-binding.json")
DEFAULT_LEDGER_PATH = Path("content/telegram/lordchrist/telegraph-v1/publication-ledger.json")

JPEG_MAGIC = b"\xff\xd8\xff"
MAX_TELEGRAPH_CONTENT_UTF8_BYTES = 120_000
SINGLE_PAGE_SOFT_UTF8_BYTES = 58_000
MAX_TELEGRAM_POST_VISIBLE_CHARS = 3_950
MIN_TELEGRAM_POST_VISIBLE_CHARS = 600

ALLOWED_TELEGRAPH_TAGS = frozenset(
    {
        "a",
        "aside",
        "b",
        "blockquote",
        "br",
        "code",
        "em",
        "figcaption",
        "figure",
        "h3",
        "h4",
        "hr",
        "i",
        "iframe",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "strong",
        "u",
        "ul",
        "video",
    }
)


@dataclass(frozen=True)
class ExpandablePoint:
    lead: str
    body: str


@dataclass(frozen=True)
class ChannelPostSpec:
    headline: str
    lead_paragraphs: tuple[str, ...]
    quote_text: str
    quote_attribution: str
    expandable_header: str
    expandable_points: tuple[ExpandablePoint, ...]
    cta_prefix: str
    cta_link_label: str


@dataclass(frozen=True)
class TelegraphQueueItem:
    publication_id: str
    ordinal: int
    scheduled_on: date | None
    status: str
    is_canary: bool = False
    article_path: Path | None = None
    article_blob: str | None = None
    cover_path: Path | None = None
    cover_blob: str | None = None
    channel_post: ChannelPostSpec | None = None

    @property
    def is_ready(self) -> bool:
        return (
            self.status == "ready"
            and self.article_path is not None
            and self.cover_path is not None
            and self.channel_post is not None
        )


@dataclass(frozen=True)
class TelegraphPayload:
    publication_id: str
    title: str
    author_name: str
    author_url: str
    cover_url: str
    nodes: list[dict[str, Any] | str]
    compact_content_json: str
    content_utf8_bytes: int
    article_sha256: str
    cover_sha256: str


@dataclass(frozen=True)
class RenderedChannelPost:
    html_text: str
    plain_text: str
    visible_char_count: int
    telegraph_url: str


class HttpTransport(Protocol):
    def post_multipart(self, url: str, fields: Mapping[str, bytes]) -> dict[str, Any]: ...
    def read_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...
    def post_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...
    def get_status(self, url: str) -> tuple[int, bytes]: ...


class HttpxLiveTransport(HttpClientOwner):
    """Managed synchronous HTTP transport using the repository's shared lifecycle owner."""

    def __init__(self, timeout_seconds: float = 30.0, http_client: httpx.Client | None = None) -> None:
        self._initialize_http_client(http_client, timeout=timeout_seconds)

    def post_multipart(self, url: str, fields: Mapping[str, bytes]) -> dict[str, Any]:
        files = {name: (None, value) for name, value in fields.items()}
        res = execute_http_request(
            lambda: self._http_client.post(url, files=files),
            provider="telegraph",
            operation=HttpOperationClass.AMBIGUOUS_MUTATION,
            method="POST",
            resource="api.telegra.ph",
        )
        res.response.raise_for_status()
        data = res.response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Expected JSON object from Telegraph API")
        return data

    def read_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        res = execute_http_request(
            lambda: self._http_client.post(url, json=payload),
            provider="telegram",
            operation=HttpOperationClass.SAFE_READ,
            method="POST",
            resource="telegram_preflight_read",
        )
        res.response.raise_for_status()
        data = res.response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Expected JSON object from Telegram Bot API read")
        return data

    def post_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        res = execute_http_request(
            lambda: self._http_client.post(url, json=payload),
            provider="telegram",
            operation=HttpOperationClass.AMBIGUOUS_MUTATION,
            method="POST",
            resource="sendMessage",
        )
        res.response.raise_for_status()
        data = res.response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Expected JSON object from Telegram Bot API")
        return data

    def get_status(self, url: str) -> tuple[int, bytes]:
        res = execute_http_request(
            lambda: self._http_client.get(url),
            provider="telegraph_probe",
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource="public_asset_probe",
        )
        return res.response.status_code, res.response.content[:1024]


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object format


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _parse_channel_post(raw: Mapping[str, Any], label: str) -> ChannelPostSpec:
    headline = str(raw.get("headline") or "").strip()
    lead_raw = raw.get("lead_paragraphs")
    quote_text = str(raw.get("quote_text") or "").strip()
    quote_attribution = str(raw.get("quote_attribution") or "").strip()
    expandable_header = str(raw.get("expandable_header") or "").strip()
    points_raw = raw.get("expandable_points")
    cta_prefix = str(raw.get("cta_prefix") or "").strip()
    cta_link_label = str(raw.get("cta_link_label") or "").strip()

    if not headline or len(headline) > 140:
        raise ValueError(f"{label}: channel_post.headline must be 1..140 chars")
    if not isinstance(lead_raw, list) or not (1 <= len(lead_raw) <= 4):
        raise ValueError(f"{label}: channel_post.lead_paragraphs must have 1..4 paragraphs")
    leads = tuple(str(p).strip() for p in lead_raw if str(p).strip())
    if len(leads) != len(lead_raw):
        raise ValueError(f"{label}: empty paragraph in lead_paragraphs")
    if not quote_text or not quote_attribution:
        raise ValueError(f"{label}: channel_post requires quote_text and quote_attribution")
    if not expandable_header:
        raise ValueError(f"{label}: channel_post requires expandable_header")
    if not isinstance(points_raw, list) or not (3 <= len(points_raw) <= 6):
        raise ValueError(f"{label}: channel_post.expandable_points must have 3..6 items")

    points: list[ExpandablePoint] = []
    for idx, entry in enumerate(points_raw):
        if not isinstance(entry, Mapping):
            raise ValueError(f"{label}: expandable_points[{idx}] must be an object")
        lead = str(entry.get("lead") or "").strip()
        body = str(entry.get("body") or "").strip()
        if not lead or not body:
            raise ValueError(f"{label}: expandable_points[{idx}] requires non-empty lead and body")
        points.append(ExpandablePoint(lead=lead, body=body))

    if not cta_prefix or not cta_link_label:
        raise ValueError(f"{label}: channel_post requires cta_prefix and cta_link_label")

    return ChannelPostSpec(
        headline=headline,
        lead_paragraphs=leads,
        quote_text=quote_text,
        quote_attribution=quote_attribution,
        expandable_header=expandable_header,
        expandable_points=tuple(points),
        cta_prefix=cta_prefix,
        cta_link_label=cta_link_label,
    )


def load_telegraph_queue(queue_path: Path, repo_root: Path) -> list[TelegraphQueueItem]:
    raw = json.loads(queue_path.read_text(encoding="utf-8"))
    if raw.get("schema_name") != TELEGRAPH_QUEUE_SCHEMA or raw.get("schema_version") != 1:
        raise ValueError(f"{queue_path}: unsupported Telegraph queue schema")
    if raw.get("project_key") != PROJECT_KEY or raw.get("channel_username") != CHANNEL_USERNAME:
        raise ValueError(f"{queue_path}: project/channel mismatch")

    items_raw = raw.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        raise ValueError(f"{queue_path}: queue items must be non-empty")

    seen_ids: set[str] = set()
    items: list[TelegraphQueueItem] = []
    for entry in items_raw:
        pub_id = str(entry.get("publication_id") or "")
        if not pub_id.startswith("lordchrist-") or pub_id in seen_ids:
            raise ValueError(f"{queue_path}: invalid or duplicate publication_id {pub_id!r}")
        seen_ids.add(pub_id)

        sched_raw = entry.get("scheduled_on_moscow")
        sched = date.fromisoformat(sched_raw) if isinstance(sched_raw, str) else None
        status = str(entry.get("status") or "")
        if status not in {"ready", "planned"}:
            raise ValueError(f"{pub_id}: unknown status {status!r}")
        is_canary = bool(entry.get("is_canary", False))

        if status == "planned":
            items.append(
                TelegraphQueueItem(
                    publication_id=pub_id,
                    ordinal=int(entry["ordinal"]),
                    scheduled_on=sched,
                    status=status,
                    is_canary=is_canary,
                )
            )
            continue

        art_ref = entry.get("article") or {}
        cov_ref = entry.get("cover") or {}
        post_raw = entry.get("channel_post") or {}

        art_path = Path(str(art_ref["path"]))
        cov_path = Path(str(cov_ref["path"]))
        art_bytes = (repo_root / art_path).read_bytes()
        cov_bytes = (repo_root / cov_path).read_bytes()

        expected_art_blob = str(art_ref["git_blob_sha"])
        expected_cov_blob = str(cov_ref["git_blob_sha"])
        if _git_blob_sha(art_bytes) != expected_art_blob:
            raise ValueError(f"{pub_id}: article bytes differ from reviewed git_blob_sha")
        if _git_blob_sha(cov_bytes) != expected_cov_blob:
            raise ValueError(f"{pub_id}: cover bytes differ from reviewed git_blob_sha")
        if not cov_bytes.startswith(JPEG_MAGIC):
            raise ValueError(f"{pub_id}: cover is not a JPEG image")

        post_spec = _parse_channel_post(post_raw, pub_id)
        # Validate rendered post length right on queue load
        rendered = render_channel_post(post_spec, "https://telegra.ph/preview-placeholder-10-23")
        if not (MIN_TELEGRAM_POST_VISIBLE_CHARS <= rendered.visible_char_count <= MAX_TELEGRAM_POST_VISIBLE_CHARS):
            raise ValueError(f"{pub_id}: rendered channel post length {rendered.visible_char_count} outside bounds")

        items.append(
            TelegraphQueueItem(
                publication_id=pub_id,
                ordinal=int(entry["ordinal"]),
                scheduled_on=sched,
                status=status,
                is_canary=is_canary,
                article_path=art_path,
                article_blob=expected_art_blob,
                cover_path=cov_path,
                cover_blob=expected_cov_blob,
                channel_post=post_spec,
            )
        )
    return items


def _rich_text_to_telegraph_children(content: RichTextContent) -> list[dict[str, Any] | str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, tuple):
        out: list[dict[str, Any] | str] = []
        for item in content:
            out.extend(_rich_text_to_telegraph_children(item))
        return out
    if isinstance(content, RichTextBold):
        return [{"tag": "strong", "children": _rich_text_to_telegraph_children(content.text)}]
    if isinstance(content, RichTextItalic):
        return [{"tag": "em", "children": _rich_text_to_telegraph_children(content.text)}]
    if isinstance(content, RichTextUnderline):
        return [{"tag": "u", "children": _rich_text_to_telegraph_children(content.text)}]
    if isinstance(content, RichTextStrikethrough):
        return [{"tag": "s", "children": _rich_text_to_telegraph_children(content.text)}]
    if isinstance(content, RichTextCode):
        return [{"tag": "code", "children": _rich_text_to_telegraph_children(content.text)}]
    if isinstance(content, RichTextUrl):
        return [
            {
                "tag": "a",
                "attrs": {"href": content.url},
                "children": _rich_text_to_telegraph_children(content.text),
            }
        ]
    return ["".join(iter_text_fragments(content))]


def _validate_telegraph_nodes(nodes: Sequence[dict[str, Any] | str]) -> None:
    for node in nodes:
        if isinstance(node, str):
            continue
        tag = node.get("tag")
        if tag not in ALLOWED_TELEGRAPH_TAGS:
            raise ValueError(f"Unsupported Telegraph tag: {tag!r}")
        children = node.get("children")
        if isinstance(children, list):
            _validate_telegraph_nodes(children)


def build_telegraph_payload(
    repo_root: Path,
    item: TelegraphQueueItem,
    *,
    media_base_url: str,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_url: str = DEFAULT_AUTHOR_URL,
) -> TelegraphPayload:
    if not item.is_ready or item.article_path is None or item.cover_path is None:
        raise ValueError(f"{item.publication_id}: item is not ready")
    if not media_base_url.startswith("https://"):
        raise ValueError(f"media_base_url must be https://, got {media_base_url!r}")

    art_bytes = (repo_root / item.article_path).read_bytes()
    cov_bytes = (repo_root / item.cover_path).read_bytes()
    article = RichArticleDocument.model_validate(json.loads(art_bytes.decode("utf-8")))

    cover_url = f"{media_base_url.rstrip('/')}/{item.cover_path.as_posix()}"
    nodes: list[dict[str, Any] | str] = [{"tag": "figure", "children": [{"tag": "img", "attrs": {"src": cover_url}}]}]

    for block in article.blocks:
        if isinstance(block, RichBlockHeading):
            # H1 is passed as the page `title` above metadata — never duplicate inside body
            if block.size == 1:
                continue
            tag = "h3" if block.size == 2 else "h4"
            plain = "".join(iter_text_fragments(block.text))
            nodes.append({"tag": tag, "children": [plain]})
        elif isinstance(block, (RichBlockParagraph, RichBlockFooter)):
            nodes.append({"tag": "p", "children": _rich_text_to_telegraph_children(block.text)})
        elif isinstance(block, RichBlockQuote):
            quote_children: list[dict[str, Any] | str] = []
            for idx_b, inner in enumerate(block.blocks):
                if idx_b > 0:
                    quote_children.extend([{"tag": "br"}, {"tag": "br"}])
                if isinstance(inner, (RichBlockParagraph, RichBlockFooter)):
                    quote_children.extend(_rich_text_to_telegraph_children(inner.text))
                else:
                    quote_children.append("".join(iter_text_fragments(inner)))
            if block.credit is not None:
                credit_plain = "".join(iter_text_fragments(block.credit)).strip()
                if not credit_plain.startswith("—"):
                    credit_plain = f"— {credit_plain}"
                quote_children.append({"tag": "br"})
                quote_children.append({"tag": "em", "children": [credit_plain]})
            nodes.append({"tag": "blockquote", "children": quote_children})

    _validate_telegraph_nodes(nodes)
    compact_json = json.dumps(nodes, ensure_ascii=False, separators=(",", ":"))
    utf8_len = len(compact_json.encode("utf-8"))
    if utf8_len > MAX_TELEGRAPH_CONTENT_UTF8_BYTES:
        raise ValueError(
            f"{item.publication_id}: Telegraph content JSON is {utf8_len} UTF-8 bytes "
            f"(ceiling {MAX_TELEGRAPH_CONTENT_UTF8_BYTES})"
        )

    return TelegraphPayload(
        publication_id=item.publication_id,
        title=article.metadata.title,
        author_name=author_name,
        author_url=author_url,
        cover_url=cover_url,
        nodes=nodes,
        compact_content_json=compact_json,
        content_utf8_bytes=utf8_len,
        article_sha256=_sha256_bytes(art_bytes),
        cover_sha256=_sha256_bytes(cov_bytes),
    )


def render_channel_post(spec: ChannelPostSpec, telegraph_url: str) -> RenderedChannelPost:
    if not telegraph_url.startswith("https://telegra.ph/"):
        raise ValueError(f"telegraph_url must start with https://telegra.ph/, got {telegraph_url!r}")

    esc = html.escape
    html_parts: list[str] = [f"<b>{esc(spec.headline)}</b>"]
    plain_parts: list[str] = [spec.headline]

    for para in spec.lead_paragraphs:
        html_parts.append(esc(para))
        plain_parts.append(para)

    quote_plain = f"{spec.quote_text}\n— {spec.quote_attribution}"
    quote_html = f"<blockquote>{esc(spec.quote_text)}\n— <i>{esc(spec.quote_attribution)}</i></blockquote>"
    html_parts.append(quote_html)
    plain_parts.append(quote_plain)

    exp_html_lines = [f"<b>{esc(spec.expandable_header)}</b>"]
    exp_plain_lines = [spec.expandable_header]
    for pt in spec.expandable_points:
        exp_html_lines.append(f"• <b>{esc(pt.lead)}</b> {esc(pt.body)}")
        exp_plain_lines.append(f"• {pt.lead} {pt.body}")

    html_parts.append(f"<blockquote expandable>{chr(10).join(exp_html_lines)}</blockquote>")
    plain_parts.append("\n".join(exp_plain_lines))

    cta_plain = f"{spec.cta_prefix}\n{spec.cta_link_label} →"
    cta_html = f'{esc(spec.cta_prefix)}\n<a href="{esc(telegraph_url, quote=True)}">{esc(spec.cta_link_label)} →</a>'
    html_parts.append(cta_html)
    plain_parts.append(cta_plain)

    full_html = "\n\n".join(html_parts)
    full_plain = "\n\n".join(plain_parts)
    return RenderedChannelPost(
        html_text=full_html,
        plain_text=full_plain,
        visible_char_count=len(full_plain),
        telegraph_url=telegraph_url,
    )


def render_preview_html_page(payload: TelegraphPayload, post: RenderedChannelPost, cover_data_uri_or_url: str) -> str:
    """Build a self-contained interactive visual preview HTML (Channel Card + Instant View Reader)."""

    def node_to_html(node: dict[str, Any] | str) -> str:
        if isinstance(node, str):
            return html.escape(node)
        tag = str(node["tag"])
        attrs = node.get("attrs") or {}
        if tag == "img":
            src = cover_data_uri_or_url if attrs.get("src") == payload.cover_url else str(attrs.get("src", ""))
            return f'<img src="{html.escape(src, quote=True)}" alt="">'
        if tag == "br":
            return "<br>"
        attr_str = "".join(f' {k}="{html.escape(str(v), quote=True)}"' for k, v in attrs.items())
        inner = "".join(node_to_html(ch) for ch in node.get("children", []))
        return f"<{tag}{attr_str}>{inner}</{tag}>"

    article_body_html = "\n".join(node_to_html(n) for n in payload.nodes)
    # Transform expandable blockquote for browser preview click-toggle
    preview_msg_html = post.html_text.replace(
        "<blockquote expandable>",
        '<div class="tg-expandable collapsed" onclick="this.classList.toggle(\'collapsed\')">',
    )
    # Replace only the matching closing tag of expandable blockquote (second blockquote)
    first_close = preview_msg_html.find("</blockquote>")
    second_close = preview_msg_html.find("</blockquote>", first_close + 13)
    if second_close != -1:
        preview_msg_html = (
            preview_msg_html[:second_close]
            + '<span class="tg-exp-hint"></span></div>'
            + preview_msg_html[second_close + 13 :]
        )
    preview_msg_html = preview_msg_html.replace("\n", "<br>\n")

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(payload.title)} — Предпросмотр @lordchrist + Telegra.ph</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0e1621; color: #f5f5f5; }}
  .topbar {{ position: sticky; top: 0; z-index: 20; display: flex; gap: 10px; align-items: center; justify-content: center; padding: 12px 16px; background: #17212b; border-bottom: 1px solid #242f3d; flex-wrap: wrap; }}
  .tab {{ border: 1px solid #2b5278; background: #182533; color: #c8d9ea; padding: 8px 16px; border-radius: 999px; cursor: pointer; font-weight: 600; font-size: 14px; }}
  .tab.active {{ background: #2b5278; color: #fff; }}
  .meta-pill {{ font-size: 12px; color: #8ea2b8; }}
  .stage {{ max-width: 780px; margin: 24px auto 64px; padding: 0 16px; }}
  /* Telegram Channel Bubble */
  .tg-wrap {{ max-width: 520px; margin: 0 auto; }}
  .tg-bubble {{ background: #182533; border-radius: 16px; padding: 14px 16px; box-shadow: 0 8px 28px rgba(0,0,0,.35); line-height: 1.5; font-size: 15px; color: #e8eef5; }}
  .tg-chan {{ color: #6ab2f2; font-weight: 700; font-size: 14px; margin-bottom: 8px; display: flex; justify-content: space-between; }}
  .tg-bubble a {{ color: #6ab2f2; text-decoration: none; }}
  .tg-bubble blockquote {{ margin: 6px 0; padding: 8px 12px; border-left: 3px solid #6ab2f2; background: rgba(106,178,242,.10); border-radius: 4px 10px 10px 4px; }}
  .tg-expandable {{ position: relative; margin: 6px 0; padding: 8px 12px 24px; border-left: 3px solid #6ab2f2; background: rgba(106,178,242,.10); border-radius: 4px 10px 10px 4px; cursor: pointer; overflow: hidden; }}
  .tg-expandable.collapsed {{ max-height: 108px; }}
  .tg-expandable.collapsed::after {{ content: "Развернуть конспект ▼"; position: absolute; left: 0; right: 0; bottom: 0; padding: 20px 12px 5px; text-align: right; font-size: 12px; font-weight: 600; color: #6ab2f2; background: linear-gradient(transparent, #1a2c3d 62%); }}
  .tg-expandable:not(.collapsed)::after {{ content: "Свернуть ▲"; position: absolute; right: 12px; bottom: 4px; font-size: 12px; font-weight: 600; color: #6ab2f2; }}
  .iv-card {{ margin-top: 12px; border-left: 3px solid #6ab2f2; background: rgba(106,178,242,.08); border-radius: 4px 12px 12px 4px; padding: 10px 12px; }}
  .iv-site {{ color: #6ab2f2; font-size: 13px; font-weight: 700; }}
  .iv-title {{ font-weight: 700; font-size: 15px; margin: 4px 0 8px; color: #fff; }}
  .iv-card img {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 8px; display: block; }}
  .iv-btn {{ margin-top: 10px; width: 100%; padding: 10px; border: 1px solid rgba(106,178,242,.45); background: rgba(106,178,242,.14); color: #6ab2f2; font-weight: 700; font-size: 14px; letter-spacing: .04em; border-radius: 8px; cursor: pointer; }}
  .iv-btn:hover {{ background: rgba(106,178,242,.25); }}
  /* Telegraph Book View */
  .tph-paper {{ background: #fff; color: #191919; border-radius: 16px; padding: 36px 40px 56px; font-family: Georgia, "Times New Roman", serif; line-height: 1.66; font-size: 18px; box-shadow: 0 12px 38px rgba(0,0,0,.4); }}
  .tph-paper h1 {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 30px; line-height: 1.24; margin: 0 0 10px; }}
  .tph-byline {{ font-family: -apple-system, sans-serif; font-size: 14px; color: #79828b; margin-bottom: 22px; }}
  .tph-byline a {{ color: #79828b; text-decoration: none; border-bottom: 1px solid #cfd6de; }}
  .tph-paper figure {{ margin: 0 -40px 26px; }}
  .tph-paper figure img {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; }}
  .tph-paper h3 {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 22px; margin: 32px 0 12px; color: #111; }}
  .tph-paper p {{ margin: 0 0 16px; }}
  .tph-paper blockquote {{ margin: 22px 0; padding: 2px 0 2px 18px; border-left: 3px solid #222; color: #2b2b2b; }}
  .hidden {{ display: none; }}
</style>
</head>
<body>
<div class="topbar">
  <button class="tab active" id="btn-post" onclick="showTab('post')">1. Пост в ленте @lordchrist</button>
  <button class="tab" id="btn-iv" onclick="showTab('iv')">2. Книжный ридер Instant View (⚡ ПОСМОТРЕТЬ)</button>
  <span class="meta-pill">Пост: {post.visible_char_count} зн. · Статья Telegra.ph: {payload.content_utf8_bytes:,} байт UTF-8 / 60 000</span>
</div>
<div class="stage">
  <div id="view-post" class="tg-wrap">
    <div class="tg-bubble">
      <div class="tg-chan"><span>Господь Бог (@lordchrist)</span><span>Stories ✓</span></div>
      {preview_msg_html}
      <div class="iv-card">
        <div class="iv-site">Telegra.ph</div>
        <div class="iv-title">{html.escape(payload.title)}</div>
        <img src="{html.escape(cover_data_uri_or_url, quote=True)}" alt="">
        <button class="iv-btn" onclick="showTab('iv')">⚡ ПОСМОТРЕТЬ</button>
      </div>
    </div>
  </div>
  <div id="view-iv" class="tph-paper hidden">
    <h1>{html.escape(payload.title)}</h1>
    <div class="tph-byline"><a href="{html.escape(payload.author_url, quote=True)}">{html.escape(payload.author_name)}</a> · Серия «Стивен Чарнок. О бытии Бога»</div>
    {article_body_html}
  </div>
</div>
<script>
function showTab(which) {{
  document.getElementById('view-post').classList.toggle('hidden', which !== 'post');
  document.getElementById('view-iv').classList.toggle('hidden', which !== 'iv');
  document.getElementById('btn-post').classList.toggle('active', which === 'post');
  document.getElementById('btn-iv').classList.toggle('active', which === 'iv');
  window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}
</script>
</body>
</html>
"""


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
            "schema_version": 1,
            "project_key": PROJECT_KEY,
            "entries": {},
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Ожидался JSON-объект в ledger: {path}")
    if not isinstance(data.get("entries"), dict):
        data["entries"] = {}
    return data


def save_ledger(path: Path, ledger: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_telegraph_token(
    transport: HttpTransport,
    *,
    explicit_token: str | None = None,
    telegraph_api_base: str = DEFAULT_TELEGRAPH_API_BASE,
    short_name: str = DEFAULT_SHORT_NAME,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_url: str = DEFAULT_AUTHOR_URL,
) -> str:
    token = (explicit_token or "").strip()
    if token:
        resp = transport.post_multipart(
            f"{telegraph_api_base.rstrip('/')}/getAccountInfo",
            {"access_token": token.encode("utf-8")},
        )
        if not resp.get("ok"):
            raise RuntimeError(f"Telegraph getAccountInfo rejected token: {resp.get('error')}")
        return token

    resp = transport.post_multipart(
        f"{telegraph_api_base.rstrip('/')}/createAccount",
        {
            "short_name": short_name.encode("utf-8"),
            "author_name": author_name.encode("utf-8"),
            "author_url": author_url.encode("utf-8"),
        },
    )
    if not resp.get("ok") or not isinstance(resp.get("result"), dict):
        raise RuntimeError(f"Telegraph createAccount failed: {resp}")
    created = str(resp["result"].get("access_token") or "").strip()
    if not created:
        raise RuntimeError("Telegraph createAccount returned empty access_token")
    return created


def _split_nodes_at_middle_heading(
    nodes: Sequence[dict[str, Any] | str],
) -> tuple[list[dict[str, Any] | str], list[dict[str, Any] | str]]:
    """Split Telegraph nodes cleanly at the middle ``<h3>`` boundary without losing a single word."""
    total_chars = sum(len(json.dumps(n, ensure_ascii=False)) for n in nodes)
    half = total_chars // 2
    running = 0
    best_idx: int | None = None
    best_dist = total_chars

    for idx, node in enumerate(nodes):
        if idx >= 2 and isinstance(node, dict) and node.get("tag") == "h3":
            dist = abs(running - half)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        running += len(json.dumps(node, ensure_ascii=False))

    split_at = best_idx if best_idx is not None else max(1, len(nodes) // 2)
    return list(nodes[:split_at]), list(nodes[split_at:])


def publish_telegraph_page(
    transport: HttpTransport,
    payload: TelegraphPayload,
    *,
    access_token: str,
    existing_path: str | None = None,
    telegraph_api_base: str = DEFAULT_TELEGRAPH_API_BASE,
) -> tuple[str, str]:
    status_code, head_bytes = transport.get_status(payload.cover_url)
    if status_code != 200 or not head_bytes.startswith(JPEG_MAGIC):
        raise RuntimeError(
            f"{payload.publication_id}: public cover URL {payload.cover_url} is not reachable as JPEG (HTTP {status_code})"
        )

    def _call_page(
        title: str, nodes: Sequence[dict[str, Any] | str], path_override: str | None = None
    ) -> dict[str, Any]:
        body_bytes = json.dumps(list(nodes), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        fields: dict[str, bytes] = {
            "access_token": access_token.encode("utf-8"),
            "title": title.encode("utf-8"),
            "author_name": payload.author_name.encode("utf-8"),
            "author_url": payload.author_url.encode("utf-8"),
            "content": body_bytes,
            "return_content": b"false",
        }
        method = f"editPage/{path_override.lstrip('/')}" if path_override else "createPage"
        return transport.post_multipart(f"{telegraph_api_base.rstrip('/')}/{method}", fields)

    resp = _call_page(payload.title, payload.nodes, existing_path if access_token else None)
    if not resp.get("ok") and str(resp.get("error") or "") == "CONTENT_TOO_BIG":
        part1_nodes, part2_nodes = _split_nodes_at_middle_heading(payload.nodes)
        resp2 = _call_page(f"{payload.title} (окончание)", part2_nodes)
        if not resp2.get("ok") or not isinstance(resp2.get("result"), dict):
            raise RuntimeError(f"Telegraph createPage part 2 failed: {resp2}")
        part2_url = str(resp2["result"].get("url") or "").strip()
        if not part2_url.startswith("https://telegra.ph/"):
            raise RuntimeError(f"Invalid Telegraph part 2 URL: {resp2}")
        part1_with_link = [
            *part1_nodes,
            {"tag": "hr"},
            {
                "tag": "p",
                "children": [
                    {
                        "tag": "strong",
                        "children": [
                            {
                                "tag": "a",
                                "attrs": {"href": part2_url},
                                "children": ["Читать окончание главы →"],
                            }
                        ],
                    }
                ],
            },
        ]
        resp = _call_page(payload.title, part1_with_link, existing_path if access_token else None)

    if not resp.get("ok") or not isinstance(resp.get("result"), dict):
        raise RuntimeError(f"Telegraph page publish failed: {resp}")

    result = resp["result"]
    url = str(result.get("url") or "").strip()
    page_path = str(result.get("path") or "").strip()
    if not url.startswith("https://telegra.ph/") or not page_path:
        raise RuntimeError(f"Telegraph returned invalid page result: {result}")

    page_status, _ = transport.get_status(url)
    if page_status != 200:
        raise RuntimeError(f"Published Telegraph page {url} returned HTTP {page_status}")
    return url, page_path


def publish_channel_message(
    transport: HttpTransport,
    *,
    bot_token: str,
    expected_bot_id: int,
    expected_chat_id: int,
    rendered_post: RenderedChannelPost,
    telegram_api_base: str = DEFAULT_TELEGRAM_API_BASE,
    show_preview_above_text: bool = False,
    preview_refresh_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    base = f"{telegram_api_base.rstrip('/')}/bot{bot_token}"
    me = transport.read_json(f"{base}/getMe", {})
    if not me.get("ok") or int((me.get("result") or {}).get("id", 0)) != expected_bot_id:
        raise RuntimeError("Telegram bot credential identity mismatch")

    chat = transport.read_json(f"{base}/getChat", {"chat_id": expected_chat_id})
    if not chat.get("ok") or int((chat.get("result") or {}).get("id", 0)) != expected_chat_id:
        raise ValueError("Telegram target chat verification failed")

    link_preview_options = {
        "is_disabled": False,
        "url": rendered_post.telegraph_url,
        "prefer_large_media": True,
        "show_above_text": show_preview_above_text,
    }
    sent = transport.post_json(
        f"{base}/sendMessage",
        {
            "chat_id": expected_chat_id,
            "text": rendered_post.html_text,
            "parse_mode": "HTML",
            "link_preview_options": link_preview_options,
        },
    )
    if not sent.get("ok") or not isinstance(sent.get("result"), dict):
        raise RuntimeError(f"Telegram sendMessage failed: {sent}")

    msg = sent["result"]
    msg_id = int(msg["message_id"])

    # If Telegram's Instant View crawler hadn't attached link preview on initial send, refresh once after warm delay
    if not msg.get("link_preview_options") and preview_refresh_delay_seconds > 0:
        time.sleep(preview_refresh_delay_seconds)
        refreshed = transport.post_json(
            f"{base}/editMessageText",
            {
                "chat_id": expected_chat_id,
                "message_id": msg_id,
                "text": rendered_post.html_text,
                "parse_mode": "HTML",
                "link_preview_options": link_preview_options,
            },
        )
        if refreshed.get("ok") and isinstance(refreshed.get("result"), dict):
            msg = refreshed["result"]

    return {
        "chat_id": expected_chat_id,
        "message_id": msg_id,
        "telegraph_url": rendered_post.telegraph_url,
    }


def _find_item(items: Sequence[TelegraphQueueItem], publication_id: str) -> TelegraphQueueItem:
    for item in items:
        if item.publication_id == publication_id:
            return item
    raise LookupError(f"Unknown publication_id: {publication_id!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m video_channel_manager.lordchrist_telegraph_publisher")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-account", help="Create a persistent Telegraph account locally and print secret value")
    p_init.add_argument("--short-name", default=DEFAULT_SHORT_NAME)
    p_init.add_argument("--author-name", default=DEFAULT_AUTHOR_NAME)
    p_init.add_argument("--author-url", default=DEFAULT_AUTHOR_URL)

    for name in ("preview", "publish-telegraph-only", "publish"):
        p = sub.add_parser(name)
        p.add_argument("--repo-root", type=Path, default=Path("."))
        p.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
        p.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
        p.add_argument("--publication-id", required=True)
        p.add_argument("--media-base-url", required=True)
        if name == "preview":
            p.add_argument("--html-out", type=Path)
        if name == "publish":
            p.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
            p.add_argument("--binding", type=Path, default=DEFAULT_BINDING_PATH)
            p.add_argument("--confirm", required=True)
            p.add_argument("--outcome", type=Path)

    args = parser.parse_args(argv)

    if args.command == "init-account":
        transport = HttpxLiveTransport()
        token = ensure_telegraph_token(
            transport,
            short_name=args.short_name,
            author_name=args.author_name,
            author_url=args.author_url,
        )
        print(
            json.dumps(
                {
                    "secret_name": "LORDCHRIST_TELEGRAPH_ACCESS_TOKEN",
                    "access_token": token,
                    "author_name": args.author_name,
                    "author_url": args.author_url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    items = load_telegraph_queue(args.repo_root / args.queue, args.repo_root)
    item = _find_item(items, args.publication_id)
    assert item.channel_post is not None and item.cover_path is not None
    payload = build_telegraph_payload(args.repo_root, item, media_base_url=args.media_base_url)

    if args.command == "preview":
        post = render_channel_post(item.channel_post, "https://telegra.ph/preview-placeholder-10-23")
        if args.html_out:
            import base64

            b64 = base64.b64encode((args.repo_root / item.cover_path).read_bytes()).decode("ascii")
            html_doc = render_preview_html_page(payload, post, f"data:image/jpeg;base64,{b64}")
            args.html_out.parent.mkdir(parents=True, exist_ok=True)
            args.html_out.write_text(html_doc, encoding="utf-8")
        print(
            json.dumps(
                {
                    "publication_id": item.publication_id,
                    "title": payload.title,
                    "telegraph_utf8_bytes": payload.content_utf8_bytes,
                    "channel_post_visible_chars": post.visible_char_count,
                },
                ensure_ascii=False,
            )
        )
        return 0

    ledger_path = args.ledger if args.ledger.is_absolute() else (args.repo_root / args.ledger)
    ledger = load_ledger(ledger_path)
    existing = ledger["entries"].get(item.publication_id) or {}

    if args.command == "publish" and existing.get("telegram_message_id"):
        raise RuntimeError(
            f"{item.publication_id} was already published to @lordchrist "
            f"(message_id={existing['telegram_message_id']}, url={existing.get('telegraph_url')})"
        )

    transport = HttpxLiveTransport()
    explicit_token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip() or None
    token = ensure_telegraph_token(transport, explicit_token=explicit_token)

    telegraph_url, telegraph_path = publish_telegraph_page(
        transport,
        payload,
        access_token=token,
        existing_path=existing.get("telegraph_path") if explicit_token else None,
    )

    entry_record: dict[str, Any] = {
        **existing,
        "publication_id": item.publication_id,
        "title": payload.title,
        "telegraph_url": telegraph_url,
        "telegraph_path": telegraph_path,
        "article_sha256": payload.article_sha256,
        "cover_sha256": payload.cover_sha256,
        "telegraph_updated_at_utc": datetime.now(UTC).isoformat(),
    }

    if args.command == "publish-telegraph-only":
        ledger["entries"][item.publication_id] = entry_record
        save_ledger(ledger_path, ledger)
        print(
            json.dumps(
                {
                    "mode": "telegraph_only",
                    "publication_id": item.publication_id,
                    "telegraph_url": telegraph_url,
                    "telegraph_utf8_bytes": payload.content_utf8_bytes,
                },
                ensure_ascii=False,
            )
        )
        return 0

    expected_confirm = f"PUBLISH:{item.publication_id}"
    if args.confirm != expected_confirm:
        raise ValueError(f"Confirmation mismatch: expected {expected_confirm!r}")

    profile = load_channel_profile(args.repo_root / args.profile)
    binding = load_target_binding(args.repo_root / args.binding, profile=profile)
    bot_token = os.environ.get(profile.bot_token_env, "").strip()
    if not bot_token:
        raise ValueError(f"Missing environment variable {profile.bot_token_env}")

    rendered_post = render_channel_post(item.channel_post, telegraph_url)
    tg_result = publish_channel_message(
        transport,
        bot_token=bot_token,
        expected_bot_id=binding.bot_id,
        expected_chat_id=binding.chat_id,
        rendered_post=rendered_post,
    )
    entry_record["telegram_chat_id"] = tg_result["chat_id"]
    entry_record["telegram_message_id"] = tg_result["message_id"]
    entry_record["telegram_published_at_utc"] = datetime.now(UTC).isoformat()
    ledger["entries"][item.publication_id] = entry_record
    save_ledger(ledger_path, ledger)

    if args.outcome:
        args.outcome.parent.mkdir(parents=True, exist_ok=True)
        args.outcome.write_text(json.dumps(entry_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(entry_record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
