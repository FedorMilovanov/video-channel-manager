# Current operational state
Updated: 2026-08-19

This file is the concise current operational interpretation. It does **not** authorize provider mutation. Historical issues, comments, pull requests, CI runs, credentials and old release receipts are evidence only; they are never standing execution authority.

For every new task, resolve the exact current `main` commit and the relevant durable state at task start. Do not treat a SHA, issue body, checkpoint comment or workflow from an older phase as the live baseline when newer terminal evidence exists.

## Completion and authority model

Repository implementation, produced artifacts and live provider outcomes are separate completion states.

- A durable verified provider outcome is not reopened merely because a stricter policy or later architecture exists.
- An old successful rollout does not authorize a new mutation.
- An ambiguous provider effect remains blocking unless exact read-only reconciliation or a narrowly bound terminal no-replay disposition resolves it.
- Credentials authenticate; exact project identity, target binding, immutable operation/release identity, durable state and fresh explicit execution authority select the operation.
- No blind provider retry is authorized anywhere by this document.

## Repository source of truth

- `main` is the only supported source/runtime baseline.
- `state/lordchrist-telegram`, `state/svodka-telegram` and `state/milovi-cake-telegram` are durable state-only refs. They must not be used as runtime/code baselines.
- Ephemeral `work/`, `agent/` and `research/` refs are non-authoritative after their scope closes. Preserve unique useful commits before cleanup; never rewrite a durable state ref as branch hygiene.
- Current source `main` is still observed as unprotected at the repository level. `.github/CODEOWNERS` and green CI are policy/evidence, not branch protection.

## YouTube / Legendary Poet / «Чёрный человек»

The historical authorized rollout is complete. Public video `x-puy27S2qs` remains the collision guard for that exact project/channel/media identity. Processing, public visibility, custom thumbnail, playlist membership and the top-level comment were verified during the completed rollout.

Issue #154 is closed as **completed**. The historical provenance gap predates the later quality-master binding rule and is not required rework. Do not regenerate or reupload the album merely to satisfy policy introduced after the published bytes were produced. No future YouTube upload, metadata edit, thumbnail change, playlist mutation, visibility change, comment mutation, deletion or replacement is authorized by this state.

## Telegram / LordChrist

The legacy `@lordchrist` quote publisher remains a separate live content track with its own durable ledger and no-blind-retry contract.

The exact historical research-v2 August release is retired and non-resumable. Its matching `retired_no_replay` certificate may suppress only that exact historical blocker; it does not prove provider absence and does not authorize replay or a successor.

The first rich successor publication is complete:

- publication: `lordchrist-rich-sermons-survive-century` — «Перо, стенографист и магнитная лента»;
- Telegram message: `1484`;
- durable state: `published / provider_effect=verified`;
- provider method: exactly one `sendRichMessage`;
- returned rich structure: exact;
- media verification: exact for all three reviewed documentary images;
- no retry, `sendMessage` fallback, edit, delete or pin occurred.

Issue #473 is closed as completed. The second reviewed rich article remains provider-inert. The completed one-shot rich live canary/controller workflows have been retired from executable `main`; durable evidence and reusable runtime/source remain preserved.

Any future LordChrist rich publication requires a new exact owning scope and fresh provider authorization.

## Telegram / Svodka

Issue #235 is closed as completed. The finished successor path has two durable verified publications:

- `svodka-rich-goldfish-three-second-memory-myth` — Telegram message `28`, verified by provider-free reconciliation of the archived HTTP-200 exact-target/exact-media response; no replay occurred;
- `svodka-rich-wombat-cubic-poop` — fresh v4 successor, `dispatch_mode=scheduled`, Telegram message `29`, `published / provider_effect=verified`, `error=null`.

The intervening v3 wombat identity ended `failed_no_effect / confirmed_absent` with no message id after Telegram could not fetch its original remote image. That attempt is immutable and was not retried under the same release identity.

Historical messages `26` and `27` and expired v2/v3 mutation identities remain non-replayable evidence. The old August schedule is not a catch-up queue.

The completed message-28 reconciliation workflow and the verified v4 successor workflow have been retired from executable `main`. Historical release/runtime/evidence and legacy provider-free/recovery contracts remain where required for reproducibility. Do not delete or rewrite those historical contracts merely to make the workflow inventory smaller.

