# Repository agent instructions

Before any work involving Fedor Milovanov's YouTube/VK media workflow, read these files in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/current-state.md`
3. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
4. `docs/operations/operational-artifact-standard.md`

These operational documents are the source of truth and take priority over chat memory.

## Two-project identity boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

They are not aliases of one project. Never mix their YouTube channels, VK communities, sites, Telegram channels, Rutube channels, playlist links, descriptions, comments, manifests, journals, or reports.

The complete canonical link and identity allowlists are in `docs/operations/project-identity-registry.md`.

## Credential model

### YouTube

YouTube uses two local OAuth aliases, one for each selected YouTube/Brand Account channel:

- `fedor-milovanov` — current `lord-god-strength` authorization; presently read-only;
- `legendary-poet` — `The Legendary Poet`; presently write-capable.

Reauthorizing one alias with `--force` replaces only that alias. Never use the `legendary-poet` YouTube token for the current theological project.

### VK

VK intentionally uses one user access token for both communities. The current stored token alias is `legendary-poet`, but the alias is only a credential name and does not identify the target project.

Every VK operation must select the project with exact numeric guards:

- `project_key`;
- `community_id`;
- `owner_id`;
- project-specific link profile.

A shared VK token is normal. Selecting a target only by token alias, community display order, or remembered context is forbidden.

## Current selected project

Current work is restricted to `lord-god-strength`:

- YouTube: https://www.youtube.com/@fedormilovanov
- YouTube channel ID: `UCeSJsC6go2c9pdJCuUI1BYA`
- current YouTube OAuth alias: `fedor-milovanov`
- current YouTube access: `read-only`; reauthorize this same alias with `--write --force` before YouTube mutation and verify the returned channel ID
- canonical VK community: https://vk.ru/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- VK community ID: `60805374`
- VK API owner ID: `-60805374`
- shared VK user-token alias: `legendary-poet`

The YouTube alias `legendary-poet` resolves to `The Legendary Poet` and is prohibited for the current rollout.

Every provider plan must bind `project_key`, exact YouTube channel ID, exact VK community/owner ID, credential alias, and the selected project's link profile. Alias names and display titles are never sufficient identity guards.

## Branch discipline

- Do not create throwaway, status-only, or duplicate branches.
- Small, low-risk documentation, link, configuration, and narrowly scoped maintenance changes go directly to `main`.
- Use a branch only for a substantial or risky code change that genuinely benefits from isolated CI or review.
- Keep at most one active working branch for the current task.
- Merge it promptly after green CI and do not open another branch for follow-up documentation.
- Never create branches merely to record progress, add pointers, or split one operational task into artificial PRs.

## Current verified state

- The reviewed VK duplicate cleanup is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`, `run=completed`.
- The final stable VK ordinary-video inventory after cleanup contains `2879` records.
- The public YouTube inventory contains `1781` items: `1673` long-form videos and `108` Shorts.
- The exact long-form transfer boundary is YouTube ID `KobOzfBqzic`, title `Рождество: Правда и Вымысел - Джон МакАртур`. It is already present in VK and must not be uploaded again.
- There are `27` long-form uploads newer than that boundary. Exactly `26` were verified missing in the VK snapshot.
- YouTube ID `s512Opa8Eu4` is already present as VK ID `-60805374_456241938`; duration delta is one second.
- Verified 26-item upload queue SHA-256: `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`.
- The 26-item upload executor was prepared, but completion is not verified until `upload-result.json` is inspected.
- Shorts are not upload-authoritative yet: the ordinary VK API snapshot reported `vk_clips=0`, although clips visibly exist in the VK UI.

## Non-negotiable safety rules

1. Never use the `legendary-poet` YouTube write token for `lord-god-strength`.
2. Never select a VK target only from the shared token alias; confirm numeric community `60805374` and owner `-60805374` for the current project.
3. Never rerun any old delete, canary, recovery, v3/v4, or fast-cleanup executor. The deletion phase is closed.
4. Never infer absence from an endpoint that does not cover the relevant surface. `video.get` ordinary-video absence is not proof of VK Clip absence.
5. Never infer a transfer boundary from screenshots or relative labels such as “4 months ago”. Use exact IDs and current inventories.
6. Never upload an ambiguous match.
7. Never repeat an upload with an unknown outcome. Reconcile the ledger and live VK state first.
8. Keep long-form videos and Shorts/Clips in separate manifests and ledgers.
9. Preserve local masters or controlled exports when available. Do not use screen capture as a source.
10. Do not publish to the wall, create playlists, rewrite descriptions, or extract MP3 until the uploaded catalog has been verified.
11. Never commit OAuth tokens, VK tokens, downloaded media, local exports, ledgers, logs, backups, or generated upload packages.
12. Every operational ZIP must pass `python scripts/verify_operational_bundle.py ...` before being handed to a user.
13. Descriptions, comments, playlists, and footers must use only the selected project's registered links unless a cross-project link has been explicitly reviewed for that exact operation.
14. Unknown or unregistered links fail closed; never invent a vanity handle, site, Clips URL, or numeric ID.

## Execution and handoff rules

- Read-only inventory first; writes only from a reviewed immutable manifest.
- Store exact project key, source ID, target ID, title, duration, status, attempt timestamps, and provider responses in a durable ledger.
- A successful HTTP response is not a postcondition. Re-read the remote object.
- Preserve intermediate successful audits and support resume; do not repeat expensive scans unnecessarily.
- Every handoff must state: selected project, exact command, exact entrypoint path, expected outputs, ledger path, result path, and recovery behavior.
- Operational ZIPs must be flat unless the launch command explicitly includes the nested directory.
- The launch script must verify its own location and required sibling files before any network write.
