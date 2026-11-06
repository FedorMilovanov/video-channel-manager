# Господь Бог — Сила Моя: профиль описаний

Project key: `lord-god-strength`

This profile applies only to the theological project. The existing files `docs/youtube-description-rendering-standard.md` and `docs/vk-description-rendering-standard.md` were written for The Legendary Poet and must not supply their channel name, site, VK community, Telegram, Rutube, playlist, or footer to this project.

## Exact identities

- YouTube channel ID: `UCeSJsC6go2c9pdJCuUI1BYA`
- YouTube handle: `@fedormilovanov`
- VK community ID: `60805374`
- VK API owner ID: `-60805374`
- Canonical VK community: https://vk.ru/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength

## Registered links

Default compact footer routes:

- Website: https://gospod-bog.ru/
- Telegram: https://t.me/lordchrist
- VK: https://vk.ru/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Rutube: https://rutube.ru/channel/1876662/

Additional registered routes, not included by default:

- Odnoklassniki: https://ok.ru/christjesus
- Facebook group: https://facebook.com/groups/116164165395881

Compatibility route allowed for migration input but not preferred in new output:

- https://vk.com/the_lord_god_is_my_strength

Historical `gospod_bog` vanity paths are not canonical output.

## YouTube description rules

1. The first paragraph explains the exact sermon, lecture, biblical passage, speaker, series, translation, or historical material.
2. Distinguish source claims, translator/editor notes, and application.
3. Do not invent dates, speaker claims, quotations, Bible references, source provenance, or translation details.
4. Use YouTube emphasis only where it improves readability; URLs remain plain text.
5. Include only exact relevant playlist links from the current snapshot or reviewed plan.
6. Remove obsolete `shelf_id` URLs, old translation solicitations, personal-contact routes, and legacy payment details when the reviewed plan requires removal.
7. Do not insert a donation/support link until the user selects and approves a service.
8. Never insert The Legendary Poet links.

Recommended compact footer:

```text
🌐 *Сайт проекта:* https://gospod-bog.ru/
*Telegram:* https://t.me/lordchrist
*Сообщество проекта в VK:* https://vk.ru/the_lord_god_is_my_strength
*VK Видео:* https://vkvideo.ru/@the_lord_god_is_my_strength
*RUTUBE:* https://rutube.ru/channel/1876662/
```

A surface may use a smaller subset. It must not duplicate the same destination in several forms.

## VK Video description rules

VK descriptions are plain text. Remove unsupported YouTube emphasis markers while preserving words, punctuation, paragraphs, source URLs, and exact timestamps.

Recommended compact footer:

```text
Сайт проекта: https://gospod-bog.ru/
Telegram: https://t.me/lordchrist
Сообщество проекта в VK: https://vk.ru/the_lord_god_is_my_strength
RUTUBE: https://rutube.ru/channel/1876662/
```

The VK Video channel URL is optional inside VK itself because it may be redundant. Use it on external surfaces where it provides a direct video-library route.

## Playlist links

- YouTube playlists must come from exact channel membership or an explicitly reviewed mapping.
- VK albums/playlists must come from exact numeric album IDs and live membership.
- Do not infer a playlist solely from title keywords.
- Do not use poet-project playlist IDs.
- A video with no reliable relevant playlist receives no playlist link.

## Chapters and timestamps

- Preserve only reviewed chapter blocks.
- A timestamp must describe the actual segment start.
- Do not convert SRT availability into invented chapter headings.
- YouTube chapter blocks require the first timestamp to begin at `00:00` when the platform behavior requires it.
- VK may use the same reviewed timestamps as plain text when useful.

## Required plan guards

Every executable plan must include or bind:

```text
project_key: lord-god-strength
youtube_channel_id: UCeSJsC6go2c9pdJCuUI1BYA
vk_community_id: 60805374
vk_owner_id: -60805374
link_profile: lord-god-strength
```

Before showing `ready`, preflight must reject:

- a resolved YouTube channel mismatch;
- a VK community or owner mismatch;
- any registered The Legendary Poet project link;
- an unknown site, Telegram, VK, VK Video, or Rutube project route;
- an invented playlist URL;
- unsupported donation or personal-contact links.

## Current credential use

- YouTube read/write authorization: alias `fedor-milovanov`; reauthorize with `--write --force` and verify exact channel ID before mutation.
- VK authorization: shared user-token alias `legendary-poet`; select the current project only through community `60805374` and owner `-60805374`.

## Scoped legacy-shelf cleanup when owner uploads contains known metadata gaps

