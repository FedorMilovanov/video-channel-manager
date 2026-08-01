# Current operational state

Updated: 2026-08-01

This file is the first place to check before continuing the current **Господь Бог — Сила Моя** YouTube → VK workflow.

The repository manages two separate projects. Read [`project-identity-registry.md`](project-identity-registry.md) before using any account alias or public link.

## Current project selection

- Project key: `lord-god-strength`
- Project: `Господь Бог — Сила Моя`
- The separate project `legendary-poet` / `The Legendary Poet — Легендарный Поэт` is outside the current scope and must not be touched.

## Canonical accounts and links

### YouTube — current project

- Project/channel currently shown by the local account listing as: `Fedor Milovanov`
- Handle: `@fedormilovanov`
- Channel: https://www.youtube.com/@fedormilovanov
- Long-form videos: https://www.youtube.com/@fedormilovanov/videos
- Shorts: https://www.youtube.com/@fedormilovanov/shorts
- Authoritative public channel ID: `UCeSJsC6go2c9pdJCuUI1BYA`
- Current local account alias: `fedor-milovanov`
- Current access as of 2026-08-01: `read-only`

The local YouTube alias `legendary-poet` has write access but resolves to the separate channel `The Legendary Poet`. It is prohibited for the current project.

Important identity warning: an earlier stored OAuth identity returned channel ID `UC-78ys2S3cQ3lpqgXfo-SvQ` and an incomplete 131-video inventory. Before any YouTube write, the write-capable OAuth identity must be verified to resolve exactly to `UCeSJsC6go2c9pdJCuUI1BYA`.

Current YouTube mutation status:

`BLOCKED_NO_VERIFIED_WRITE_TOKEN_FOR_CURRENT_PROJECT`

### VK — current project

- Community title: `† Господь Бог - Сила Моя! †`
- Canonical community: https://vk.com/the_lord_god_is_my_strength
- Alternate/historical vanity URL: https://vk.com/gospod_bog
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Historical browser videos path: https://vk.com/video/@gospod_bog
- Historical browser Clips path: https://vk.com/clips/gospod_bog
- Community ID: `60805374`
- API owner ID: `-60805374`
- Current local user-token alias: `legendary-poet`

The VK alias is only a credential label. The token belongs to user `Федор Милованов` and can see multiple communities, including both projects. Every current VK write must bind and confirm numeric community ID `60805374` and owner ID `-60805374`.

### Current project links

- Website: https://gospod-bog.ru/
- Telegram: https://t.me/lordchrist
- Rutube: https://rutube.ru/channel/1876662/
- Facebook group: https://facebook.com/groups/116164165395881

No current description, comment, playlist, post, or footer may use The Legendary Poet links unless an explicit per-operation cross-project exception has been reviewed.

### Repository and local paths

- Repository: https://github.com/FedorMilovanov/video-channel-manager
- Local repository: `C:\Users\Fedor\Projects\video-channel-manager`
- Historical delete worktree: `C:\Users\Fedor\Projects\video-channel-manager-orchestrator`
- Delete ledger: `C:\Users\Fedor\Projects\video-channel-manager\data\vk\delete-orchestrator.db`
- Final cleanup log: `C:\Users\Fedor\Projects\video-channel-manager\data\vk\fast-cleanup-final-20260731-031942.log`
- Inventory report directory: `C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-vk-transfer-20260731-140628`
- Upload ledger directory: `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26`

## Required identity preflight

Before the current API rollout, run:

```powershell
video-manager youtube channels --account fedor-milovanov
video-manager vk communities --account legendary-poet
```

Continue only when the selected identities are exactly:

```text
project_key: lord-god-strength
YouTube channel ID: UCeSJsC6go2c9pdJCuUI1BYA
VK community ID: 60805374
VK API owner ID: -60805374
```

A YouTube write additionally requires a write-capable OAuth token for the same channel ID. The existing `legendary-poet` YouTube write token is not acceptable.

## Completed work

### VK duplicate cleanup