No new Svodka Telegram mutation is authorized by this state.

## VK / Milovi Cake / Issue #323

Issue #323 is closed. The marathon closure accepted the exact 12 allowlisted Milovi Cake sources as completed native VK Clip uploads with their base durable logical wall mappings; all 12 reached durable rollout completion rather than the older 8/12 checkpoint.

Older Issue #323 body text and comments that say `OPEN`, `8/12`, source 9 `upload_in_progress`, or sources 10–12 `pending` are historical fail-closed checkpoints from before the later completion and must not be used as current authority.

The durable safety lessons remain current:

- a verified exact Clip identity is not duplicate-uploaded because of later transient provider projection;
- postponed wall provider IDs are incarnation-local across a proven due publication transition; logical source/Clip/frozen-slot identity is durable;
- aggregate omission is not exact disappearance proof when an exact durable ID can be read directly;
- wall `-68859909_475` one-time destructive cleanup authority is consumed and must never be replayed automatically;
- ambiguous provider responses require exact reconciliation before any retry decision;
- the retired legacy Issue #323 finalizer must not return as a second mutation authority;
- the historical STOP replay corpus remains a permanent provider-inert regression suite.

Later optional promotion/metadata/finalizer work must not be reinterpreted as “missing Clip uploads.” Any new VK metadata edit, promotion change, upload, delete or wall mutation requires a new exact scope, fresh target/provider evidence and separate execution authority.

Canonical historical analysis remains [`2026-08-14-milovi-issue-323-interim-postmortem.md`](2026-08-14-milovi-issue-323-interim-postmortem.md). The reusable architecture target remains [`vk-native-clip-golden-path.md`](vk-native-clip-golden-path.md).

## Telegram / Milovi Cake / Issue #353

Issue #353 is a separate Milovi Telegram workstream and remains outside this audit/cleanup scope. This document does not modify it and does not grant or revoke any provider authority for it. Read its current issue/state evidence directly when that workstream is handled.

## Telegram runtime / supply chain

The minimal Telegram runtime remains exact-version and SHA-256 hash locked with pip `--require-hashes`. Production/minimal installs keep the hash-locked transaction isolated from test-only dependencies. Any lock refresh is one explicit coherent supply-chain change and must pass the isolated install, `pip check`, guarded provider-free CLI smoke and dependency audit before acceptance.

One durable state/concurrency namespace has one write owner at a time. Parallel agents must not create competing provider writers against the same state namespace.

## Local MP3 and Resi DASH

Supported Local MP3 capability remains `local_only_read_only_intake_and_manifest`: inspect, probe, hash, tag inventory and deterministic manifests. It does not authorize ID3 rewrite, rename/transcode, remote upload, metadata mutation, playlist changes or wall publication.

Resi remains the repository-owned local three-stage flow: `watch` -> `sample` -> explicit `handoff`. The watcher never auto-dispatches a multi-gigabyte FULL download; language-sensitive work samples sermon speech before full handoff. This capability has provider effect `impossible` and does not bypass DRM/access controls or infer rights/permission. Canonical runbooks remain [`resi-dash-local-handoff.md`](resi-dash-local-handoff.md) and [`resi-grace-russian-live.md`](resi-grace-russian-live.md).

## GitHub governance

The latest read-only repository observation still reports source `main` as `protected=false`; repository policy files and green checks do not create branch protection by themselves. Issue #443 was closed `not_planned` because the connected mutation surface did not provide the required repository-admin branch-protection/ruleset operation. Re-check live GitHub governance before making any future claim that protection has changed.

## Next safe work

1. Do not reopen completed Svodka, LordChrist rich canary or Milovi Clips work because an older issue body or checkpoint says it was incomplete.
2. Keep Milovi Telegram #353 separate from this audit/cleanup workstream.
3. Continue branch hygiene only with exact unique-commit/PR-state proof; preserve all durable `state/*` refs.
4. For any new provider-visible work, start with fresh current `main`, fresh durable state, exact target identity and a new explicit owning scope.

Nothing in this document is authorization for a provider mutation.
