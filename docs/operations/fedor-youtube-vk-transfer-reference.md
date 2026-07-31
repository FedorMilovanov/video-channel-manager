# Fedor Milovanov: YouTube → VK transfer reference

Updated: 2026-07-31

This document is the operational source of truth for the remaining YouTube → VK transfer, subsequent VK playlist organization, postponed wall posts, and MP3 extraction. It takes priority over chat memory.

## Accounts and canonical links

### YouTube

- Channel handle: `@fedormilovanov`
- Channel: https://www.youtube.com/@fedormilovanov
- Long-form videos: https://www.youtube.com/@fedormilovanov/videos
- Shorts: https://www.youtube.com/@fedormilovanov/shorts
- Local account alias used by Video Channel Manager: `legendary-poet`

### VK

- Community ID: `60805374`
- VK API owner ID: `-60805374`
- Canonical community URL: https://vk.com/gospod_bog
- Stable numeric community URL: https://vk.com/public60805374
- Video section: https://vk.com/video/@gospod_bog
- Clips section: https://vk.com/clips/gospod_bog
- Stored VK account alias used by Video Channel Manager: `legendary-poet`

The live vanity screen name is `gospod_bog`. API operations must still use numeric community ID `60805374` and owner ID `-60805374`; never use the vanity name as an API identity guard.

### Repository and local paths

- GitHub repository: https://github.com/FedorMilovanov/video-channel-manager
- Repository path: `C:\Users\Fedor\Projects\video-channel-manager`
- Delete-orchestrator worktree: `C:\Users\Fedor\Projects\video-channel-manager-orchestrator`
- Durable delete ledger: `C:\Users\Fedor\Projects\video-channel-manager\data\vk\delete-orchestrator.db`
- Completed fast-cleanup log: `C:\Users\Fedor\Projects\video-channel-manager\data\vk\fast-cleanup-final-20260731-031942.log`

## Completed duplicate cleanup

The reviewed duplicate-delete decision set contained exactly 403 candidate videos.

Final verified state:

- `confirmed_deleted=403`
- `planned=0`
- `unresolved=0`
- `run=completed`
- VK owner inventory after cleanup: `2879` videos

Signed policy:

- decision set: `vk-lord-strength-delete-megawave-20260730`
- community: `60805374`
- operation count: `403`
- policy SHA-256: `sha256:6c5f6f856c72c685d7e6bf33a163b9e9c3513464e76ec3d45edaa57c73539ded`

Do not run any old delete, canary, recovery, v3, v4, or fast-cleanup executor again. The delete phase is closed.

Protected primary example retained during cleanup:

- VK ID: `-60805374_456239743`
- title: `Уникальность Церкви | 4 | Вопросы и ответы | Джон МакАртур в Москве 1999`

## Remaining YouTube → VK transfer

VK Video Transfer was previously used, but became unreliable and reported that videos were still processing. Remaining content must be determined from live YouTube and live VK inventories rather than estimated from screenshots alone.

### Long-form boundary

The previous transfer is known to include:

- `Рождество: Правда и Вымысел - Джон МакАртур`

The video below is **not** the inclusive boundary and must be checked as part of the missing range:

- `Христос Умер Для Бога | Римлянам 3:25–31 | Джон МакАртур`

Operational rule:

1. Build the complete current YouTube long-form inventory in newest-first order.
2. Build the complete current VK video inventory.
3. Treat every YouTube upload newer than `Рождество: Правда и Вымысел - Джон МакАртур` as a transfer candidate.
4. Also include `Рождество: Правда и Вымысел - Джон МакАртур` in comparison, but do not upload it if the live VK match exists.
5. Do not assume that approximately 56 means exactly 56; derive the exact count from live IDs and duration/title matching.

### Shorts boundary

A previously observed transferred Short is:

- `Закрой Всякое Окно Для Греха - Джоэл Бики ()`

The trailing `()` is an unwanted title artifact and should be removed during VK editorial cleanup.

This Short is not a reliable chronological cutoff by itself: screenshots show later YouTube Shorts that may already exist in VK. Therefore:

1. Inventory every current YouTube Short.
2. Inventory current VK Clips.
3. Match by exact source URL/YouTube ID when available; otherwise use normalized title, duration, publication order, and visual/manual review for ambiguous cases.
4. Upload only confirmed missing Shorts.
5. Keep Shorts/Clips in a separate manifest and ledger from long-form videos.

## Matching rules

Never decide only from title text.

Preferred evidence, strongest first:

1. persisted YouTube video ID/source URL in VK metadata or transfer ledger;
2. exact normalized title plus duration tolerance;
3. normalized title, speaker/series, part number, and duration;
4. thumbnail or manual review for ambiguous candidates.

Required output groups:

- already present in VK;
- confirmed missing in VK;
- ambiguous/manual review;
- duplicate in VK;
- present but title/description/playlist needs repair.

No upload executor may consume the ambiguous group.

## Transfer policy

- Download/upload only content owned or controlled by the channel operator.
- One source YouTube ID may map to at most one new VK video/clip ID.
- Use a durable SQLite ledger before the first upload.
- Record intent before requesting an upload URL.
- Persist every upload response and resulting VK ID.
- Never automatically repeat a request with an unknown outcome; reconcile first.
- Preserve the best available original file. Prefer local masters or the operator's YouTube export over low-quality screen capture.
- Long-form videos and Shorts use separate queues.
- Do not create or import playlists during the raw upload pass. Organize after the exact surviving/uploaded catalog is known.

## Post-transfer workflow

1. Verify all newly uploaded VK IDs and durations.
2. Build a clean VK playlist/album taxonomy.
3. Repair titles, including removal of artifacts such as trailing `()`.
4. Write VK-native plain-text descriptions.
5. Create a postponed wall-post queue with deduplication and exact publication timestamps.
6. Extract MP3 from controlled local/source files with FFmpeg.
7. Normalize audio, add ID3 tags and artwork, and create a separate audio manifest.
8. Test VK audio upload permissions on one file before any batch audio operation.

## Planned artifacts

- `youtube-longform-current.json`
- `youtube-shorts-current.json`
- `vk-video-current.json`
- `vk-clips-current.json`
- `youtube-vk-longform-match.csv`
- `youtube-vk-shorts-match.csv`
- `missing-longform.json`
- `missing-shorts.json`
- `ambiguous-longform.csv`
- `ambiguous-shorts.csv`
- `upload-ledger.db`
- `playlist-plan.csv`
- `postponed-posts-plan.csv`
- `mp3-queue.json`

## Immediate next action

Run a read-only inventory and matching pass against the canonical YouTube channel and VK community. Do not upload anything until the exact missing manifests have been reviewed and their counts and SHA-256 digests recorded.
