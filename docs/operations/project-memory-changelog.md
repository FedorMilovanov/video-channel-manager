# Project memory changelog

This file records durable updates to the repository's operational memory.

## 2026-08-02

### Daily article-link queue prepared

- Prepared 10 postponed article posts for `lord-god-strength`, one daily at 14:00 UTC+03:00 from 2026-08-03 through 2026-08-12.
- Source truth is `FedorMilovanov/gb-is-my-strength` search-manifest blob `952cfbd8b276fc7e877a784660fb4481dc8bd83f`; post copy is derived from the selected articles and points to their canonical public URLs.
- Only pages with declared `.webp` Open Graph images are included. No separate photos are uploaded: the article URL is attached as a VK link card.
- The executor verifies each live canonical URL and OG image before any write, blocks duplicate article URLs or occupied 14:00 slots, journals every attempt, and requires a VK link card with an image after every accepted post before continuing.
- Policy SHA-256: `sha256:458b716dad898f7a692da7204259b43c42b1803387e9ea5ca855d456f044b85b`. Entrypoint: `scripts/run-lord-god-article-wave.ps1`.

### Theological postponed wall queue prepared

- Prepared one immutable 26-video wall plan for `lord-god-strength`, VK community `60805374` / owner `-60805374`; no VK write occurs during plan creation.
- Cadence is two postponed posts per day at 09:00 and 19:00 Moscow time, from 2026-08-03 through 2026-08-15, ordered oldest-to-newest within the verified long-form tail.
- Every post has an individual compact introduction, a discussion question, the exact YouTube source, a reviewed relevant playlist, and the registered project links for the site, Telegram, VK Video, and Rutube.
- The executor revalidates all exact videos, scans both published and postponed wall queues, blocks duplicates or changed text/times, journals intent before `wall.post`, and verifies all scheduled posts afterward. It has no edit, delete, or immediate-post method.
- Policy SHA-256: `sha256:2f9e4de476ad7267b6f8423b7e23bd89173964af9d31641d3698a051c82041c5`. Entrypoint: `scripts/run-lord-god-wall-tail.ps1`.

### Long-form tail correction

- Confirmed the only pre-upload failure in the reviewed 26-video queue: YouTube `uI-wfRaq2SA`, part 2 of `Архитектура мышления`; the download failed with HTTP 403 before any VK reservation or upload, so no duplicate ambiguity exists.
- Added `scripts/complete_vk_longform_tail.py` as the single focused completion entrypoint. It reconciles all 26 exact rows, uploads only safe never-attempted gaps, repairs source thumbnails, and verifies the five-part Sproul VK album.
- Added the durable transfer rule: when source artwork exists, the transfer is incomplete until that exact YouTube thumbnail or a reviewed local branded override is applied to VK and its source, SHA-256, target ID, and result are journaled. A VK-generated frame requires an explicit no-artwork exception.
- Recorded a cross-project renderer defect: the generic VK publication helper still contains a poet-specific title convention, so it must not be used for `lord-god-strength` until made project-aware. The focused completion script preserves the current theological video's exact title and description.
- The previous broad playlist audit was not accepted as current evidence because one run paginated only the first 100 VK videos and another failed VK authorization. Playlist completion now uses exact series IDs and live album membership.
- Issue #40 tracks this one correction; accidental temporary issues #41–#43 were closed and contain no work.

### Shorts reset completed

- Replaced 34 reviewed low-view Shorts with verified ordinary VK videos.
- Accepted 34 old-video deletions and 34 generated wall-post deletions.
- Final result reported no remaining planned or unresolved wall posts; protected wall post `12400` remained present.

## 2026-08-01

### The Legendary Poet identities and links confirmed

- Confirmed the project website: `https://thelegendarypoet.ru/`.
- Confirmed the YouTube channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`.
- Confirmed the canonical VK route: `https://vk.ru/thelegendarypoet`.
- Retained `https://vk.com/thelegendarypoet` as a working compatibility/migration route.
- Confirmed VK community number `club235216998`, community ID `235216998`, and API owner ID `-235216998`.
- Confirmed the public VK Clips route: `https://vkvideo.ru/@thelegendarypoet/clips`.
- Confirmed the VK Video author dashboard and filtered published-clips view as operational/admin routes.
- Explicitly prohibited `cabinet.vkvideo.ru` URLs in public descriptions, comments, posts, footers, and promotion blocks.
- Added `docs/operations/legendary-poet-description-profile.md`.
- Updated the canonical project registry, link audit, and operations index.
- Recorded that source-code link profiles and validators still require synchronization before the newly confirmed `vk.ru` and VK Clips routes are used by an executable plan.

