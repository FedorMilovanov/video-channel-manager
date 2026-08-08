# Current operational state

Updated: 2026-08-07  
Current production code baseline: `main@7a142dac360f682a3700f8106e336e69bd0e6533`  
Current machine-state overlay: [`audit-register-v12-2026-08-07.json`](audit-register-v12-2026-08-07.json)  
Immutable predecessor: [`audit-register-v11-2026-08-07.json`](audit-register-v11-2026-08-07.json)  
Earlier postponed-text predecessor: [`audit-register-v10-2026-08-06.json`](audit-register-v10-2026-08-06.json)

The newest machine-state overlay and this file override stale execution claims in older chats, screenshots, ZIP names, remembered counts, historical issue wording, and superseded executors. Historical Wave 13–16 and VK postponed-text proofs remain preserved in their immutable audit registers and runbooks; they are evidence only and never authorize replay.

## Active local album scope — Legendary Poet / «Чёрный человек»

Issue #154 is the single current project-bound owner for the new album workflow. PR #157 was squash-merged as `7a142dac360f682a3700f8106e336e69bd0e6533` after exact tested head `dec83f8f594b2a3fdf048e45fba6989c33905520` passed CI run `31167299479` / #3264 with all six required jobs green. The implementation performed provider reads/writes `0/0`.

Exact project identity:

