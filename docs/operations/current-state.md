# Current operational state
Updated: 2026-08-20

This file is the concise current operational interpretation. It does **not** authorize provider mutation. Historical issues, comments, pull requests, CI runs, credentials and release receipts are evidence only; they are never standing execution authority.

For every new task, resolve the exact current `main` commit and relevant durable state at task start. Do not treat an older SHA, issue body, checkpoint comment or workflow as the live baseline when newer terminal evidence exists.

## Completion and authority model

Repository implementation, artifact production and provider rollout are separate completion states.

- A completed artifact/provider outcome is not retroactively reopened only because a stricter policy is introduced later.
- Implementation completion does not itself authorize execution.
- An old successful rollout does not authorize a new mutation.
- An ambiguous provider effect remains blocking unless exact read-only reconciliation or a narrowly bound terminal no-replay disposition resolves it.
- Credentials authenticate; exact project identity, target binding, immutable operation/release identity, durable state and fresh explicit execution authority select the operation.
- No blind provider retry is authorized anywhere by this document.

## Repository source of truth

Only `main` is a supported repository code/runtime execution baseline.

`state/lordchrist-telegram`, `state/svodka-telegram`, and `state/milovi-cake-telegram` are durable state-only refs. None of them is a runtime/code baseline.

Ephemeral `work/`, `agent/` and `research/` refs are non-authoritative after their scope closes. Preserve unique useful commits before cleanup; never rewrite a durable state ref as branch hygiene.

## YouTube / Legendary Poet / «Чёрный человек»

The historical authorized rollout is complete. Public video `x-puy27S2qs` remains the collision guard for that exact project/channel/media identity. Processing, public visibility, custom thumbnail, playlist membership and the top-level comment were verified during the completed rollout.

The current `main` includes the guarded YouTube release executor; implementation completion does not itself authorize execution.

Issue #154 is closed as **completed**. The historical provenance gap predates the later quality-master binding rule and is not required rework. Do not regenerate or reupload the album solely to satisfy policy introduced after the published bytes were produced. No future YouTube upload, metadata edit, thumbnail change, playlist mutation, visibility change, comment mutation, deletion or replacement is authorized by this state.

## Telegram / LordChrist

The legacy `@lordchrist` quote publisher remains a separate live content track with its own durable ledger and no-blind-retry contract.

The historical research-v2 canary ambiguity is no longer a legacy blocker. Issue #286 / PR #287 introduced the exact `retired_no_replay` disposition. For every unrelated ambiguity, every other `dispatching` or `may_exist` effect remains fail-closed. By contract, the retired August research release itself cannot resume, retry, or authorize a successor.

Issue #168 is closed as repository implementation complete. The generic LordChrist profile remains `provider_writes_authorized=false`; any future research or rich provider mutation still requires a new exact scope and authorization.

The first rich successor publication is complete:

- publication `lordchrist-rich-sermons-survive-century` — «Перо, стенографист и магнитная лента»;
- Telegram message `1484`;
- durable state `published / provider_effect=verified`;
- exactly one `sendRichMessage`;
- exact returned rich structure and exact all three reviewed documentary media;
- no retry, `sendMessage` fallback, edit, delete or pin.

Issue #473 is closed as completed. The second reviewed rich article remains provider-inert. The completed one-shot rich live canary/controller workflows have been retired from executable `main`; durable evidence and reusable runtime/source remain preserved.

The LordChrist YouTube Shorts → Telegram native-video **repository implementation is complete and hardened** through PRs #502, #504 and #505. The provider-inert lane uses stable `lordchrist-short-<youtube_video_id>` publication identities, fresh owner-snapshot evidence, exact owner-media SHA-256/size bindings, immutable snapshot-bound candidate approval, complete durable-state proof, content-addressed release identities and a `17:17 Europe/Moscow` slot that preserves the configured four-hour gap from the `21:17` editorial catch-up slot. Issue #503 remains the current **artifact-level** scope until a fresh owner `video-manager youtube scan` AuditPackage and exact Google Takeout/local owner media are available and classified/prepared. Historical duration-only snapshots are reconciliation evidence only. No Telegram publication, Telegram Story, MTProto/user-session action, YouTube mutation, release authorization or execution authority is created by this implementation state.

Canonical Shorts runbook: [`lordchrist-shorts-feed.md`](lordchrist-shorts-feed.md).

## Telegram / Svodka

