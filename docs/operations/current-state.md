# Current operational state

Updated: 2026-08-09

This file is the concise current operational interpretation. It does **not** authorize provider mutation. Historical audits/PRs/issues are evidence only.

For every new task, resolve the exact current `main` commit and relevant durable state at task start; do not treat a SHA written in an old document as the live baseline.

Latest repository/local control continuation: [`control-audit-continuation-2026-08-09.md`](control-audit-continuation-2026-08-09.md).

## Current closure model

Repository implementation, final artifact production, and live provider rollout are separate completion states.

- Repository code may be complete while live rollout remains intentionally unauthorized.
- A media/artifact issue is not complete until the exact current-policy bytes are regenerated and verified.
- Future provider execution requires a new explicit exact operation/review; an old issue, release, credential, CI run, or artifact is never standing authorization.

## YouTube / Legendary Poet / «Чёрный человек»

Repository/local implementation is hardened and current:

- final album timing/render/package paths require exact accepted quality-master provenance;
- stale/tampered quality masters fail closed;
- canonical YouTube project identity is `project_key + OAuth alias + channel_id` and must be proved before credentials are relied on;
- description authoring is source-first and unresolved media-derived chapters fail closed;
- exact chapters can be rendered only from a digest-valid album package and produce immutable evidence bound to body/package/media/timing/quality-master hashes;
- same-media upload planning uses stable project/channel/media identity; timestamps or metadata changes cannot create a new journal namespace;
- merged YouTube upload tooling is provider-inert (`plan/status/abandon` only). There is no provider upload executor in the supported baseline.

Issue #154 remains **artifact-level open** for one reason: the previously rendered album MP4 predates the quality-master binding fix. Completion requires regeneration from the seven accepted exact masters under the current pipeline, then fresh timing/render/verify/package/description evidence (SHA-256 + required ffprobe/QC). Do not reuse the historical MP4 as current-policy proof.

No YouTube upload, metadata edit, thumbnail change, playlist creation/membership change, visibility change, or deletion is authorized by this state.

## Telegram / Lordchrist legacy quote publisher

The legacy `@lordchrist` quote publisher is the only live Telegram publishing track represented here.

Durable reviewed state currently includes verified publications `1470`, `1472`, and `1473`; later reviewed queue items were pending with `provider_effect=impossible` at the latest control audit, with no reviewed unresolved `may_exist` entry.

Safety properties include lossless single-writer serialization, exact-current-main/CI gates around provider access, durable intent-before-send, zero blind mutation retry, archived exact provider outcome before final state persistence, evidence-bound recovery, and publication-time-correct reconciliation.

Do not modify the legacy live path merely to activate another content class.

## Telegram / Lordchrist research-v2

Research-v2 repository implementation is complete as a **provider-inert content/release track**:

- claim/source/evidence validation is separate from provider execution;
- immutable evidence identity is separate from mutable activation state;
- exact target-bound release review/approval is provider-inert;
- generic Lordchrist profile remains `provider_writes_authorized=false`;
- no research sender/scheduler is activated by this state.

Issue #168 should be treated as repository-hardening/content-model completion, not standing authorization for a live research canary. Any future live research publication must start from a new explicit execution scope proving exact release, isolated durable state, current provider identity, intent-before-send, zero blind retries, exact receipt/postcondition, and strict-next scheduling.

## Telegram / Svodka

`@deep_info_life` has a separate generic multi-channel implementation, target binding, reviewed-content tooling, durable state model, provider-outcome recovery and deployment/catch-up safety regressions.

Current activation state remains fail-closed:

- `content/telegram/channels/svodka.json` has `provider_writes_authorized=false`;
- pinned target is chat `-1003527567039` with bot `8716602202 / @preaching_mp3_bot`;
- no approved live August release is present at the latest control point;
- no live Svodka publication ledger is present at the latest control point;
- no Svodka provider mutation or scheduled production is authorized by this state.

Issue #170 should be treated as repository pipeline implementation completion. A future canary or scheduled pilot is a separate live rollout decision and requires a new explicit exact provider scope rather than reopening generic implementation work.

## Telegram runtime / supply chain

The minimal Telegram runtime is exact-version and SHA-256 hash locked with pip `--require-hashes`; production/minimal installs keep the hash-locked transaction isolated from test-only dependencies. CI validates the installed graph, guarded provider-free CLI surface, dependency audit, Python quality matrices and PowerShell operator environments.

One durable state/concurrency namespace has one write owner at a time. Parallel agents must not open competing hardening/mutation branches against shared Telegram runtime/state writers.

## VK

The completed Lord God postponed-text cleanup is historical verified evidence only. Supported reusable VK capability remains the guarded attachment-free postponed wall text-edit contract with exact project/community/owner/post binding, durable intent, no blind replay and exact postflight.

Historical browser/internal-web VK Audio executors and ZIP families remain retired/experimental evidence and are not current execution surfaces.

## Local MP3

Supported capability remains `local_only_read_only_intake_and_manifest`: inspect/probe/hash/tag inventory, deterministic manifests, explicit metadata policy and conflict classification.

It does not authorize ID3 rewrite, rename/transcode, browser automation, remote upload, metadata mutation, playlist changes, or wall publication.

## GitHub governance and external state

`.github/CODEOWNERS` exists for critical repository paths, but effective branch protection/rulesets and the current Dependency Graph setting are external GitHub state and remain **UNVERIFIED** through the available connector. Green CI or CODEOWNERS presence must not be presented as proof of those settings.

Open Dependabot version-update PRs are a separate maintenance queue, not unresolved production state. Major dependency/action changes require independent compatibility review and exact-current-main CI; they are not bulk-merged to make the queue look empty.

## Provider/credential boundary

Credentials authenticate/select configuration; they do not choose the project target.

Canonical project identity, exact provider IDs, immutable release/plan, durable state and explicit execution authority select the operation. Never print, commit, package, log, or put provider credentials on a command line.

Unknown provider outcomes remain blocking until read-only reconciliation. A timeout, HTTP success, screenshot, stdout, filename, CI result, approval artifact, or visible UI state is not a provider postcondition.

## Next safe work

1. For #154, regenerate/verify the final seven-master Black Man artifact only when the exact accepted master bytes are available to the executing environment.
2. Keep Lordchrist research-v2 and Svodka provider-inert unless a new explicit live execution request is created and reviewed.
3. Treat Dependabot updates as bounded maintenance, not operational closure debt.
4. Keep effective GitHub protection/Dependency Graph status `UNVERIFIED` until independently observable.

Nothing in this document is authorization for a provider mutation.