The reviewed exact deletion set contained 403 videos.

Final verified result:

- `confirmed_deleted=403`
- `planned=0`
- `unresolved=0`
- `run=completed`
- stable ordinary-video inventory after cleanup: `2879`

Policy SHA-256:

`sha256:6c5f6f856c72c685d7e6bf33a163b9e9c3513464e76ec3d45edaa57c73539ded`

This phase is closed. Do not rerun any deletion executor from it.

### Public YouTube and VK inventory

Final read-only public inventory:

- YouTube total: `1781`
- YouTube long-form: `1673`
- YouTube Shorts: `108`
- VK ordinary videos: `2879`
- VK Clips covered by the ordinary API snapshot: `0`

The zero Clips count is a coverage limitation, not proof that no clips exist.

### Exact long-form tail

Boundary already present in VK:

- YouTube ID: `KobOzfBqzic`
- title: `Рождество: Правда и Вымысел - Джон МакАртур`
- action: never upload again

Newer long-form items:

- total newer than boundary: `27`
- verified missing: `26`
- resolved already present: `1`

Resolved present item:

- YouTube ID: `s512Opa8Eu4`
- VK ID: `-60805374_456241938`
- evidence: same sermon/title identity and one-second duration difference

Verified 26-item upload queue SHA-256:

`b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`

## Work currently in progress

A resumable uploader for the 26 verified-missing long-form videos has been prepared for local execution.

The upload is not considered complete until this result exists and is reviewed:

`C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26\upload-result.json`

Expected durable ledger:

`C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26\upload-ledger.db`

Until the result is inspected, status is:

`UPLOAD_26 = IN_PROGRESS_OR_UNVERIFIED`

Do not infer completion from terminal silence, VK processing messages, or elapsed time.

## GitHub tracking

- [Issue #31 — verify the 26-video upload result and reconcile the ledger](https://github.com/FedorMilovanov/video-channel-manager/issues/31)
- [Issue #32 — inventory the real VK Clips surface and derive the exact Shorts queue](https://github.com/FedorMilovanov/video-channel-manager/issues/32)
- [Issue #33 — organize and publish the verified VK catalog after transfer completion](https://github.com/FedorMilovanov/video-channel-manager/issues/33)

Issue #33 is blocked until issues #31 and #32 have no silent unknown outcomes and their exact target IDs/manifests are recorded.

## Shorts status

The preliminary matcher reported:

- YouTube Shorts: `108`
- matched in ordinary VK inventory: `42`
- provisional missing: `65`
- ambiguous: `1`
- VK Clips seen by current API snapshot: `0`

The 65-item list is explicitly `DO_NOT_UPLOAD` because the current inventory did not cover the real VK Clips surface. Existing clips are visible in the VK UI, including title artifacts such as trailing `()`.

Required next step:

1. Inventory the live VK Clips surface.
2. Resolve exact clip IDs, titles, durations, and publication order.
3. Compare all 108 canonical YouTube Shorts against that inventory.
4. Produce separate present, missing, ambiguous, and title-repair manifests.
5. Upload only the exact confirmed-missing set with a separate ledger.

## Work after transfer verification

Proceed in this order:

1. Verify every newly uploaded VK ID and duration.
2. Build clean VK playlists/albums.
3. Repair titles and remove transfer artifacts such as trailing `()`.
4. Write VK-native plain-text descriptions using only the current project's registered links.
5. Build a deduplicated postponed wall-post queue with exact timestamps.
6. Extract MP3 from controlled source files with FFmpeg.
7. Normalize loudness and add ID3 tags and cover art.
8. Test VK audio-upload permissions with one file before any audio batch.

## Required update protocol

After every operational run, update this document with:

- selected `project_key`;
- resolved YouTube channel ID and VK community/owner ID;
- run timestamp;
- manifest SHA-256;
- attempted/accepted/verified/failed/unknown counts;
- result and ledger paths;
- exact remaining work;
- whether a retry is safe;
- any new provider, identity, link-profile, or packaging failure.
