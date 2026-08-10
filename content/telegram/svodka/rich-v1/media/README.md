# Svodka rich-v1 — media registry (licensed media assets & manifests)

Directory: `content/telegram/svodka/rich-v1/media/`

Prepared 2026-08-10 for the Svodka / `@deep_info_life` project by the
media-acquisition/provenance agent (Arena.ai Agent Mode). Base commit:
`b1f6b76` (main, PR #290).

## What this is

A media base for the future Rich Messages of the `rich-v1` editorial revision.
It binds **licensed, provider-ready HTTPS media** to the existing
`media_slots` in `articles/*.json`, and provides **media manifests** for the
remaining slots.

- `media-registry.json` — one entry per media slot (29 assets across all 14
  articles). Each entry records `asset_id`, `article_id`, `media_slot_id`,
  `kind`, canonical source page, direct HTTPS media URL, creator, institution,
  licence, attribution, `checked_at`, `depicts`, caption, provenance, intended
  mode, expected MIME, checksum state and `provider_upload_status`.
- `validate_registry.py` — self-contained, read-only validator that enforces
  the required checks (see below). Run it with:
  `python3 content/telegram/svodka/rich-v1/media/validate_registry.py`.
- This `README.md`.

## Scope decisions (as requested)

- **Canary article** — `svodka-rich-2026-august-total-solar-eclipse`. It is the
  only rich-v1 article whose **two** media slots are both real, freely-licensed
  **public-domain NASA** assets (official NASA eclipse path map + NASA WB-57
  high-altitude research aircraft photo), hosted on stable official NASA URLs —
  the most stable canary possible.
- The **other 13 articles** are covered by media manifests: every photo/map
  slot is bound to a stable, licensed HTTPS source; every diagram slot is
  recorded as an in-house editorial original to be produced by the editorial
  team (not a copied copyrighted figure).
- Nothing is uploaded and no Telegram API is called.
  `provider_upload_status: "not_uploaded"` for every asset, and
  `telegram_write_authorization.provider_writes_authorized: false`.

## Source policy applied

- Preferred sources were NASA / NOAA (US Government public domain) and
  Wikimedia Commons files with an explicit compatible licence (verified via the
  Wikimedia Commons API: artist + `LicenseShortName`).
- No random Google/Bing images; no image assumed free merely because it is
  publicly visible.
- Copyrighted journal figures (Elsevier, RSC, Royal Society, Wiley, Smithsonian
  mixed-rights pages, UC Davis / Kew / official Eiffel Tower site imagery) were
  **not** reused. Diagram slots are in-house originals (facts/procedures are
  not copyrightable).
- The Eiffel Tower slot uses a **daytime** photograph; night-lighting shots are
  deliberately excluded (lighting design is separately copyrighted).

## Telegram Bot API 10.2 media semantics (checked 2026-08-10)

Per the official Bot API 10.2 docs (2026-07-14):

- Rich messages structure content as **blocks**; media is embedded **only as
  separate media blocks** (inline images inside running text are not a
  supported construct).
- Media blocks support **only HTTP and HTTPS URLs**; media type is determined
  by the **MIME type** and the URL.
- Rich messages allow up to **50 media attachments**.
- There is **no first-class "inline / collage / slideshow" enum** in the Bot
  API. Those are editorial intents in this registry; a collage/slideshow would
  be realised as multiple separate media blocks or a media group
  (`sendMediaGroup`).
- `intended_mode` is therefore an editorial hint, not a Bot API guarantee.

Implication: stable licensed HTTPS URLs are the correct provider-ready form,
so no large binary files were committed. Each `direct_media_url` is HTTPS and
carries an expected MIME.

## Explicitly-flagged manifest

`asset-tardigrades-survived-space-exposure-media-03` (ESA Foton-M3 / TARDIS
photo) is a **manifest, not a ready URL**:
`remote_ready: false`, `acquisition_status: "extract_direct_asset_from_source_page"`.
The stable ESA source **page** is referenced (and was confirmed reachable), but
the direct image file must be pulled from the ESA multimedia page at
acquisition with its per-asset licence checked (ESA `CC BY-SA 3.0 IGO`). This
is deliberately flagged rather than silently assumed, per the task rule: if a
remote URL is unreliable/incomplete, mark it explicitly.

## Checksum note (important)

`content_checksum` is `null` for every asset. This sandbox has **no general
outbound network** (TLS is terminated for non-allowlisted hosts), so the
canonical remote bytes could not be fetched and hashed here. No SHA-256 is
claimed for bytes that were not retrieved. Verification was instead done via
official page HTML, the NASA images API, and the Wikimedia Commons API (see
each asset's `verification` field). Binding the canonical SHA-256 is deferred
to the media-acquisition step per the repo artifact standard (AGENTS.md);
`provider_upload_status` stays `not_uploaded`. A network-capable environment
should re-verify `direct_media_url` responds and hash the canonical bytes
before any future release.

## Checks enforced by `validate_registry.py`

- every URL is HTTPS
- licence / source-provenance non-empty
- attribution consistent (required → attribution_text non-empty)
- expected MIME present for ready photo/map assets
- duplicate detection (no duplicate `asset_id`; no duplicate `direct_media_url`)
- no dead media slots (every (article, slot) has an entry; every entry maps to
  an existing (article, slot))
- every asset belongs to an exact existing article
- `provider_upload_status == "not_uploaded"` for all
- canary article declared and its slots present

## Not touched

No workflows, no state branches, no `src/`/`scripts/`/`tests/`/`.github/`
changes, and no frozen release files were modified. This is a content-only
addition under `content/telegram/svodka/rich-v1/media/`.
