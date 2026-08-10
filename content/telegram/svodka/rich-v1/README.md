# Svodka rich article editorial revision — `rich-v1`

Prepared 2026-08-10 for the Svodka / `@deep_info_life` project by the
editorial/data-migration pass.

## What this is

A rich-article editorial revision of the 14 pilot posts in the **frozen**
release `svodka-pilot-2026-08`
(`content/telegram/svodka/draft-14-posts-2026-08.json`).

Each micro-post is re-worked into a long-form rich article with:

- a title and a restrained lead;
- headed sections and short paragraphs;
- deliberate bold/italic semantics (`<b>` for verified key facts and
  quantities, `<i>` for terms, definitions, Latin names and soft emphasis);
- a quote where it genuinely adds something (verified at the source — see
  below);
- a footnote/source block with visible URLs;
- media placement suggestions, each with: what must be depicted, why it is
  needed, preferred source type, copyright/provenance requirements, a caption,
  and the exact block after which it sits;
- an optional collage/slideshow plan only where it improves comprehension
  (Venus day-length comparison; sunflower daily/path pair; shark timeline);
- Unicode-only icons: every icon in every record has a stock-font glyph.
  There is **no Premium Emoji dependency** anywhere in this revision
  (`premium_emoji_dependency: false`, and `icons_used` lists exactly what is
  used).

## What this is not

- **Not** a modification of the frozen pilot release. The draft queue,
  release approval and rollout schedule files are untouched. Historical
  frozen release stays evidence.
- **Not** a provider release. All 14 articles are
  `status: editorial_draft_review_required`,
  `provider_writes_authorized: false`. No Telegram post is scheduled,
  rendered to a provider payload, or sent from this revision. Any future
  publication needs its own reviewed candidate, exact release authorization
  and the existing guarded pipeline.
- **Not** a runtime or workflow change. Nothing under `src/`, `scripts/`,
  `tests/`, `requirements/` or `.github/` is touched.
- **Not** an image commit. Media slots are acquisition plans with licence
  constraints, not files. No copyright-unsafe assets are committed.

## Files

- `SCHEMA.md` — the `video-channel-manager.svodka-rich-article` schema v1.
- `articles/<article_id>.json` — canonical rich article data (14 records).
- `articles/<article_id>.md` — the accompanying editorial markdown (the
  human-readable reading copy; keep in sync with the JSON under review).
- `sources.json` — central source/provenance ledger with per-source media
  policy notes.
- `manifest.json` — migration manifest mapping each frozen
  `old_publication_id` to its `rich-v1` successor article id.

## Editorial line applied

- Careful literary Russian without chancery: concrete nouns, short measured
  sentences, no bureaucratic constructions.
- No cheap "coolness": no clickbait caps, no feigned shock, no ranking of
  animals, people or studies. The frozen release's ALL-CAPS post headlines
  were not carried over.
- Respect for people, including the little-known: researchers are named with
  role and affiliation where the source gives them (Stacey Harmer, UC Davis;
  Jason N. Bruck, University of Chicago; the Seattle field team), and no
  "genius ranking" framing is added.
- Theological conclusions: **none are added in this revision.** These are
  empirical science-fact articles; attaching a theological moral would be
  exactly the "навязать богословский вывод туда, где его нет" case the style
  guide warns against. If a future Svodka article ever handles a subject where
  such a reflection is genuinely native to the material, it will be a separate
  reviewed decision, not a batch rule.
- Source claims unchanged without a check: every paragraph maps to the same
  sources that were verified for the frozen release on 2026-08-08. Three
  sources were re-read on 2026-08-10 during this revision to support quotes
  or exact wording (UC Davis sunflower release — Harmer quote verbatised;
  NOAA lightning page — temperature/thunder passage; Proc. B dolphin paper —
  abstract claim). This is recorded per-source as `reverified_on` in
  `sources.json`.
- Time-sensitive wording: the eclipse article is anchored to the explicit
  date (12 August 2026), not to "next Wednesday", so the rich article stays
  correct as a standalone long-form piece.

## Media policy summary

- NASA still imagery: public domain, preserve the requested per-image credit.
- ESA imagery: generally CC BY-SA 3.0 IGO — check the licence stated beside
  each asset and keep attribution.
- Smithsonian: rights are mixed per image; use only Open Access/CC0-flagged
  items or switch to NOAA/public-domain alternatives.
- Journal figures (Elsevier, RSC, Wiley, the Royal Society): copyrighted —
  never copied; original editorial diagrams may restate the published facts.
- UC Davis / Kew / official Eiffel Tower site imagery: rights reserved —
  not used; prefer openly licensed or editorial originals.
- Eiffel Tower night photographs are deliberately excluded: the lighting
  design is separately copyrighted.
- All chosen assets, when a future release actually acquires them, must have
  author, licence and provenance recorded in the article record before
  download, and no watermarked or "found on the internet" material is ever
  acceptable.

## Suggested review path for a future release

1. Human editor reviews the markdown companions (reading copies).
2. JSON records are corrected in sync with any markdown edits.
3. Media slots are filled only with licence-checked assets; the slot records
   are updated with final provenance.
4. A new reviewed candidate / release artifact is prepared separately from
   this revision; nothing here bypasses the standard candidate + approval
   flow.
