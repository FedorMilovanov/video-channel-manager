# Current operational state

Updated: 2026-08-15

This file is the concise current operational interpretation. It does **not** authorize provider mutation. Historical audits/PRs/issues are evidence only.

For every new task, resolve the exact current `main` commit and relevant durable state at task start; do not treat a SHA written in an old document as the live baseline.

Latest repository/local control continuation: [`control-audit-continuation-2026-08-09.md`](control-audit-continuation-2026-08-09.md).

## Current closure model

Repository implementation, final artifact production, and live provider rollout are separate completion states.

- Repository code may be complete while live rollout remains intentionally unauthorized or incomplete.
- A completed artifact/provider outcome is not retroactively reopened only because a stricter policy is introduced later; reopening requires a new explicit owning scope.
- Future provider execution requires a new explicit exact operation/review; an old issue, release, credential, CI run, artifact, or successful rollout is never standing authorization.
- A durable verified child remains durable across later phases unless exact identity/postcondition evidence proves it changed; transient or incomplete provider projection alone must not erase prior success.

## YouTube / Legendary Poet / «Чёрный человек»

Repository/local implementation is hardened and current:

- final album timing/render/package paths require exact accepted quality-master provenance for new current-policy artifacts;
- stale/tampered quality masters fail closed;
- canonical YouTube project identity is `project_key + OAuth alias + channel_id` and must be proved before credentials are relied on;
- description authoring is source-first and unresolved media-derived chapters fail closed;
- same-media upload planning uses stable project/channel/media identity; timestamps or metadata changes cannot create a new journal namespace;
- current `main` includes the guarded YouTube release executor completed by Issue #232 / PR #271: read-only existing-target adoption, immutable provider-inert release planning, separate exact execution approval, durable child-operation state, resumable upload/status reconciliation, metadata/status, thumbnail, fully paginated playlist membership, visibility, top-level comment, manual-only pin evidence, and zero blind mutation retries. Canonical plans remain provider-inert and implementation completion does not itself authorize execution.

The separately authorized historical rollout is complete and remains durable remote-state evidence:

- public video ID `x-puy27S2qs`;
- uploaded media SHA-256 `sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0`;
- processing succeeded and final visibility is `public`;
- custom thumbnail verified present;
- playlist memberships and the top-level comment were verified during the completed rollout;
- exact retrospective/live-state evidence remains in [`black-man-youtube-release-retrospective-2026-08-09.md`](black-man-youtube-release-retrospective-2026-08-09.md) and [`black-man-youtube-live-state-2026-08-09.json`](black-man-youtube-live-state-2026-08-09.json).

Issue #154 is closed as **completed**. The published historical MP4 predates the later quality-master binding rule, but that provenance gap is retained as historical evidence only and is not required rework. Do not regenerate or reupload the album solely to satisfy a policy introduced after those bytes were produced.

The known public target `x-puy27S2qs` remains an external collision guard for the stable project/channel/media identity. Absence of a local journal must never be interpreted as permission to create another `videos.insert` for the same media.

No future YouTube upload, metadata edit, thumbnail change, playlist mutation, visibility change, comment mutation, deletion or replacement is authorized by this state.

## Telegram / Lordchrist legacy quote publisher

The legacy `@lordchrist` quote publisher remains a live Telegram publishing track.

Durable reviewed state includes verified publications `1470`, `1472`, `1473`, and `1474`; later reviewed queue items remain governed by the strict durable ledger.

Safety properties include lossless single-writer serialization, exact-current-main/CI gates around provider access, durable intent-before-send, zero blind mutation retry, archived exact provider outcome before final state persistence, evidence-bound recovery, publication-time-correct reconciliation, and reciprocal cross-track blocking for unresolved provider effects.

The historical research-v2 canary ambiguity is no longer a legacy blocker. Issue #286 / PR #287 introduced an exact `retired_no_replay` certificate contract, and durable retirement evidence now exists on `state/lordchrist-telegram` at `content/telegram/lordchrist/research-v2/retirement.json`. Only that exact certificate may suppress its matching historical research blocker; every other `dispatching` or `may_exist` effect remains fail-closed.