Issue #170 is closed as repository pipeline implementation complete. The historical August approval bound release `svodka-pilot-2026-08`. The historical profile used `provider_writes_authorized=true` only for the reviewed rollout gates; that phrase describes the reviewed rollout contract, not standing authority. As historical rollout evidence, the durable ledger now exists on `state/svodka-telegram`.

Issue #235 is closed as completed. The finished successor path has two durable verified publications:

- `svodka-rich-goldfish-three-second-memory-myth` — Telegram message `28`, verified by provider-free reconciliation of the archived HTTP-200 exact-target/exact-media response; no replay occurred;
- `svodka-rich-wombat-cubic-poop` — fresh v4 successor, `dispatch_mode=scheduled`, Telegram message `29`, `published / provider_effect=verified`, `error=null`.

The intervening v3 wombat identity ended `failed_no_effect / confirmed_absent` with no message id after Telegram could not fetch its original remote image. That attempt is immutable and was not retried under the same release identity.

Historical messages `26` and `27` and expired v2/v3 mutation identities remain non-replayable evidence. The old August schedule is not a catch-up queue.

The original 14-entry `svodka-pilot-2026-08` ledger on `state/svodka-telegram` is now fully terminalized: all 14 historical entries are `skipped / provider_effect=impossible`, with no intent, workflow run, message id or provider effect. The provider-free stale-window cleanup debt is closed. These terminal records are historical no-replay evidence, not a publication backlog or execution authority.

The completed message-28 reconciliation workflow and verified v4 successor workflow have been retired from executable `main`. Historical release/runtime/evidence and legacy provider-free/recovery contracts remain where required for reproducibility. No new Svodka Telegram mutation is authorized by this state.

## VK / Milovi Cake / Issue #323

Issue #323 is closed. The marathon closure accepted the exact 12 allowlisted Milovi Cake sources as completed native VK Clip uploads with their base durable logical wall mappings; all 12 reached durable rollout completion rather than the older 8/12 checkpoint.

Older Issue #323 body text and comments that say `OPEN`, `8/12`, source 9 `upload_in_progress`, or sources 10–12 `pending` are historical fail-closed checkpoints and must not be used as current authority.

Durable safety lessons remain current: verified Clip identities are not duplicate-uploaded because of transient provider projection; postponed wall provider IDs may change only through a proven due publication transition; aggregate omission is not exact disappearance proof; wall `-68859909_475` destructive cleanup authority is consumed; ambiguous provider responses require exact reconciliation; the retired legacy finalizer must not return as a second mutation authority; and the historical STOP replay corpus remains provider-inert regression evidence.

Later optional promotion/metadata/finalizer work must not be reinterpreted as “missing Clip uploads.” Any new VK mutation requires a new exact scope, fresh identity/evidence and separate execution authority.

Canonical historical analysis remains [`2026-08-14-milovi-issue-323-interim-postmortem.md`](2026-08-14-milovi-issue-323-interim-postmortem.md). The reusable architecture target remains [`vk-native-clip-golden-path.md`](vk-native-clip-golden-path.md).

## Telegram / Milovi Cake / Issue #353

The live canary-v2 is completed historical evidence: it proved the exact `@MiloviCake` / chat `-1002215328390` / bot `8716602202` path with one durable intent, one provider mutation attempt, a verified message and no blind retry. That completed canary never grants authority to another publication.

The permanent architecture is now a single feed control plane. `.github/workflows/milovi-telegram-feed-publisher.yml` is the only supported Milovi Telegram provider writer. It is manual-only, owns `state/milovi-cake-telegram` and concurrency group `milovi-cake-telegram-publisher`, and shares the repository generic Telegram prepare/send/apply runtime rather than introducing a second transport.

Historical bootstrap, one-off canary, live-canary-v2, ledger-init, per-publication controller/quality/media-proof, and `follow-on-*` readiness/media-proof workflows are retired from executable `main`. Historical JSON, frozen manifests, provider receipts and durable evidence remain non-executable evidence. The only other Milovi Telegram workflow beside permanent publisher/quality is exact target discovery, which is read-only and must remain independent of technical write-capability state.

Each new feed publication uses one immutable `milovi-feed-YYYYMMDD-NNN` bundle: exact runtime release, exact media binding where applicable, exact release ledger on the durable state branch, a channel-wide feed index, and a separate execution-authority object. Release/content authorization and provider execution authorization are separate gates. State initialization is explicit and provider-free after exact release authorization; missing state is never auto-created during publish.