The generic YouTube auto-fix builder MUST continue to reject an owner
`AuditPackage` with `uploads_playlist_inventory.complete=false`. An
unmaterialized video ID must never silently disappear from coverage.

Only the separately reviewed Lord God one-video mode permits a narrowly
scoped plan in the presence of explicit `youtube.owner-upload-metadata-gap`
errors. It requires the canonical channel ID, matching exact metadata-gap
finding IDs, two agreeing owner-upload enumerations, exactly one present
public target and an SHA-bound editorial preview with **only** known obsolete
`shelf_id` lines deleted. All inaccessible upload IDs appear in the plan's
`unresolved` section, never as implicitly corrected videos.

Example (operator-managed private files, no token files in Git):

```powershell
python scripts/autofix_youtube_copy.py <owner-AuditPackage.json> `
  --lord-god-preview <DESCRIPTION-CLEANUP-REVIEW-ONLY.json> `
  --target-video-id <exact-public-YouTube-ID> `
  --plan-output <one-video-plan.json> `
  --report-output <one-video-report.md>

video-manager youtube apply-copy-fixes <one-video-plan.json> `
  --account fedor-milovanov `
  --confirm-channel UCeSJsC6go2c9pdJCuUI1BYA `
  --max-operations 1
```

The second invocation above is **dry-run**. No `--execute` may be added
without completing source and rights review, exact before/after diff
inspection, owner write-scope confirmation, and no competing writer.
Use the existing CLI lock, write-ahead backup/journal, provider readback and
safe rollback. Historical archived descriptions or auto-generated previews
are **not** execution authority.

The scoped builder rejects legacy personal contacts and donation/translation
solicitations, an empty heading left by a shelf deletion, unknown or
non-member playlists, mixed/semantic URL lines, nonpublic targets, unrelated
project identities and any content modification other than deletion of the
recognized shelf line. If none passes, stop and prepare a new editorial
review for the individual video rather than weakening the gate.


## One-video transcript-anchored chapter review (Issue #795)

Do not turn automatic captions into arbitrary equal-length timecodes. The
source-anchored chapter review records the exact video ID, public owner channel,
current published description SHA, transcript chunk count, selected chunk
indices, source text excerpts, cues, and editor-chosen thematic headings.
The original review stays explicitly non-executable while YouTube quota is
exhausted.

Only the reviewed, one-video builder may convert that evidence to a
schema-valid, signed guarded plan:

    python scripts/autofix_youtube_copy.py <canonical-owner-AuditPackage.json> `
      --lord-god-chapters-review <REVIEW-ONLY.json> `
      --previous-editorial-plan <previous-signed-description-PLAN.json> `
      --archive-transcript-db <read-only-transcript-archive.db> `
      --target-video-id VIDEO-ID `
      --plan-output <one-video-chapter-PLAN.json> `
      --report-output <one-video-chapter-report.md>

    video-manager youtube apply-copy-fixes <one-video-chapter-PLAN.json> `
      --account fedor-milovanov `
      --confirm-channel UCeSJsC6go2c9pdJCuUI1BYA `
      --max-operations 1

The last command is a dry-run. Only add the explicit execute flag with
a unique backup and result after the owner API has recovered and a fresh
preflight proves the exact before-description SHA. On quotaExceeded, stop.
Never retry blindly, create alternative OAuth clients to circumvent quota,
or silently apply a stale plan.

The builder fails closed unless the exact source owner and previous signed
plan match the same original title, revision and description, and all
metadata-inaccessible uploads are preserved as explicit unresolved IDs.
Each anchor is checked against the archive SQLite transcript's chunk index,
timestamp, source excerpt, and text cue. Timecodes start at 00:00,
strictly increase, leave at least ten seconds per chapter, and use
h:mm:ss format after one hour. Only one chapter block may be appended;
previous descriptive text and links must remain byte-for-byte unchanged.

A successful API readback proves description text and chapter syntax,
NOT that the YouTube player has displayed chapter navigation or that
editorial section boundaries precisely match the underlying audio.
The latter are separate visual/audio witnesses. The generic full-inventory
fail-closed policy is not changed.


## Source-preserving retired-appeal removal: exact one-video mode

Removing old shelf_id links is not the same as repairing a complete YouTube
description. Many historical descriptions still contain personal translator
solicitations, fundraising, or unrelated playlist navigation. Some contain
almost no original editorial content. Never treat the 1,386-item source preview
as a mass write plan.