Do not modify the legacy live path merely to activate another content class.

## Telegram / Lordchrist research-v2

The canonical research-v2 evidence queue remains provider-inert outside separately reviewed execution scopes, and the generic Lordchrist profile remains `provider_writes_authorized=false`.

The exact August release `lordchrist-research-live-2026-08` is now **retired and non-resumable**:

- the historical publication `lordchrist-research-three-preachers-numbers` remains honestly recorded in the research ledger as `unknown / provider_effect=may_exist`;
- no Telegram `message_id`, provider receipt, or provider absence was invented;
- bounded read-only recovery did not recover exact message identity;
- durable retirement evidence is `disposition=retired_no_replay`, exact-bound to the historical release, publication, payload, intent, run/attempt, GitHub/workflow SHA, chat and bot identity;
- the retirement certificate permits the healthy legacy writer to ignore only this one historical research blocker;
- the retired August research release itself cannot resume, retry, or authorize a successor;
- any later research release, changed schedule, changed target, or new research provider mutation requires a new exact owning issue and separate authorization.

Issue #168 is closed as repository implementation complete. Issue #242 is historical authorization for the retired exact August release only and is not standing authorization.

## Telegram / Svodka

`@deep_info_life` has a separate generic multi-channel implementation, target binding, reviewed-content tooling, durable state model, provider-outcome recovery and deployment/catch-up safety regressions.

The exact August rollout remains owned by Issue #235 and current durable state, not by a static snapshot in this document:

- `content/telegram/channels/svodka.json` has `provider_writes_authorized=true` only for the reviewed rollout gates; this is not standing broad Telegram authority;
- immutable approval `content/telegram/svodka/release-approval-2026-08.json` binds release `svodka-pilot-2026-08`;
- pinned target is chat `-1003527567039` with bot `8716602202 / @preaching_mp3_bot`;
- the durable ledger now exists on `state/svodka-telegram`;
- mutable provider outcome truth must be read from the current durable state branch and Issue #235 at operation start; this document is not a substitute for either.

Issue #170 is closed as repository pipeline implementation complete. No later or broader Svodka rollout is authorized by the August approval.

## Telegram runtime / supply chain

The minimal Telegram runtime is exact-version and SHA-256 hash locked with pip `--require-hashes`; production/minimal installs keep the hash-locked transaction isolated from test-only dependencies. CI validates the installed graph, guarded provider-free CLI surface, dependency audit, Python quality matrices and PowerShell operator environments.

`requirements/telegram-publisher.in` is the small root-constraint source for this production runtime; `requirements/telegram-publisher.txt` is one exact resolved/hash-bound closure. Any lock refresh is one explicit coherent supply-chain change that regenerates the whole exact closure and must pass isolated Python 3.11 install, `pip check`, guarded CLI smoke and dependency audit before acceptance.

One durable state/concurrency namespace has one write owner at a time. Parallel agents must not open competing hardening/mutation branches against shared Telegram runtime/state writers.

## VK

The completed Lord God postponed-text cleanup is historical verified evidence only. Supported reusable VK capability remains the guarded attachment-free postponed wall text-edit contract with exact project/community/owner/post binding, durable intent, no blind replay and exact postflight.

The reusable architecture target for future native-Clip projects is [`vk-native-clip-golden-path.md`](vk-native-clip-golden-path.md). It combines the useful Legendary Poet operational lineage with the stronger identity/replay/temporal rules learned under Milovi. It is an architecture contract, not provider-write authority and not a reason to refactor an in-progress live rollout underneath its durable state.

### Milovi Cake / Issue #323

Issue #323 is a separate exact live rollout scope and remains **open**. Repository recovery/finalizer hardening may be merged while live 12/12 completion is still unproved. Read Issue #323 and its durable journal/provider state at operation start.

Current retained safety interpretation through PR #359 once merged:

