"""Native, entirely provider-inert bridge for the source-bound thirty quote-v6 cards.

The v6 candidate is not a signed production release.  This module gives the
existing Telegram presentation and immutable-ledger code exact, typed inputs
while deliberately refusing to convey execution authority.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN

SOURCE_PATH = Path("docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json")
NATIVE_SCHEMA = "video-channel-manager.telegram-quote-v6-native-queue"
RENDER_RE = re.compile(r"\A<blockquote>(.*?)</blockquote>\n<i>(.*?)</i>\n\n(.*)\Z", re.DOTALL)
ID_RE = re.compile(r"^lordchrist-[a-z0-9][a-z0-9-]{4,100}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


class QuoteV6Source(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    author: str = Field(min_length=2, max_length=160)
    work: str = Field(min_length=2, max_length=320)
    url: str = Field(pattern=r"^https://")
    original_english_span_sha256: str = Field(pattern=SHA256_PATTERN)
    original_ru_quote_sha256: str = Field(pattern=SHA256_PATTERN)


class QuoteV6NativePost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=30)
    publication_id: str = Field(pattern=ID_RE.pattern)
    title: str = Field(min_length=2, max_length=160)
    text: str = Field(min_length=100, max_length=4096)
    quote_text: str = Field(min_length=50, max_length=3000)
    attribution_line: str = Field(min_length=8, max_length=300)
    hashtags: str = Field(min_length=5, max_length=400)
    html_text: str = Field(min_length=100)
    source_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    render_html_sha256: str = Field(pattern=SHA256_PATTERN)
    source: QuoteV6Source

    @model_validator(mode="after")
    def exact_render_binding(self) -> "QuoteV6NativePost":
        if self.quote_text != self.quote_text.strip():
            raise ValueError("quote contains unreviewed leading/trailing whitespace")
        if not self.quote_text.startswith("«") or not self.quote_text.endswith("»"):
            raise ValueError("quote boundaries missing")
        if self.attribution_line != self.attribution_line.strip() or not self.attribution_line.startswith("— "):
            raise ValueError("attribution must be a single reviewed line prefixed with em dash")
        if "\n" in self.attribution_line:
            raise ValueError("attribution must occupy one line")
        if not self.attribution_line.removeprefix("— ").startswith(self.source.author + ","):
            raise ValueError("source author and reader attribution differ")
        expected_html = (
            "<blockquote>"
            + html.escape(self.quote_text, quote=True)
            + "</blockquote>\n<i>"
            + html.escape(self.attribution_line, quote=True)
            + "</i>\n\n"
            + html.escape(self.hashtags, quote=True)
        )
        if self.html_text != expected_html or self.render_html_sha256 != _sha(expected_html):
            raise ValueError("v6 provider HTML differs from source-bound candidate")
        if self.text != self.quote_text + "\n" + self.attribution_line + "\n\n" + self.hashtags:
            raise ValueError("v6 plain text differs from provider HTML")
        if any(not tag.startswith("#") for tag in self.hashtags.split()) or not 2 <= len(self.hashtags.split()) <= 8:
            raise ValueError("unreviewed v6 hashtag structure")
        if len(self.text.encode("utf-16-le")) // 2 > 4096:
            raise ValueError("Telegram UTF-16 limit exceeded")
        payload = {
            "publication_id": self.publication_id,
            "project_key": "lord-god-strength",
            "channel_username": "@lordchrist",
            "html_text": self.html_text,
            "parse_mode": "HTML",
            "link_preview_disabled": True,
        }
        if self.source_payload_sha256 != _sha(_canonical(payload)):
            raise ValueError("v6 provider payload SHA does not bind exact HTML and target")
        if self.source.original_ru_quote_sha256 != _sha(self.quote_text[1:-1]):
            raise ValueError("quoted Russian words differ from source proof")
        return self

    @property
    def payload_sha256(self) -> str:
        return self.source_payload_sha256


class QuoteV6NativeQueue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-v6-native-queue"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_state: Literal["provider_inert_candidate"]
    provider_writes_authorized: Literal[False]
    candidate_digest: str = Field(pattern=SHA256_PATTERN)
    posts: tuple[QuoteV6NativePost, ...]

    @model_validator(mode="after")
    def exact_queue_binding(self) -> "QuoteV6NativeQueue":
        if len(self.posts) != 30 or [post.sequence for post in self.posts] != list(range(1, 31)):
            raise ValueError("v6 must have thirty contiguous source-bound cards")
        ids = [post.publication_id for post in self.posts]
        if len(set(ids)) != 30:
            raise ValueError("duplicate v6 publication IDs")
        digest_input = [
            {
                "publication_id": post.publication_id,
                "candidate_payload_sha256": post.payload_sha256,
                "quoted_russian_sha256": post.source.original_ru_quote_sha256,
            }
            for post in self.posts
        ]
        if self.candidate_digest != _sha(_canonical(digest_input)):
            raise ValueError("candidate digest changed after source review")
        return self

    @property
    def digest(self) -> str:
        # This is a review candidate identity, explicitly NOT a signed release identity.
        return self.candidate_digest


def build_quote_v6_native_queue(source_path: Path) -> QuoteV6NativeQueue:
    """In-memory adapter only: no file/state/API writes and no approval promotion."""

    raw = json.loads(source_path.read_text(encoding="utf-8"))
    if (
        raw.get("schema_name") != "video-channel-manager.lordchrist-quote-v6-payload-candidate-inert"
        or raw.get("project_key") != "lord-god-strength"
        or raw.get("channel_username") != "@lordchrist"
        or raw.get("new_release_digest") is not None
        or raw.get("read_only") is not True
        or raw.get("live_schedule_enabled") is not False
        or raw.get("provider_write_authorization") is not False
        or raw.get("approved_new_queue") is not False
        or raw.get("rights_review_complete") is not False
        or raw.get("full_bilingual_review_complete") is not False
        or raw.get("responsible_editor_approval") is not False
        or raw.get("historical_v4_replay_authorized") is not False
    ):
        raise ValueError("v6 candidate changed its immutable provider-inert review boundary")
    items = raw.get("items")
    if not isinstance(items, list) or len(items) != 30:
        raise ValueError("exactly thirty candidate records required")
    posts: list[QuoteV6NativePost] = []
    for index, item in enumerate(items, start=1):
        if item.get("sequence") != index or item.get("provider_write_authorization") is not False:
            raise ValueError("v6 card identity or authorization changed")
        if item.get("rights_review_complete") is not False or item.get("responsible_editor_approval") is not False:
            raise ValueError("v6 card did not retain the rights/editorial hold")
        match = RENDER_RE.fullmatch(item["html_text"])
        if match is None:
            raise ValueError("v6 candidate contains unparseable provider HTML")
        quoted, attribution, hashtags = (html.unescape(v) for v in match.groups())
        author, separator, work = attribution.removeprefix("— ").partition(", ")
        if not separator or not author or not work:
            raise ValueError("v6 reader attribution is incomplete")
        post = QuoteV6NativePost(
            sequence=index,
            publication_id=item["publication_id"],
            title=author,
            text=quoted + "\n" + attribution + "\n\n" + hashtags,
            quote_text=quoted,
            attribution_line=attribution,
            hashtags=hashtags,
            html_text=item["html_text"],
            source_payload_sha256=item["candidate_payload_sha256"],
            render_html_sha256=item["source_render_html_sha256"],
            source=QuoteV6Source(
                author=author,
                work=work,
                url=item["source_url"],
                original_english_span_sha256=item["historical_english_span_sha256"],
                original_ru_quote_sha256=item["quoted_russian_sha256"],
            ),
        )
        if item["visible_utf16_units"] != len(post.text.encode("utf-16-le")) // 2:
            raise ValueError("v6 UTF-16 length does not agree with source review")
        posts.append(post)
    return QuoteV6NativeQueue(
        schema_name=NATIVE_SCHEMA,
        schema_version=1,
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        release_state="provider_inert_candidate",
        provider_writes_authorized=False,
        candidate_digest=raw["candidate_digest"],
        posts=tuple(posts),
    )


def main(argv: list[str] | None = None) -> int:
    """Read-only executable proof that every v6 payload binds the canonical queue."""

    import argparse

    parser = argparse.ArgumentParser(description="Check exact 30 quote-v6 native records without any provider")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    queue = build_quote_v6_native_queue(args.root / SOURCE_PATH)
    print(
        _canonical(
            {
                "project_key": queue.project_key,
                "channel_username": queue.channel_username,
                "candidate_digest": queue.digest,
                "posts": len(queue.posts),
                "first_publication_id": queue.posts[0].publication_id,
                "last_publication_id": queue.posts[-1].publication_id,
                "provider_writes_authorized": queue.provider_writes_authorized,
                "release_state": queue.release_state,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
