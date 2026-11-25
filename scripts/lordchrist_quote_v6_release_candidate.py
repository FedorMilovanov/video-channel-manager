"""Deterministic, **provider-inert** v6 quote release-candidate proof.

The candidate binds all thirty approved-for-review reader renderings by exact
source identifiers and hashes.  It is intentionally not a TelegramQueue,
a production workflow, an editor's signoff, or a provider execution grant.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
READER_FILE = Path("docs/audits/2026-11-06-lordchrist-30-reader-preview-v6-inert.json")
RIGHTS_FILE = Path("docs/audits/2026-11-06-lordchrist-30-edition-rights-provenance-v1.json")
PROFILE_FILE = Path("content/telegram/channels/lordchrist.json")
DEFAULT_OUT = Path("docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"^lordchrist-[a-z0-9][a-z0-9-]{4,100}$")


def _sha(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def _canonical(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(root: Path, relative: Path) -> dict[str, Any]:
    result = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"{relative} is not an object")
    return result


def _blob_sha(root: Path, relative: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD:" + relative.as_posix()],
        text=True,
    ).strip()


class _TelegramQuoteHtml(HTMLParser):
    """Allow only one complete blockquote and one sibling italic attribution."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth: str | None = None
        self.opened: list[str] = []
        self.closed: list[str] = []
        self.text_parts: list[str] = []
        self.quote_parts: list[str] = []
        self.attribution_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ("blockquote", "i") or attrs or self.depth is not None:
            raise ValueError("unexpected Telegram HTML tag, attribute, or nested entity")
        if self.opened == ["blockquote"] and tag != "i":
            raise ValueError("HTML attribution must be the second and last entity")
        if self.opened and self.opened != ["blockquote"]:
            raise ValueError("unexpected additional Telegram HTML entity")
        if not self.opened and tag != "blockquote":
            raise ValueError("Telegram HTML must open with its quote entity")
        self.opened.append(tag)
        self.depth = tag

    def handle_endtag(self, tag: str) -> None:
        if self.depth != tag:
            raise ValueError("unmatched Telegram HTML closing tag")
        self.closed.append(tag)
        self.depth = None

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self.depth == "blockquote":
            self.quote_parts.append(data)
        elif self.depth == "i":
            self.attribution_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(html.unescape(f"&#{name};"))


def validate_provider_html(html_text: str, *, expected_attribution: str) -> tuple[str, int]:
    parser = _TelegramQuoteHtml()
    parser.feed(html_text)
    parser.close()
    if parser.depth is not None or parser.opened != ["blockquote", "i"] or parser.closed != parser.opened:
        raise ValueError("Telegram HTML must contain exactly one complete quote and attribution")
    visible = "".join(parser.text_parts)
    quoted = "".join(parser.quote_parts)
    if not quoted.startswith("«") or not quoted.endswith("»"):
        raise ValueError("source quote boundaries lost")
    if "".join(parser.attribution_parts) != expected_attribution:
        raise ValueError("reader-facing attribution no longer matches reviewed v6")
    if not visible.startswith(quoted + "\n" + expected_attribution + "\n\n#"):
        raise ValueError("hashtag or attribution spacing violates quote-v6 contract")
    if "<" in visible and "</" in visible:
        raise ValueError("unescaped HTML fragments remain in reader copy")
    utf16_units = len(visible.encode("utf-16-le")) // 2
    if not 100 <= utf16_units <= 4096:
        raise ValueError("Telegram visible-length limit exceeded")
    return visible, utf16_units