- wall `-68859909_475` cleanup has one destructive owner only: `milovi_issue323_anomaly_reconcile.py` phase 1; the finalizer has no delete authority for that post;
- wall-475 phase 1 persists `delete_dispatch_started` before its one provider delete. A restart from historical `delete_intent`, dispatch-started or unknown state may reconcile exact absence/tombstone but never blindly delete again; once cleanup is durably `verified_absent`, automatic re-delete authority is consumed even if a live object later reappears;
- latest recorded live evidence still accepts wall 475 only as exact absence/deleted-tombstone evidence and preserves exact eighth Clip `-68859909_456239232`; this checkpoint is not standing proof of later provider state;
- already-dispatched recovery cannot reserve or retransmit the binary; recovery capability is narrower than fresh upload capability;
- strict readiness remains required for a new/resumed upload. An already-created exact native Clip may cross child completion only with one of two reviewed description states: exact legacy copy or exact promoted copy. A source URL/marker by itself is no longer sufficient overwrite or child-completion authority;
- the fresh continuation after PR #352 established source 9's exact native Clip `-68859909_456239233` and then exposed an impossible phase prerequisite. PR #355 removed that child/promotion ordering deadlock without granting recovery metadata-write authority;
- final provider success still requires exact promoted Clip descriptions and wall messages. Legacy copy is accepted only as a pre-promotion state, never as final completion;
- before the first promotion edit, one read-only batch preflight proves all 12 durable mappings, exact current wall incarnations and exact legacy/promoted copy states. A deterministic conflict on a later item therefore blocks before partial promotion of earlier items;
- promotion `video.edit` and successor-aware `wall.edit` persist exact intent plus a durable `dispatch_started` barrier before the single mutation, re-read the exact target immediately before dispatch, reconcile a lost response only from exact target-state readback, and forbid blind replay when dispatch may already have occurred;
- promotion target identity does not grant overwrite authority. `video.edit` may start only from exact reviewed legacy description; `wall.edit` may start only from exact reviewed legacy wall message. Any third text state blocks even when owner/date/Clip/source marker still look correct;
- all local VK writers sharing a lock directory now converge on one canonical mutex per `community_id`; operation-specific filenames cannot allow rollout, resume, anomaly reconciliation or finalizer processes to mutate the same community concurrently;
- the logical scheduled wall mapping is durable, but a VK postponed timer `post_id` is not assumed durable across publication. Before its frozen slot, the journaled postponed ID must remain exact; after the slot, the current incarnation may be the old ID or one uniquely proven published successor;
- unresolved `wall_intent` / `wall_may_exist` recovery is also time-aware: a uniquely bound published incarnation may be adopted after the frozen slot without replay, while publication before the slot, wrong date, duplicate mapping or multiple video attachments block;
- aggregate omission is contextual evidence, not exact-object disappearance proof when a durable exact ID exists. Exact readback governs that object's live/tombstone state; complete aggregate snapshots still govern drift and historical-SHA reconstruction;
- source 9–12 upload-side-effect cleanup remains one narrow exact `wall.delete` boundary only when the durable upload delta, exact reserved Clip, capture window, exact current candidate and exact historical pre-upload SHA all prove the one side effect. It does not authorize source 8/wall 475 cleanup, broad cleanup or upload replay;
- recovery, metadata maintenance, ambiguous edit reconciliation and final postflight share the same logical source/Clip/frozen-slot/current-incarnation model;
- mutation governance is callsite-aware: the inventory binds provider marker + source file + callable, so a second direct `wall.delete`, `wall.edit`, `video.edit` or `wall.post` cannot disappear behind a method-name set entry;
- Issue #323 is complete only after fresh live readback proves all 12 exact Clip mappings, all 12 logical scheduled wall mappings with legitimate current provider incarnations, authorized internal Milovi public copy with no YouTube public links, and a clean final provider postflight.

Canonical incident analysis: [`2026-08-14-milovi-issue-323-interim-postmortem.md`](2026-08-14-milovi-issue-323-interim-postmortem.md).

