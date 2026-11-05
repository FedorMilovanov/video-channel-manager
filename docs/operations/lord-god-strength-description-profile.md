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