def build_candidate(root: Path) -> dict[str, Any]:
    reader, rights, profile = (
        _load(root, READER_FILE),
        _load(root, RIGHTS_FILE),
        _load(root, PROFILE_FILE),
    )
    if (
        reader["schema_name"] != "video-channel-manager.lordchrist-30-reader-preview-v6-inert"
        or reader["project_key"] != "lord-god-strength"
        or profile["project_key"] != "lord-god-strength"
        or reader["channel_username"] != "@lordchrist"
        or profile["channel_username"] != "@lordchrist"
    ):
        raise ValueError("canonical LordChrist project/channel identity mismatch")
    forbidden = (
        "approved_new_queue",
        "full_bilingual_review_complete",
        "rights_review_complete",
        "responsible_editor_approval",
        "provider_write_authorization",
    )
    if reader["read_only"] is not True or any(reader[field] is not False for field in forbidden):
        raise ValueError("v6 input must remain provider-inert and unapproved")
    if rights["release_hold_active"] is not True or rights["provider_write_authorization"] is not False:
        raise ValueError("historical rights hold must remain active")
    if profile["provider_writes_authorized"] is not False:
        raise ValueError("profile must not grant publication rights")
    if rights["approved_new_queue"] or rights["new_release_digest"] is not None:
        raise ValueError("rights ledger must not mint a release digest")
    src_posts, rights_posts = reader["posts"], rights["entries"]
    if len(src_posts) != 30 or len(rights_posts) != 30:
        raise ValueError("exactly thirty source-bound reader cards required")
    entries: list[dict[str, Any]] = []
    for index, (post, legal) in enumerate(zip(src_posts, rights_posts, strict=True), 1):
        if post["sequence"] != index or legal["sequence"] != index:
            raise ValueError("sequence mismatch")
        pub_id = post["publication_id"]
        if not ID_PATTERN.fullmatch(pub_id) or pub_id != legal["publication_id"]:
            raise ValueError(f"unexpected publication ID: {pub_id}")
        for field in ("quote_sha256", "historical_english_span_sha256", "candidate_render_html_sha256"):
            if not HASH_PATTERN.fullmatch(post[field]):
                raise ValueError("invalid immutable source digest")
        if legal["candidate_body_sha256"] != post["quote_sha256"]:
            raise ValueError(f"unbound historical quotation: {pub_id}")
        if legal["candidate_source_url"] != post["source_url"]:
            raise ValueError(f"source URL changed: {pub_id}")
        if legal["clearance_status"] != "not_approved" or legal["provider_write_authorization"]:
            raise ValueError(f"unreviewed rights state changed: {pub_id}")
        html_text = post["reader_html_preview"]
        if _sha(html_text) != post["candidate_render_html_sha256"]:
            raise ValueError(f"provider HTML changed after review: {pub_id}")
        visible, utf16_units = validate_provider_html(html_text, expected_attribution=post["reader_attribution"])
        if len(visible) != post["visible_char_count"]:
            raise ValueError(f"visible text changed after review: {pub_id}")
        if post["provider_write_authorization"] or post["final_editor_approval"]:
            raise ValueError(f"card approval must be independently granted: {pub_id}")
        entry = {
            "sequence": index,
            "publication_id": pub_id,
            "source_url": post["source_url"],
            "historical_english_span_sha256": post["historical_english_span_sha256"],
            "source_anchors": {
                "start": post["source_anchor_start"],
                "end": post["source_anchor_end"],
            },
            "quoted_russian_sha256": post["quote_sha256"],
            "source_render_html_sha256": post["candidate_render_html_sha256"],
            "candidate_payload_sha256": _sha(
                _canonical(
                    {
                        "publication_id": pub_id,
                        "project_key": reader["project_key"],
                        "channel_username": reader["channel_username"],
                        "html_text": html_text,
                        "parse_mode": "HTML",
                        "link_preview_disabled": True,
                    }
                )
            ),
            "parse_mode": "HTML",
            "link_preview_disabled": True,
            "html_text": html_text,
            "visible_utf16_units": utf16_units,
            "rights_review_complete": False,
            "responsible_editor_approval": False,
            "provider_write_authorization": False,
        }
        entries.append(entry)
    ids = [p["publication_id"] for p in entries]
    if len(set(ids)) != 30:
        raise ValueError("duplicate quote identity")
    candidate_digest = _sha(
        _canonical(
            [
                {
                    "publication_id": p["publication_id"],
                    "candidate_payload_sha256": p["candidate_payload_sha256"],
                    "quoted_russian_sha256": p["quoted_russian_sha256"],
                }
                for p in entries
            ]
        )
    )
    return {
        "schema_name": "video-channel-manager.lordchrist-quote-v6-payload-candidate-inert",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "channel_profile_path": PROFILE_FILE.as_posix(),
        "channel_profile_git_blob_sha1": _blob_sha(root, PROFILE_FILE),
        "source_reader_preview_path": READER_FILE.as_posix(),
        "source_reader_preview_git_blob_sha1": _blob_sha(root, READER_FILE),
        "source_reader_preview_digest": reader["preview_digest"],
        "rights_ledger_git_blob_sha1": _blob_sha(root, RIGHTS_FILE),
        "candidate_digest": candidate_digest,
        "new_release_digest": None,
        "approved_new_queue": False,
        "rights_review_complete": False,
        "full_bilingual_review_complete": False,
        "responsible_editor_approval": False,
        "provider_write_authorization": False,
        "historical_v4_replay_authorized": False,
        "live_schedule_enabled": False,
        "read_only": True,
        "pending_prerequisites": [
            "Verify exact primary text edition, human-reviewed Russian translations and rights for each ID",
            "Independent responsible-editor acceptance of all thirty exact provider payload digests",
            "Design reviewed v6 state-preserving activation and no-replay transition",
            "Recheck protected provider ledger, same-day channel load, and any unresolved cross-track effects",
            "Bind one explicitly authorized new release digest and single producer before any send",
        ],
        "first_canary_candidate": {
            "sequence": 1,
            "publication_id": entries[0]["publication_id"],
            "candidate_payload_sha256": entries[0]["candidate_payload_sha256"],
            "provider_write_authorization": False,
        },
        "items": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a provider-inert, exact quote-v6 payload candidate")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    value = build_candidate(args.root)
    if args.out is None:
        print(
            _canonical(
                {
                    "candidate_digest": value["candidate_digest"],
                    "count": len(value["items"]),
                    "live_schedule_enabled": False,
                    "provider_write_authorization": False,
                }
            )
        )
    else:
        args.out.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