For a narrowly source-verified item, the new offline builder is:

    python scripts/autofix_youtube_copy.py <owner-AuditPackage.json> `
      --lord-god-retired-appeal-review <LORDGOD-EXACT-VIDEO-REVIEW-ONLY.json> `
      --target-video-id VIDEO-ID `
      --plan-output <VIDEO-SIGNED-PREFLIGHT-PENDING.json> `
      --report-output <VIDEO-SIGNED-REPORT.md>

This emits exactly one standard SHA-bound copy plan, not a provider mutation.
Required evidence: the precise public owner ID, two independently reconciled
owner upload-ID reads, all six explicit metadata gaps, exact original description,
previously source-validated removal of shelf-only URLs, and exactly one
full-line allowlisted retired translator appeal. The deleted appeal must not
contain any unrelated attribution, copyright/source, or third-party URLs.
Every surviving line is kept byte-for-byte in original order. The builder
rejects unknown lines, nonpublic videos, stale source SHA, incomplete content,
out-of-scope playlists, or personal contacts still present.

Once the official YouTube daily quota recovers, the first-party
video-manager youtube apply-copy-fixes dry-run must confirm the exact owner,
video, original description and SHA again. Only then permit one explicitly
bounded execute with unique backup and result; independently read back the
published after SHA and do not retry blindly after an ambiguous timeout.
No alternative OAuth app and no API quota bypass are provided.

In the archival November 2026 owner review, only 12 of 1,386 old shelf-linked
items met the strict source-preserving minimum for this additional method.
The others require genuine topic-based editorial revision or proof of source
and playlist provenance. An offline plan does not prove rights clearance
or publication status.


## YouTube-native presentation and retired solicitations: mandatory pre-publish gate

As of the November 2026 editorial review (#795), the exact Lord God channel ID is
UCeSJsC6go2c9pdJCuUI1BYA. Any first-party YouTube apply-copy-fixes plan
targeting this ID must pass the **project-bound presentation gate before
OAuth/API preflight**, for both dry-run and execute. This applies even if
a historical signed plan was previously generated; no retroactive edit.

**YouTube presentation:**

- Keep the first meaningful paragraph unmarked and useful in a share
  preview. In long descriptions (at least 350 characters), use a small
  number of YouTube-native single-asterisk bold spans (e.g. *heading:*)
  and single-underscore italic spans (e.g. _meaning_). No double-star
  Markdown, hidden Markdown hyperlinks, unbalanced markers, or wrong
  punctuation outside the emphasized phrase.
- Keep bare URL links. Distinguish original source and rights credit,
  topical recommendations, channel destinations, and video membership.
  Do not remove cited external sources merely because they are not
  owner-playlist members. Chapters remain true timestamp starts.
- The Legendary Poet shares the **YouTube markup syntax and factual
  rigor**, NOT its poetry-specific channel identity, links, six social
  rows, 3500–4600 length target, fixed playlist order, or biography format.

**Historical cleanup and rights:**

- Remove retired personal translator recruitment, outdated personal
  contact links, bank/card solicitations, Yandex wallet numbers,
  DonatePay references and obsolete VK donor applications before
  treating a rewritten description as final.
- Do not insert new bank details, fundraising apps, contact handles or
  donation links without separate and explicit owner approval.
- Retain sermon sources, source and translation attribution, speaker
  identity, notices about rights, and genuine citations unless a separate
  review proves a particular claim/link incorrect.
- Reject unverified claims about all videos having been moved to VK,
  invented chapters, fake translations and irrelevant cross-project
  links. Avoid dense navigation-only and SEO keyword-stuffed boilerplate.

**Staged source evidence is NOT publication approval:**

- Six Prokopenko descriptions: the newer YouTube-formatted v2 offline
  plans pass the renderer and supersede earlier plain v1 plans. They
  still require exact live owner/API preflight, source/rights review and
  independent postflight after an individual write.
- Twelve earlier source-preserving shelf and translator-appeal cleanups:
  the signed plain archival plans lack proper formatting. They are
  NOT cleared as final YouTube publications. Re-edit and sign new
  plans preserving source and attribution first.
- Older proposed chapter appends are not exempt; their resulting
  descriptions must pass this same gate. Previously published videos
  are not automatically modified or rolled back by this policy.

**Implementation:** src/video_channel_manager/cli/youtube.py uses
platforms/youtube/lord_god_presentation.py and the shared
editorial.youtube_copy.validate_youtube_description checker. Fix a
rejected plan upstream and re-sign. Never bypass the validation,
replay an ambiguous timeout, or work around a quotaExceeded response.
