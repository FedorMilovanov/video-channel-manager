# Svodka rich article schema — revision `rich-v1`

Canonical JSON records live in `articles/*.json`. Schema name:
`video-channel-manager.svodka-rich-article`, `schema_version: 1`.

This is a **content-only** schema definition for human review and for a future
renderer/validator, if one is ever reviewed and approved. No runtime parser or
renderer exists for it in this repository yet, and none is added here.

## Record fields

- `schema_name`, `schema_version` — as above.
- `project_key` — always `svodka`.
- `channel_username`, `channel_title` — the Svodka channel identity.
- `article_id` — stable rich successor identity, pattern `svodka-rich-<slug>`.
- `revision` — `rich-v1`.
- `status` — `editorial_draft_review_required` until a human editor reviews;
  no rich article may be rendered to a provider payload or published without a
  separate reviewed release. Rich articles are **not** part of release
  `svodka-pilot-2026-08` and do not modify it.
- `provider_writes_authorized` — always `false` in this revision.
- `premium_emoji_dependency` — always `false`: every icon used anywhere in the
  record is a Unicode codepoint with a glyph in stock device fonts.
- `predecessor` — `{ publication_id, source_file, source_file_sha256,
  release_id, source_format }`: the frozen pilot item this article revises.
- `title` — plain text, sentence case, no clickbait caps.
- `lead` — restrained lead, plain text.
- `icons_used` — the complete set of Unicode icons used by the article across
  its JSON record and markdown companion (a theme marker by the title, diagram
  or photo markers inside media-slot notes, and the tagline seal), so a future
  renderer can prove no Premium Emoji crept in. Every entry must be a standard
  Unicode codepoint sequence with a glyph in stock device fonts.
- `sections` — ordered list of `{ section_id, heading, icon?, blocks }`.
  Blocks:
  - `{ type: "paragraph", html: str, footnotes?: [int] }`
  - `{ type: "list", ordered?: bool, items: [str], footnotes?: [int] }`
  - `{ type: "quote", html: str, attribution: str, note?: str,
      footnotes?: [int] }`
  - `html` uses only `<b>` and `<i>` inline semantics (bold = verified key
    fact or quantity; italic = term, definition, Latin name, soft emphasis).
- `quotes` — index of quotation blocks with their attribution (may be `[]`).
  Every entry here must also exist as a `{ type: "quote" }` block inside the
  referenced section, so the JSON record and the markdown companion stay
  structurally identical.
- `media_slots` — ordered list of acquisition plans, **not** assets. Fields:
  - `slot_id`, `placement` (`after` / `before` section ids),
  - `depicts` — what must be shown,
  - `purpose` — why the article needs it,
  - `preferred_source_type`,
  - `copyright_provenance` — licensing and credit requirements,
  - `caption`.
  No image files are committed with this revision; no image may be added
  before its licence and provenance are recorded here and reviewed.
- `visual_plan` — optional collage/slideshow plan `{ rationale, panels }`;
  present only where it genuinely improves comprehension.
- `footnotes` — ordered source/footnote block `{ n, source_id, label, url }`.
  URLs must remain visible to the reader in any rendering.
- `sources` — full provenance for each footnote `{ source_id, label, url,
  verified_on, evidence }`, carried over from the frozen pilot release without
  altering the underlying claims. `evidence` notes the claims the source
  actually supports; `reverified_on` appears only where the revising editor
  re-read the source during this revision.
- `footer` — `{ tagline, hashtags }`.
- `editorial_notes` — what the revision changed relative to the micro-post.

## Markdown companions

`articles/<article_id>.md` is the human-readable editorial text of the same
article. The markdown is the authoritative reading copy; the JSON is the
canonical data record. They must stay in sync under review.