- project key `legendary-poet`;
- YouTube OAuth alias `legendary-poet`;
- YouTube channel `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- album key `black-man`;
- intended album size: seven tracks.

The supported source model is intentionally mixed:

- tracks 1–6: `youtube_exact_source`, each requiring exact YouTube video ID and exact channel identity before acquisition;
- track 7: `local_controlled_master`, allowed to remain `pending_local_master` while the bonus version is still being created;
- the bonus track never receives a fabricated YouTube ID and does not need to be uploaded separately before album assembly.

The production CLI now exposes:

- `video-manager album init`;
- `video-manager album add-youtube`;
- `video-manager album add-local`;
- `video-manager album status`;
- `video-manager album acquire`;
- `video-manager album probe`;
- `video-manager album timing`;
- `video-manager album artwork-plan`;
- `video-manager album render`;
- `video-manager album verify`;
- `video-manager album package`.

Current local capability:

1. create and hash a deterministic album manifest;
2. bind YouTube tracks to exact 11-character source IDs without a network mutation;
3. bind a future or existing local bonus master to an explicit path;
4. acquire configured YouTube audio with `yt-dlp` only after read-only metadata proves both exact video ID and exact channel ID;
5. use `after_move:filepath` as the authoritative downloaded path inside a controlled album cache;
6. hash and `ffprobe` available masters without modifying source bytes;
7. build deterministic grid-aligned chapter timing only after every final track is probed;
8. reserve one neutral artwork state plus one active state for every track;
9. render a local H.264/AAC album MP4 with FFmpeg;
10. verify final media duration/streams and build a local package containing chapters and upload metadata with `provider_write_authorized=false`.

The current artwork contract for seven tracks therefore reserves eight PNG states: `cover-neutral.png` plus `track-01.png` through `track-07.png`.

### Album quality proof

Exact-head CI #3264 proved:

- Python 3.11/3.12/3.13 quality jobs: green;
- Windows PowerShell 5.1: green;
- PowerShell 7 Windows: green;
- PowerShell 7 Linux: green;
- Python 3.11: `897 passed, 1 xfailed`;
- coverage: `77%` across `16,487` statements;
- Ruff correctness: green;
- Ruff formatting: `480 files already formatted`;
- strict mypy: `153 source files`, no issues;
- dependency audit: no known vulnerabilities;
- review threads: `0`.

## Album operation phase and provider boundary

Current operation phase is **local pipeline implemented / exact source reconciliation pending**.

Allowed next work under issue #154:

- update the local checkout/install to `main` at or after `7a142dac360f682a3700f8106e336e69bd0e6533`;
- run a fresh official YouTube read-only scan for the exact Legendary Poet channel;
- reconcile the six existing full-length «Чёрный человек» source IDs from that scan;
- configure those six exact IDs in the local album manifest;
- acquire and probe the six source masters locally;
- keep track 7 in `pending_local_master` until the user freezes the bonus file;
- prepare artwork states;
- generate final timing and local render only after all seven masters are ready.

Not implemented or authorized by PR #157:

- YouTube video upload;
- YouTube metadata or thumbnail mutation;
- playlist creation/update/reordering;
- playlist membership mutation;
- deletion/replacement of a remote object;
- automatic publication;
- blind retry after any unknown provider effect.

A future provider execute phase requires a separately reviewed immutable exact-ID plan, durable intent-before-dispatch state, explicit user authorization, exact target binding, and exact provider postflight. The existence of a local album package, green CI, or issue #154 alone is not provider authorization.

## Current VK postponed-text capability — preserved predecessor

The reusable VK postponed-text v1 capability from issue #152 / PR #153 remains supported exactly as recorded in [`audit-register-v11-2026-08-07.json`](audit-register-v11-2026-08-07.json) and [`vk-postponed-text-edit-runbook-2026-08-06.md`](vk-postponed-text-edit-runbook-2026-08-06.md).

Its scope remains existing **attachment-free postponed VK wall posts only** with exact project/community/owner/post binding, immutable request and plan digests, complete preflight, exact before/after text and original `publish_date`, stable account/community lock, intent-before-dispatch journaling, exact readback/postflight, CAPTCHA stop without bypass, and no blind replay. Schema v1 still rejects target attachments and `allow_attachments=true`.

The completed 2026-08-06 Lord God cleanup remains historical evidence only: target postponed IDs `12513..12541`, `29/29` exact after-state, `0` pending, postponed count `66/66`, 37 non-target rows unchanged, and no published-post mutation. It is not authorized for replay.

## Preserved Wave 13–16 foundations

Wave 13–16 proofs remain immutable historical compatibility evidence in the v6–v9 audit registers. Important retained boundaries include:

- adaptive agents reason from exact identities and observable postconditions rather than remembered scripts;
- unknown or possibly completed provider effects require read-only reconciliation and never blind retry;
- local MP3 support remains local-only intake/manifest work and does not become a VK Audio writer;
- SQLite connections are explicitly closed and unclosed-database warnings remain blocking in tests;
- GitHub Actions use immutable Node 24-generation action pins;
- historical browser/ZIP upload experiments remain evidence only and must not be rerun.

The album pipeline is a separate local media capability. It does not broaden the VK Audio experimental boundary and does not revive retired upload, playlist, reset, recovery, transfer, article-wave, or browser executors.

## Credential and project isolation

This repository manages two distinct projects and never treats credentials as project selectors.

YouTube:

- `lord-god-strength` → OAuth alias `fedor-milovanov` → channel `UCeSJsC6go2c9pdJCuUI1BYA`;
- `legendary-poet` → OAuth alias `legendary-poet` → channel `UC-78ys2S3cQ3lpqgXfo-SvQ`.

VK uses a shared user credential, but every operation still binds exact project key, community/owner IDs, manifests, plans, journals, and results. The VK credential alias `legendary-poet` is never a project selector.

## Active operational graph

Active local/read-only owner:

- #154 — Legendary Poet seven-track «Чёрный человек» album: local pipeline implemented; exact six-source reconciliation and bonus local master remain pending; no provider mutation authorized.

Completed historical owners include #31, #38, #119, #130, #133, #137, #147, and #152. Retired/not-planned provider scopes include #32, #33, #99, and #123. Historical ownership distinctions remain unchanged; in particular #32 belonged to Lord God, #38 was shared/provider-neutral, and #119 belonged to Legendary Poet.

`M5hNecL_MsQ → -235216998_456239160` remains an ordinary VK video with `is_draft=1`, is not native Clip success, and must not be retransmitted.

## Permanent safety rules

- Provider writes remain unauthorized outside a newly reviewed exact operation and explicit user authorization.
- Never select a remote source by fuzzy title when an exact ID can be established.
- Never fabricate a remote identity for a local asset.
- Never infer provider success from HTTP status, process exit code, screenshot, visible playback, filename, stdout line, or package name alone.
- Never blind-retry an accepted, processing, verified, or unknown mutation.
- Existing VK and YouTube objects remain untouched by repository-only engineering, local album acquisition/rendering, CI, manifests, previews, or packaging.
- Content in quotation marks must map to a contiguous source passage unless explicitly labeled synthesis.

## Next allowed action

Continue issue #154 from the **read-only source reconciliation** phase: update the local installation, verify that `video-manager album --help` resolves from current `main`, run an exact Legendary Poet YouTube scan, then configure the six proven source IDs. Track 7 may remain pending until its local bonus master is finished. No provider upload or playlist mutation is currently authorized.
