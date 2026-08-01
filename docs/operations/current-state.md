# Current operational state

Updated: 2026-08-01

This file is the first place to check before continuing the current **Господь Бог — Сила Моя** YouTube → VK workflow.

The repository manages two separate projects. Read [`project-identity-registry.md`](project-identity-registry.md) before using any account alias or public link.

## Current project selection

- Project key: `lord-god-strength`
- Project: `Господь Бог — Сила Моя`
- The separate project `legendary-poet` / `The Legendary Poet — Легендарный Поэт` is outside the current scope and must not be touched.

## Credential model

### YouTube

Two separate local OAuth aliases are used, one per selected YouTube/Brand Account channel:

- `fedor-milovanov` — current theological channel authorization, presently read-only;
- `legendary-poet` — The Legendary Poet, presently write-capable.

For current YouTube writes, reauthorize the same `fedor-milovanov` alias with `--write --force`. Never substitute the poet alias.

### VK

One shared VK user token is intentionally used for both communities. Its canonical operational alias is `legendary-poet`, but the alias is only a credential label. Project isolation is enforced with exact numeric community and owner IDs in each operation.

A second local alias `default` was created on 2026-08-01 by running `video-manager vk login` without `--account`. Do not use `default` in operational commands. It does not represent a third project and must not replace the reviewed `legendary-poet` alias.

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

`BLOCKED_UNTIL_FEDOR_MILOVANOV_ALIAS_IS_REAUTHORIZED_FOR_WRITE_AND_ID_VERIFIED`

### VK — current project

- Community title: `† Господь Бог - Сила Моя! †`
- Canonical viewer-facing community: https://vk.ru/the_lord_god_is_my_strength
- Published compatibility URL: https://vk.com/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Community ID: `60805374`
- API owner ID: `-60805374`
- Shared local user-token alias: `legendary-poet`

The shared VK token belongs to user `Федор Милованов` and can see several communities. Every current VK write must bind and confirm numeric community ID `60805374` and owner ID `-60805374`.

Historical `gospod_bog` vanity paths are operational history, not current canonical viewer links. Do not insert them into new descriptions without a fresh live verification.

### Current project links

Default compact footer:

- Website: https://gospod-bog.ru/
- Telegram: https://t.me/lordchrist
- VK: https://vk.ru/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Rutube: https://rutube.ru/channel/1876662/

Additional registered links, not part of the default compact footer:

- Odnoklassniki: https://ok.ru/christjesus
- Facebook group: https://facebook.com/groups/116164165395881

No current description, comment, playlist, post, or footer may use The Legendary Poet links unless an explicit per-operation cross-project exception has been reviewed.

### Repository and local paths

- Repository: https://github.com/FedorMilovanov/video-channel-manager
- Local repository: `C:\Users\Fedor\Projects\video-channel-manager`
- Historical delete worktree: `C:\Users\Fedor\Projects\video-channel-manager-orchestrator`
- Delete ledger: `C:\Users\Fedor\Projects\video-channel-manager\data\vk\delete-orchestrator.db`
- Final cleanup log: `C:\Users\Fedor\Projects\video-channel-manager\data\vk\fast-cleanup-final-20260731-031942.log`
- Inventory report directory: `C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-vk-transfer-20260731-140628`
- Long-form upload ledger directory: `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26`
- Shorts upload ledger directory: `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-shorts`

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

For YouTube mutation, first reauthorize the current-project alias:

```powershell
video-manager youtube login --account fedor-milovanov --write --force
```

The authorization command must print exactly channel ID `UCeSJsC6go2c9pdJCuUI1BYA`. Otherwise stop without scanning or writing.

## Critical VK wall safety block

The owner reports that a previous transfer produced a large sequence of one-video wall posts instead of a gradual postponed queue.

Current wall mutation status:

`BLOCKED_PENDING_ISSUE_36_AND_FRESH_READ_ONLY_WALL_AUDIT`

Mandatory rules:

