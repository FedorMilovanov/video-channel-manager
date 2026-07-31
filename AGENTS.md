# Repository agent instructions

Before any work involving Fedor Milovanov's YouTube/VK media workflow, read:

- `docs/operations/fedor-youtube-vk-transfer-reference.md`
- `docs/operations/fedor-youtube-vk-transfer-result-20260731.md`

Those operational documents are the source of truth and take priority over chat memory.

Canonical identities:

- YouTube channel: https://www.youtube.com/@fedormilovanov
- YouTube videos: https://www.youtube.com/@fedormilovanov/videos
- YouTube Shorts: https://www.youtube.com/@fedormilovanov/shorts
- public YouTube channel ID resolved from the canonical pages: `UCeSJsC6go2c9pdJCuUI1BYA`
- stored OAuth alias currently reports a different/incomplete channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- VK community: https://vk.com/gospod_bog
- VK videos: https://vk.com/video/@gospod_bog
- VK clips: https://vk.com/clips/gospod_bog
- VK community ID: `60805374`
- VK API owner ID: `-60805374`
- local YouTube/VK account alias: `legendary-poet`

Safety and project state:

1. The reviewed VK duplicate-delete run is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`, `run=completed`.
2. Never rerun old delete, canary, recovery, v3/v4, or fast-cleanup executors.
3. The read-only inventory dated 2026-07-31 resolved 1,781 public YouTube items: 1,673 long-form videos and 108 Shorts. The VK snapshot contains 2,879 ordinary video objects.
4. The exact long-form transfer boundary is YouTube ID `KobOzfBqzic`, title `Рождество: Правда и Вымысел - Джон МакАртур`. It is already present in VK and is excluded from upload.
5. There are 27 long-form uploads newer than that boundary. Exactly 26 are verified missing in the VK snapshot. The remaining item, YouTube ID `s512Opa8Eu4`, is already present as VK ID `-60805374_456241938` (same sermon, duration delta 1 second).
6. The verified long-form upload queue SHA-256 is `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`.
7. Shorts/Clips must use a separate manifest and ledger. The current VK API snapshot reported `vk_clips=0`, although the VK interface visibly contains clips. Therefore the provisional 65-item missing-Shorts list is not upload-authoritative and must never be executed.
8. Before any Shorts upload, inventory the live page `https://vk.com/clips/gospod_bog` and compare its real Clip IDs/titles/durations against all 108 canonical YouTube Shorts.
9. Never upload an ambiguous match. Exact source IDs and live platform IDs are required.
10. Do not infer transfer boundaries only from screenshots or relative labels such as “4 months ago”. Build current inventories.
11. Playlist organization, VK-native descriptions, postponed wall posts, and MP3 extraction happen only after the upload catalog is verified.
12. Never commit OAuth tokens, VK tokens, downloaded media, local exports, ledgers, logs, backups, or other ignored operational data.
13. For YouTube Shorts, canonical membership and order come from the flat ID list of `https://www.youtube.com/@fedormilovanov/shorts`. Resolve metadata only for those exact IDs. A resolved uploader/channel mismatch is a review warning, not a reason to abort the entire inventory, and no resolved ID may enter the manifest unless it was present in the canonical flat page list.
