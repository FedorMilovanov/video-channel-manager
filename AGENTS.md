# Repository agent instructions

Before any work involving Fedor Milovanov's YouTube/VK media workflow, read these files in order:

1. `docs/operations/current-state.md`
2. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
3. `docs/operations/operational-artifact-standard.md`

These operational documents are the source of truth and take priority over chat memory.

## Canonical identities

- YouTube channel: https://www.youtube.com/@fedormilovanov
- YouTube videos: https://www.youtube.com/@fedormilovanov/videos
- YouTube Shorts: https://www.youtube.com/@fedormilovanov/shorts
- public YouTube channel ID resolved from canonical pages: `UCeSJsC6go2c9pdJCuUI1BYA`
- stored OAuth alias currently reports a different/incomplete channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- VK community: https://vk.com/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- VK Clips canonical URL: not recorded until the live Clips surface is verified; do not invent it from a vanity name
- VK community ID: `60805374`
- VK API owner ID: `-60805374`
- local account alias: `legendary-poet`
- Telegram: https://t.me/lordchrist
- website: https://gospod-bog.ru
- Rutube: https://rutube.ru/channel/1876662
- Facebook group: https://facebook.com/groups/116164165395881

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

1. Never rerun any old delete, canary, recovery, v3/v4, or fast-cleanup executor. The deletion phase is closed.
2. Never infer absence from an endpoint that does not cover the relevant surface. `video.get` ordinary-video absence is not proof of VK Clip absence.
3. Never infer a transfer boundary from screenshots or relative labels such as “4 months ago”. Use exact IDs and current inventories.
4. Never upload an ambiguous match.
5. Never repeat an upload with an unknown outcome. Reconcile the ledger and live VK state first.
6. Keep long-form videos and Shorts/Clips in separate manifests and ledgers.
7. Preserve local masters or controlled exports when available. Do not use screen capture as a source.
8. Do not publish to the wall, create playlists, rewrite descriptions, or extract MP3 until the uploaded catalog has been verified.
9. Never commit OAuth tokens, VK tokens, downloaded media, local exports, ledgers, logs, backups, or generated upload packages.
10. Every operational ZIP must pass `python scripts/verify_operational_bundle.py ...` before being handed to a user.

## Execution and handoff rules

- Read-only inventory first; writes only from a reviewed immutable manifest.
- Store exact source ID, target ID, title, duration, status, attempt timestamps, and provider responses in a durable ledger.
- A successful HTTP response is not a postcondition. Re-read the remote object.
- Preserve intermediate successful audits and support resume; do not repeat expensive scans unnecessarily.
- Every handoff must state: exact command, exact entrypoint path, expected outputs, ledger path, result path, and recovery behavior.
- Operational ZIPs must be flat unless the launch command explicitly includes the nested directory.
- The launch script must verify its own location and required sibling files before any network write.