### Two-project identity separation

- Added `docs/operations/project-identity-registry.md` as the canonical registry for the two distinct projects:
  - `lord-god-strength` — Господь Бог — Сила Моя;
  - `legendary-poet` — The Legendary Poet — Легендарный Поэт.
- Recorded the credential model correctly:
  - YouTube uses two separate OAuth aliases, one per selected channel;
  - VK uses one shared user token for both communities;
  - every VK operation must select its target by exact numeric community and owner IDs.
- Recorded the current theological-project identities:
  - YouTube channel ID `UCeSJsC6go2c9pdJCuUI1BYA`;
  - YouTube alias `fedor-milovanov`, currently read-only;
  - VK community ID `60805374` and owner ID `-60805374`;
  - shared VK token alias `legendary-poet`.
- Replaced the current canonical theological VK community link with `https://vk.ru/the_lord_god_is_my_strength` and retained the published `vk.com` form only as a compatibility URL.
- Registered the current compact footer links for the theological project: website, Telegram, VK, VK Video, and Rutube.
- Initially marked the poet-project website and numeric VK identity as unverified; this was superseded later the same day by direct owner confirmation recorded above.
- Updated root `AGENTS.md`, `docs/operations/current-state.md`, and the operations index so future work must bind `project_key`, exact provider IDs, and a project-specific link profile.

### Project-specific editorial profiles

- Replaced the old global editorial link model with project-specific link profiles.
- Added cross-project link rejection and regression coverage.
- Added a dedicated theological description profile.
- Added a dedicated The Legendary Poet description profile after the missing identities were confirmed.

## 2026-07-31

### Added

- Root `AGENTS.md` with canonical YouTube/VK identities, current verified counts, closed deletion state, transfer queue identity, and non-negotiable safety rules.
- `docs/operations/current-state.md` as the first-stop operational status board.
- `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md` with successful outcomes, failed attempts, root causes, and permanent rules.
- `docs/operations/operational-artifact-standard.md` defining ZIP, launcher, manifest, ledger, resume, postcondition, and handoff requirements.
- `docs/operations/README.md` as an index for operational documentation.
- `scripts/verify_operational_bundle.py` for pre-handoff ZIP validation.
- Regression tests for valid bundles, nested roots, missing entrypoints, path traversal, secret leakage, checksum mismatches, and critical operational-memory references.
- Pull-request checklist, operational incident issue form, incident-report template, and decision-log template.
- Prioritized automation backlog.

### Repository workflow completed

- PR #30, `Complete operational memory and reporting workflow`, passed CI on Python 3.11, 3.12, and 3.13 and was squash-merged into `main`.
- Merge commit: `dcc91326ab50f9ead0a97f0e3aa7cae8a1ff652f`.

### Active operational issues

- [Issue #31 — verify the 26-video upload result and reconcile the ledger](https://github.com/FedorMilovanov/video-channel-manager/issues/31)
- [Issue #32 — inventory the real VK Clips surface and derive the exact Shorts queue](https://github.com/FedorMilovanov/video-channel-manager/issues/32)
- [Issue #33 — organize and publish the verified VK catalog after transfer completion](https://github.com/FedorMilovanov/video-channel-manager/issues/33)

Issue #33 is explicitly blocked by #31 and #32.

### Current operational status

- VK duplicate cleanup: complete and verified (`403 confirmed_deleted`, `0 planned`, `0 unresolved`).
- Public YouTube inventory: `1781` items (`1673` long-form, `108` Shorts).
- VK ordinary-video inventory after cleanup: `2879`.
- Verified long-form upload queue: `26` items.
- Upload completion: unverified until local `upload-result.json` is reviewed.
- Shorts upload: blocked pending inventory of the real VK Clips surface.

### Required future updates

After each operational run, update `docs/operations/current-state.md` and append a dated entry here containing:

- manifest SHA-256;
- attempted, accepted, processing, verified, failed, and unknown counts;
- result and ledger paths;
- whether resume is safe;
- any new provider, identity, endpoint-coverage, launcher, or packaging failure;
- exact next action.
