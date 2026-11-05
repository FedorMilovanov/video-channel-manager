"""Build an inert 30-card quote review preview; never produce a live release.

This is an editorial reader view, not a TelegramQueue or execution authority.
The canonical reviewed quote and exact historical English anchors are retained.
Any editorial context that is not part of the author's quoted words is kept as
research evidence, not inserted into Telegram message copy.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUDITS = Path("docs/audits")
V5_PREVIEW = AUDITS / "2026-11-05-lordchrist-30-card-editorial-preview-v5-inert.json"
V5_INDEX = AUDITS / "2026-11-05-lordchrist-30-quote-editorial-candidate-index-v5.json"
V5_SOURCE = AUDITS / "2026-11-05-lordchrist-30-quote-independent-collation-v5.json"
RIGHTS = AUDITS / "2026-11-06-lordchrist-30-edition-rights-provenance-v1.json"
DEFAULT_OUTPUT = AUDITS / "2026-11-06-lordchrist-30-reader-preview-v6-inert.json"


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _load(root: Path, path: Path) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _blob_sha(root: Path, path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD:" + path.as_posix()],
        text=True,
    ).strip()


def _parse_post(text: str, *, sequence: int, author: str) -> tuple[str, str, list[str], str]:
    blocks = [s.strip() for s in text.replace("\r\n", "\n").split("\n\n") if s.strip()]
    attribution_indexes = [i for i, block in enumerate(blocks) if block.startswith("© ")]
    if len(attribution_indexes) != 1:
        raise ValueError(f"post {sequence}: require one marked source attribution")
    index = attribution_indexes[0]
    if index != len(blocks) - 2 and index != len(blocks) - 3:
        raise ValueError(f"post {sequence}: unexpected extra blocks after attribution")
    if not 2 <= index <= 4:
        raise ValueError(f"post {sequence}: expected two to four complete quotation paragraphs")
    quote_paragraphs = blocks[:index]
    if any(len(block) < 80 for block in quote_paragraphs):
        raise ValueError(f"post {sequence}: short/dangling quotation paragraph")
    quote = "\n\n".join(quote_paragraphs)
    if not quote.startswith("«") or not quote.endswith("»"):
        raise ValueError(f"post {sequence}: require an intact quotation boundary")
    attribution = blocks[index].removeprefix("© ")
    if not attribution.startswith(author + ", «") or "»" not in attribution:
        raise ValueError(f"post {sequence}: source attribution mismatch")
    notes = blocks[index + 1 : -1]
    tags = blocks[-1]
    if not tags.startswith("#"):
        raise ValueError(f"post {sequence}: hashtags missing from last block")
    if not 2 <= len(tags.split()) <= 8:
        raise ValueError(f"post {sequence}: invalid hashtag count")
    if any(not tag.startswith("#") for tag in tags.split()):
        raise ValueError(f"post {sequence}: invalid hashtag block")
    return quote, attribution, notes, tags


def make_reader_preview(root: Path) -> dict[str, Any]:
    preview = _load(root, V5_PREVIEW)
    index = _load(root, V5_INDEX)
    source = _load(root, V5_SOURCE)
    rights = _load(root, RIGHTS)
    if any(
        [
            index["approved_new_queue"],
            index["provider_write_authorization"],
            preview["provider_write_authorization"],
            rights["provider_write_authorization"],
            rights["rights_review_complete"],
        ]
    ):
        raise ValueError("candidate review builder requires all provider gates closed")

    posts, records, excerpts, licenses = (
        preview["posts"],
        index["entries"],
        source["source_evidence"],
        rights["entries"],
    )
    if not len(posts) == len(records) == len(excerpts) == len(licenses) == 30:
        raise ValueError("all four independent input corpora must contain 30 records")
    cards: list[dict[str, Any]] = []
    for n, (post, record, source_note, legal) in enumerate(
        zip(posts, records, excerpts, licenses, strict=True), start=1
    ):
        if not (post["sequence"] == record["sequence"] == source_note["sequence"] == legal["sequence"] == n):
            raise ValueError(f"post {n}: evidence order changed")
        if any(
            [
                post["publication_id"] != record["original_publication_id"],
                post["publication_id"] != legal["publication_id"],
                post["source"]["url"] != record["candidate_source_url"],
                post["source"]["url"] != source_note["source_url"],
                post["source"]["url"] != legal["candidate_source_url"],
                record["candidate_body_sha256"] != legal["candidate_body_sha256"],
                record["eligible_for_release"],
                legal["provider_write_authorization"],
                legal["clearance_status"] != "not_approved",
            ]
        ):
            raise ValueError(f"post {n}: source or approval evidence diverged")

        quote, attribution, notes, hashtags = _parse_post(post["text"], sequence=n, author=post["source"]["author"])
        if _digest(quote[1:-1]) != record["candidate_body_sha256"]:
            raise ValueError(f"post {n}: exact source-quoted text SHA changed")
        paragraphs = quote.split("\n\n")
        html_quote = html.escape(quote).replace("\n\n", "\n\n")
        post_html = (
            "<blockquote>"
            + html_quote
            + "</blockquote>\n"
            + "<i>— "
            + html.escape(attribution)
            + "</i>\n\n"
            + html.escape(hashtags)
        )
        reader_plain = quote + "\n— " + attribution + "\n\n" + hashtags
        if len(reader_plain) > 4096:
            raise ValueError(f"post {n}: exceeds Telegram 4096 visible-character limit")
        if "Контекст:" in post_html or "Примечание редакции:" in post_html:
            raise ValueError(f"post {n}: editor notes leaked into reader message")
        cards.append(
            {
                "sequence": n,
                "publication_id": post["publication_id"],
                "historical_english_span_sha256": source_note["english_span_sha256"],
                "quote_sha256": record["candidate_body_sha256"],
                "candidate_render_html_sha256": _digest(post_html),
                "source_url": post["source"]["url"],
                "source_anchor_start": record["candidate_source_anchor_start"],
                "source_anchor_end": record["candidate_source_anchor_end"],
                "original_work_title": rights["groups"][legal["work_id"]]["historical_title"],
                "reader_attribution": "— " + attribution,
                "quoted_paragraph_count": len(paragraphs),
                "visible_char_count": len(reader_plain),
                "reader_html_preview": post_html,
                "research_notes_excluded_from_reader_message": notes,
                "rights_review_status": "pending",
                "final_editor_approval": False,
                "provider_write_authorization": False,
            }
        )
    ids = [entry["publication_id"] for entry in cards]
    if len(set(ids)) != 30:
        raise ValueError("duplicate publication identity in preview")
    digest_payload = [
        {
            "publication_id": p["publication_id"],
            "quote_sha256": p["quote_sha256"],
            "candidate_render_html_sha256": p["candidate_render_html_sha256"],
            "historical_english_span_sha256": p["historical_english_span_sha256"],
        }
        for p in cards
    ]
    return {
        "schema_name": "video-channel-manager.lordchrist-30-reader-preview-v6-inert",
        "schema_version": 1,
        "observed_on": "2026-11-06",
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "preview_digest": _digest(_canonical(digest_payload)),
        "new_release_digest": None,
        "approved_new_queue": False,
        "full_bilingual_review_complete": False,
        "rights_review_complete": False,
        "responsible_editor_approval": False,
        "provider_write_authorization": False,
        "read_only": True,
        "source_sha": {
            "v5_index_git_blob": _blob_sha(root, V5_INDEX),
            "v5_preview_git_blob": _blob_sha(root, V5_PREVIEW),
            "v5_collation_git_blob": _blob_sha(root, V5_SOURCE),
            "rights_provenance_git_blob": _blob_sha(root, RIGHTS),
        },
        "rendering_note": (
            "Source quote words are unchanged. Research-only editor notes are excluded. "
            "A Telegram-ready HTML visualization is NOT a TelegramQueue, rights approval, "
            "publisher activation, state mutation, or permission to dispatch."
        ),
        "posts": cards,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provider-inert 30-card source quote preview")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = make_reader_preview(args.root)
    # Only explicit local artifact generation; no access to network, GitHub or Telegram.
    if args.out is not None:
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    else:
        print(
            _canonical(
                {
                    "preview_digest": result["preview_digest"],
                    "candidate_count": len(result["posts"]),
                    "provider_write_authorization": result["provider_write_authorization"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
