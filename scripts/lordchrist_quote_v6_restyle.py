"""Source-preserving, provider-inert redesign of the 19 pending LordChrist quote-v6 cards.

NEVER use this preview as a Telegram queue or authorize provider effects. Before
activation, an explicit guarded state-ledger migration is required: the existing
queue binds frozen hashes for all 30 cards, including the 11 published cards.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from scripts.lordchrist_quote_v6_native_readonly import SOURCE_PATH, build_quote_v6_native_queue

ROOT = Path(__file__).resolve().parents[1]
V1_MANIFEST_PATH = Path("content/telegram/lordchrist/quote-v6-pending-restyle-v1.json")
MANIFEST_PATH = Path("content/telegram/lordchrist/quote-v6-pending-restyle-v2.json")
DEFAULT_PREVIEW = Path("docs/audits/2026-11-18-lordchrist-quote-v6-editorial-v2-inert.json")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _excerpt(original: str, direction: dict[str, Any]) -> str:
    if not original.startswith("«") or not original.endswith("»"):
        raise ValueError("source quote does not have its reviewed outer boundaries")
    words = original[1:-1]
    start, end = direction["excerpt_start"], direction["excerpt_end"]
    if (start is None) != (end is None):
        raise ValueError("start/end must either both be present or both be absent")
    if start is None:
        excerpt = words
    else:
        if words.count(start) != 1 or words.count(end) != 1:
            raise ValueError("excerpt boundaries must each appear exactly once in source")
        i = words.index(start)
        j = words.index(end) + len(end)
        if j <= i:
            raise ValueError("excerpt boundaries are reversed")
        excerpt = words[i:j]
    if not excerpt or excerpt.strip() != excerpt:
        raise ValueError("excerpt must be a clean, contiguous source span")
    if excerpt not in words or words.count(excerpt) != 1:
        raise ValueError("excerpt is not a unique verbatim source span")
    return excerpt


def _emphasize(excerpt: str, bold: str | None, italic: str | None) -> str:
    """Exactly one meaningful emphasis is sufficient; over-formatting is not required."""
    spans: list[tuple[int, int, str]] = []
    for label, needle in (("b", bold), ("i", italic)):
        if needle is None:
            continue
        if not needle or excerpt.count(needle) != 1:
            raise ValueError(f"reviewed emphasis {label} must occur exactly once")
        start = excerpt.index(needle)
        spans.append((start, start + len(needle), label))
    if not spans:
        raise ValueError("at least one meaningful emphasis required")
    spans.sort()
    if len(spans) == 2 and spans[0][1] > spans[1][0]:
        raise ValueError("bold/italic spans overlap; nested or duplicate emphasis is forbidden")
    out: list[str] = []
    position = 0
    for start, end, tag in spans:
        out.append(html.escape(excerpt[position:start], quote=False))
        out.append(f"<{tag}>" + html.escape(excerpt[start:end], quote=False) + f"</{tag}>")
        position = end
    out.append(html.escape(excerpt[position:], quote=False))
    return "".join(out)


def build_restyle_preview(root: Path = ROOT, *, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    original = build_quote_v6_native_queue(root / SOURCE_PATH)
    manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
    if manifest_path == MANIFEST_PATH and (
        manifest.get("editorial_revision") != 2
        or manifest.get("previous_queue_digest")
        != "sha256:62a15d4b19057509fb38023847ccbdbde319f9d428a9d6463074ae11b3940b03"
    ):
        raise ValueError("new editorial revision lacks exact old live-digest binding")
    if (
        manifest.get("schema_name") != "video-channel-manager.lordchrist-quote-v6-pending-restyle"
        or manifest.get("schema_version") != 1
        or manifest.get("project_key") != "lord-god-strength"
        or manifest.get("channel_username") != "@lordchrist"
        or manifest.get("source_candidate_digest") != original.digest
    ):
        raise ValueError("restyle manifest is not bound to the immutable 30-card original")
    baseline = manifest["baseline_published_ids"]
    directions = manifest["pending"]
    if len(baseline) != 11 or len(set(baseline)) != 11:
        raise ValueError("published historical boundary must contain exactly 11 distinct IDs")
    if len(directions) != 19 or len({d["publication_id"] for d in directions}) != 19:
        raise ValueError("must review exactly 19 unique pending entries")
    original_by_id = {p.publication_id: p for p in original.posts}
    if not set(baseline).isdisjoint({d["publication_id"] for d in directions}):
        raise ValueError("published card may not be restyled")
    if set(baseline) | {d["publication_id"] for d in directions} != set(original_by_id):
        raise ValueError("restyle manifest does not cover the exact frozen source")
    published = [p for p in original.posts if p.publication_id in baseline]
    candidates = []
    new_by_id: dict[str, dict[str, Any]] = {}
    for d in directions:
        old = original_by_id[d["publication_id"]]
        if d["sequence"] != old.sequence:
            raise ValueError("restyle sequence differs from source identity")
        body = _excerpt(old.quote_text, d)
        body_html = _emphasize(body, d["bold"], d["italic"])
        tags = d["hashtags"]
        if not 2 <= len(tags) <= 6:
            raise ValueError("2 to 6 intentional hashtags required")
        if any(not tag.startswith("#") or "_" in tag or not tag[1:].isalnum() for tag in tags):
            raise ValueError("tags must be human-readable CamelCase with no underscores")
        if len(set(tags)) != len(tags):
            raise ValueError("duplicate hashtags")
        footer = " ".join(tags)
        rich = body_html + "\n<i>" + html.escape(old.attribution_line, quote=False) + "</i>\n\n" + html.escape(footer)
        plain = body + "\n" + old.attribution_line + "\n\n" + footer
        if "«" == body[0] and "»" == body[-1]:
            raise ValueError("outer quotation marks were not removed")
        if "<blockquote" in rich.lower() or "</blockquote" in rich.lower():
            raise ValueError("the new quote lane forbids wrapping the entire quotation in a quote block")
        if len(plain.encode("utf-16-le")) // 2 > 4096:
            raise ValueError("Telegram message too long")
        payload = {
            "publication_id": old.publication_id,
            "project_key": "lord-god-strength",
            "channel_username": "@lordchrist",
            "html_text": rich,
            "parse_mode": "HTML",
            "link_preview_disabled": True,
        }
        card = {
            "sequence": old.sequence,
            "publication_id": old.publication_id,
            "original_payload_sha256": old.payload_sha256,
            "source_russian_sha256": old.source.original_ru_quote_sha256,
            "source_url": old.source.url,
            "excerpt_sha256": sha(body),
            "excerpt_chars": len(body),
            "original_chars": len(old.quote_text) - 2,
            "excerpt_is_exact_contiguous_source": True,
            "body_html": body_html,
            "html_text": rich,
            "text": plain,
            "render_html_sha256": sha(rich),
            "provider_payload_sha256": sha(canonical(payload)),
            "hashtag_count": len(tags),
        }
        candidates.append(card)
        new_by_id[old.publication_id] = card
    digest_input = [
        {
            "publication_id": p.publication_id,
            "candidate_payload_sha256": new_by_id[p.publication_id]["provider_payload_sha256"]
            if p.publication_id in new_by_id
            else p.payload_sha256,
            "quoted_russian_sha256": p.source.original_ru_quote_sha256,
        }
        for p in original.posts
    ]
    return {
        "schema_name": "video-channel-manager.lordchrist-quote-v6-restyle-inert",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "provider_inert": True,
        "live_queue_mutated": False,
        "state_ledger_mutated": False,
        "original_queue_digest": original.digest,
        "prospective_queue_digest": sha(canonical(digest_input)),
        "published_immutable": [
            {"publication_id": p.publication_id, "payload_sha256": p.payload_sha256} for p in published
        ],
        "pending_restyled_count": len(candidates),
        "items": sorted(candidates, key=lambda p: p["sequence"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check proposed Telegram quote typography without sending")
    parser.add_argument("--out", type=Path, help="Optional output path for inert 19-card review artifact")
    args = parser.parse_args(argv)
    result = build_restyle_preview()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "published_immutable": len(result["published_immutable"]),
                "pending_restyled": result["pending_restyled_count"],
                "original_queue_digest": result["original_queue_digest"],
                "prospective_queue_digest": result["prospective_queue_digest"],
                "provider_inert": result["provider_inert"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
