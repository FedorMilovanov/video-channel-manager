# Svodka rich article schema — revision `rich-v1`

Canonical JSON records live in `articles/*.json`. Schema name:
`video-channel-manager.svodka-rich-article`, `schema_version: 1`.

This revision is the **editorial source schema** for Svodka Rich Articles.
The repository now has a reviewed runtime loader/domain model and a native
Telegram Rich Message renderer that can transform these records into
`InputRichMessage` structures for the guarded transport. Editorial data and
provider authorization remain separate: a valid rich-v1 article is **not**
permission to publish it.

Reader-facing editorial rules live in `EDITORIAL_STANDARD.md` and are part of
the review contract for this revision.

## Record fields

- `schema_name`, `schema_version` — as above.
- `project_key` — always `svodka`.
- `channel_username`, `channel_title` — the Svodka channel identity.
- `article_id` — stable rich successor identity, pattern `svodka-rich-<slug>`.
- `revision` — `rich-v1`.
- `status` — `editorial_draft_review_required` until a separate human/release
  review promotes the material. Parsing or rendering an article does not
  authorize a provider mutation. Rich articles are not part of the historical
  frozen release `svodka-pilot-2026-08` and do not modify it.
- `provider_writes_authorized` — always `false` in this editorial revision.
- `premium_emoji_dependency` — always `false`: the reading copy must remain
  understandable without Telegram Premium/custom emoji support.
- `predecessor` — `{ publication_id, source_file, source_file_sha256,
  release_id, source_format }`: immutable provenance of the pilot item this
  article revises.
- `title` — plain text, sentence case, no clickbait caps.
- `lead` — reader-first lead in plain text.
- `icons_used` — complete Unicode icon set used by the article/companion copy.
- `sections` — ordered list of `{ section_id, heading, icon?, blocks }`.
  Editorial source blocks in schema v1 are deliberately small:
  - `{ type: "paragraph", html: str, footnotes?: [int] }`
  - `{ type: "list", ordered?: bool, items: [str], footnotes?: [int] }`
  - `{ type: "quote", html: str, attribution: str, note?: str,
      footnotes?: [int] }`
  - `html` uses only reviewed inline `<b>` and `<i>` semantics.
- `quotes` — index of quotation blocks with attribution. Every entry must also
  exist as a quote block in the referenced section.
- `media_slots` — ordered acquisition/placement plans, **not** provider assets.
  Fields include `slot_id`, placement, `depicts`, explanatory `purpose`,
  preferred source type, copyright/provenance requirements and caption.
- `visual_plan` — optional editorial plan for a diagram, timeline, collage or
  slideshow where multiple visual elements genuinely improve comprehension.
  It is a plan, not automatic permission to emit a native rich block.
- `footnotes` — ordered reader-visible source references.
- `sources` — provenance/evidence records describing what each source actually
  supports. A clarity rewrite must not silently broaden those claims.
- `footer` — tagline and hashtags.
- `editorial_notes` — revision history and claim-boundary notes.

## Renderer boundary

The native renderer may use Telegram capabilities that are richer than this
source schema (for example headings, dividers, details, tables, mathematical
expressions, native collage/slideshow blocks and media blocks). Those are
**rendering capabilities**, not requirements of every article.

The editorial source must not add a formula, table, details block, collage or
slideshow merely because Telegram can render it. `EDITORIAL_STANDARD.md`
requires every rich element to improve comprehension. The 2026-08-11 native
Rich Message canary intentionally exercised multiple provider capabilities;
that capability proof is not the production editorial template.

Any future extension that makes a new rich block authorable directly from this
JSON schema must bump/review the schema contract and add parser/renderer tests.

## Provider boundary

A successfully parsed/rendered article remains provider-inert until a separate
reviewed release/candidate authorizes the exact document, target, media bundle
and publication time. Ambiguous provider outcomes are never permission to
retry or fall back with another mutation.

## Markdown companions

`articles/<article_id>.md` is the human-readable editorial reading copy of the
same article. JSON is the canonical structured record; Markdown is the review
surface. They must remain semantically synchronized under review.