1. Video upload and wall publication are separate operations.
2. Every upload executor must explicitly send `wallpost=0`, `auto_publish=0`, and `repeat=0` unless a reviewed video-specific exception exists.
3. Every upload manifest must state `wall_mutation_authorized=false`.
4. Upload postflight must fail if any unexpected wall post appears.
5. Shorts/Clips must never be shared to the wall automatically.
6. Wall publication must use a separate postponed plan with exact `publish_date`, deterministic `guid`, duplicate scan, dry-run, lock, repeated preflight, and postflight.
7. Immediate `wall.post` is prohibited for the current project by default.
8. Existing wall posts must not be bulk-deleted without a fresh exact-ID, engagement-aware, reviewed deletion plan.

Incident details: [`2026-08-01-vk-wall-and-short-player-incident.md`](2026-08-01-vk-wall-and-short-player-incident.md).

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

Final read-only public inventory used for transfer classification:

- YouTube total: `1781`
- YouTube long-form: `1673`
- YouTube Shorts: `108`
- complete VK owner inventory observed by the Shorts workflow: `2903`

Ordinary and short-form surfaces must still be distinguished by final VK object `type` and processing state.

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

### Long-form reconciliation

The upload is not considered complete until this result and ledger are reviewed:

- `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26\upload-result.json`
- `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26\upload-ledger.db`

Do not infer completion from terminal silence, VK processing messages, or elapsed time.

### Shorts reconciliation

Authoritative source classification from the completed owner inventory:

- canonical YouTube Shorts: `108`;
- already present: `42`;
- already present duplicate source: `1`;
- originally confirmed missing: `65`;
- ambiguous: `0`.

Last reviewed state for 64 native uploads accepted by VK:

- confirmed `type=short_video`: `44`;
- still processing: `6`;
- accepted but not yet visible through exact-object reconciliation: `14`;
- wrong completed type: `0`;
- one source remained failed before VK upload because YouTube authentication blocked the download.

No retransmission is allowed for accepted/processing objects. Reconcile exact VK IDs first.

Direct native uploads may look and play differently from external YouTube imports because VK exposes a distinct `short_video` type and clip player. During conversion, a future clip may temporarily appear as ordinary `video`; final classification must be checked after processing.

## GitHub tracking

- [Issue #31 — verify the 26-video upload result and reconcile the ledger](https://github.com/FedorMilovanov/video-channel-manager/issues/31)
- [Issue #32 — inventory/reconcile the real VK Clips surface and final Shorts types](https://github.com/FedorMilovanov/video-channel-manager/issues/32)
- [Issue #33 — organize and publish the verified VK catalog after transfer completion](https://github.com/FedorMilovanov/video-channel-manager/issues/33)
- [Issue #36 — block upload-triggered wall spam and require postponed publishing](https://github.com/FedorMilovanov/video-channel-manager/issues/36)

Issue #33 is blocked until issues #31, #32, and #36 have no silent unknown outcomes and their exact target IDs/manifests are recorded.

## Required next actions

1. Reconcile every long-form upload outcome against exact live VK IDs.
2. Reconcile all 64 accepted Shorts after processing and record final `type`, dimensions, player/platform fields, and wall references.
3. Obtain or document the single remaining blocked YouTube Short without repeating accepted uploads.
4. Run a fresh read-only wall audit covering both published and postponed posts.
5. Classify historical wall posts into intentional, auto-generated, duplicate, engaged/manual-review, and safe-removal candidates.
6. Build clean VK playlists/albums.
7. Repair titles and remove transfer artifacts such as trailing `()`.
8. Write VK-native plain-text descriptions using only the current project's registered links.
9. Build a deduplicated postponed wall-post queue with exact timestamps. No immediate posts.
10. Extract MP3 from controlled source files with FFmpeg only after the video catalog is verified.
11. Test VK audio-upload permissions with one file before any audio batch.

## Required update protocol

After every operational run, update this document with:

- selected `project_key`;
- resolved YouTube channel ID and VK community/owner ID;
- run timestamp;
- manifest SHA-256;
- attempted/accepted/verified/failed/unknown counts;
- published/postponed wall counts when a wall audit is involved;
- result and ledger paths;
- exact remaining work;
- whether a retry is safe;
- any new provider, identity, link-profile, media-type, wall, or packaging failure.