Historical browser/internal-web VK Audio executors and ZIP families remain retired/experimental evidence and are not current execution surfaces.

## Local MP3

Supported capability remains `local_only_read_only_intake_and_manifest`: inspect/probe/hash/tag inventory, deterministic manifests, explicit metadata policy and conflict classification.

It does not authorize ID3 rewrite, rename/transcode, browser automation, remote upload, metadata mutation, playlist changes, or wall publication.

## Local video / Resi DASH

Supported local-only capability is `video-manager resi handoff` (with `video-manager-resi` retained as a focused alias) for ordinary HTTP(S) DASH `Manifest.mpd` sources.

It uses structured format evidence, deterministic source receipts, SHA-256 and ffprobe QC, source-aware exact trimming, NVENC detection / CPU fallback, and user-facing outputs under canonical `operator-output`.

This capability has provider effect `impossible`. It does not bypass DRM/access controls, infer rights/permission, upload media, or authorize any provider mutation. The canonical runbook is [`resi-dash-local-handoff.md`](resi-dash-local-handoff.md).

## GitHub governance and external state

Read-only governance evidence is recorded in [`github-governance-readonly-probe-2026-08-09.md`](github-governance-readonly-probe-2026-08-09.md).

At those probe points:

- `GET /branches/main` returned HTTP 200 with `protected=false`;
- `GET /rulesets` returned HTTP 200 with repository ruleset count `0`;
- Dependency Graph itself is policy-enabled for this public repository;
- GitHub SBOM REST export is verified unavailable through both documented generation surfaces at the probe points;
- this is a scoped observed REST status, not a blanket `UNVERIFIED` item and not permanent truth.

A fresh read before PR #359 work again observed `main` as unprotected. `.github/CODEOWNERS` remains repository policy only; it must not be presented as branch protection. Green CI likewise does not create GitHub protection by itself.

Only `main` is a supported repository code/runtime execution baseline. `state/lordchrist-telegram` and `state/svodka-telegram` are durable state-only refs and must never be used as runtime/code sources. Any other branch is ephemeral and non-authoritative after its scope closes; delete it where supported or align the ref to exact current `main` after preserving any genuinely unique useful work through a focused PR.

Dependabot version-update work is a separate maintenance queue, not unresolved production state. The production Telegram hash lock is not a routine bot target. Every accepted maintenance change still requires exact-current-main CI.

## Provider/credential boundary

Credentials authenticate/select configuration; they do not choose the project target.

Canonical project identity, exact provider IDs, immutable release/plan, durable state and explicit execution authority select the operation. Never print, commit, package, log, or put provider credentials on a command line.

Unknown provider outcomes remain blocking until read-only reconciliation **unless** a narrowly scoped current-main contract recognizes an exact durable terminal disposition such as the Lordchrist `retired_no_replay` certificate. Such a disposition never becomes a provider receipt, never proves absence, and never grants replay or successor authority.

## Next safe work

1. Treat Issue #232 / PR #271 as repository implementation complete only: no future YouTube provider mutation is authorized without a new exact execution approval.
2. Treat Lordchrist P0 / Issue #286 as closed: the exact historical research ambiguity is retired for legacy cross-track purposes, while the retired research release itself remains no-replay and no-successor.
3. Keep Svodka inside Issue #235's current exact scope and read its durable state at operation start; do not infer live rollout status from this document.
4. For Milovi #323, merge only an exact-current-main green hardening head; then read fresh durable/provider state before continuation. Do not infer 12/12 completion from PR #359, this document or historical checkpoints.
5. After exact live #323 completion, extract the shared native-Clip kernel behind compatibility tests according to `vk-native-clip-golden-path.md`; do not refactor the in-progress durable rollout merely for architectural cleanup.
6. Treat production Telegram lock refreshes as explicit coherent supply-chain changes; routine bot maintenance must not edit that closure piecemeal.
7. Treat GitHub governance evidence as observed state, not permanent truth: future changes require fresh read-only verification rather than assumptions.

Nothing in this document is authorization for a provider mutation.
