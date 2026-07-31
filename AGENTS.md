# Repository agent instructions

Before any work involving Fedor Milovanov's YouTube/VK media workflow, read:

- `docs/operations/fedor-youtube-vk-transfer-reference.md`

That operational document is the source of truth and takes priority over chat memory.

Canonical identities:

- YouTube channel: https://www.youtube.com/@fedormilovanov
- YouTube videos: https://www.youtube.com/@fedormilovanov/videos
- YouTube Shorts: https://www.youtube.com/@fedormilovanov/shorts
- VK community: https://vk.com/gospod_bog
- VK videos: https://vk.com/video/@gospod_bog
- VK clips: https://vk.com/clips/gospod_bog
- VK community ID: `60805374`
- VK API owner ID: `-60805374`
- local YouTube/VK account alias: `legendary-poet`

Safety and project state:

1. The reviewed VK duplicate-delete run is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`, `run=completed`.
2. Never rerun old delete, canary, recovery, v3/v4, or fast-cleanup executors.
3. The next phase is read-only YouTube/VK inventory and exact missing-content matching.
4. Long-form and Shorts/Clips must use separate manifests and ledgers.
5. Never upload an ambiguous match. Exact source IDs and live platform IDs are required.
6. Do not infer transfer boundaries only from screenshots or relative labels such as “4 months ago”. Build current inventories.
7. Playlist organization, VK-native descriptions, postponed wall posts, and MP3 extraction happen only after the upload catalog is verified.
8. Never commit OAuth tokens, VK tokens, downloaded media, local exports, ledgers, logs, backups, or other ignored operational data.