Before one provider attempt, the permanent writer requires exact current `main`, exact quality, exact initialized state, channel-wide duplicate-guard agreement, strict freshness, exact target preflight and fresh exact human execution authority. It persists durable intent before `send-once`, performs zero blind mutation retries, and persists verified or blocking outcome before completion.

`milovi-feed-20260819-001` is immutable stale provider-inert history and must not be caught up, retimed or reinterpreted as a successor. The current exact candidate is `milovi-feed-20260820-001`, scheduled for `2026-08-20T10:30:00+03:00` with frozen `p16` JPEG transport and caption. Its runtime release remains `release_authorized=false`, its execution authority remains `execution_authorized=false`, and `provider_mutation_allowed=false`; its permanent feed ledger is not initialized and no Telegram access or mutation has occurred.

The native-video lane is now artifact-complete at `16 / 16` accepted Telegram-ready MP4/H.264 outputs. The exact provider-free build is durably preserved on content-addressed review branch `agent/milovi-video-accepted-73c578eff825` with evidence digest `sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`; its accepted evidence records `provider_access_performed=false` and `provider_write_performed=false`. This artifact completion does not authorize Telegram publication, does not initialize feed state, and does not reopen or modify the photo-feed architecture.

Canonical runbook: [`milovi-telegram-feed-control-plane.md`](milovi-telegram-feed-control-plane.md).

## Telegram runtime / supply chain

The minimal Telegram runtime remains exact-version and SHA-256 hash locked with pip `--require-hashes`. Production/minimal installs keep the hash-locked transaction isolated from test-only dependencies. Any lock refresh is one explicit coherent supply-chain change and must pass isolated install, `pip check`, guarded provider-free CLI smoke and dependency audit before acceptance.

One durable state/concurrency namespace has one write owner at a time. Parallel agents must not create competing provider writers against the same state namespace.

## Local MP3 and Resi DASH

Supported Local MP3 capability remains `local_only_read_only_intake_and_manifest`: inspect, probe, hash, tag inventory and deterministic manifests. It does not authorize ID3 rewrite, rename/transcode, remote upload, metadata mutation, playlist changes or wall publication.

Resi remains the repository-owned local three-stage flow: `watch` -> `sample` -> explicit `handoff`. The watcher never auto-dispatches a multi-gigabyte FULL download; language-sensitive work samples sermon speech before full handoff. The retained `<TITLE> - FULL.mp4` master goes to canonical Windows Downloads (`C:\Users\Fedor\Downloads`); generated handoff/watcher control files and exact-trim outputs remain under repository `operator-output` unless explicitly redirected. This capability has provider effect `impossible` and does not bypass DRM/access controls or infer rights/permission. Canonical runbooks remain [`resi-dash-local-handoff.md`](resi-dash-local-handoff.md) and [`resi-grace-russian-live.md`](resi-grace-russian-live.md).

## GitHub governance

The latest read-only repository observation still reports source `main` as `protected=false` and repository ruleset count `0`. Dependency Graph itself is policy-enabled for this public repository. SBOM REST export is verified unavailable through both documented generation surfaces at the recorded probe points; that scoped result must not be collapsed into a blanket `UNVERIFIED` item.

Repository policy files and green checks do not create branch protection by themselves. Issue #443 was closed `not_planned` because the connected mutation surface did not provide the required repository-admin branch-protection/ruleset operation. Re-check live GitHub governance before claiming that protection has changed.

## Next safe work

1. Do not reopen completed Svodka, LordChrist rich canary or Milovi Clips work because an older issue body or checkpoint says it was incomplete.
2. Continue LordChrist Shorts Issue #503 only as `official_api_read` + `local_only` artifact work: obtain one fresh owner AuditPackage from the existing `fedor-milovanov` OAuth runtime, classify it through the merged readiness/inventory path, bind exact owner Takeout/local media, and keep every release preview provider-inert. Do not treat the historical 2026-07-29 package as current completion evidence.
3. Keep `milovi-feed-20260820-001` provider-inert until a separate exact release authorization and a separate fresh exact human execution authorization are deliberately created; `milovi-feed-20260819-001` remains stale immutable no-catch-up history.
4. Treat the Milovi native-video artifact lane as complete at `16 / 16`; preserve its content-addressed accepted branch/evidence as immutable artifact proof and do not infer any Telegram execution authority from it.
5. Continue branch hygiene only with exact unique-commit/PR-state proof; preserve all durable `state/*` refs.
6. For any new provider-visible work, start with fresh current `main`, fresh durable state, exact target identity and a new explicit owning scope.

Nothing in this document is authorization for a provider mutation.
