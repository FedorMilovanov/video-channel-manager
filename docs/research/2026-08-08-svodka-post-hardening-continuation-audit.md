# Svodka post-hardening continuation audit — 2026-08-08

This is an immutable successor record. It does not rewrite or supersede the historical evidence in earlier Svodka audit files; it records the repository state after the later recovery, authorization, state-writer, workflow-retirement and runner-pinning waves.

## Audited repository point

- repository: `FedorMilovanov/video-channel-manager`
- audited `main`: `71fbaaac132c1bd337d915a02a2a20f7f987629f`
- channel project: `svodka`
- Telegram channel: `@deep_info_life`
- state branch: `state/svodka-telegram`
- shared writer concurrency group: `svodka-telegram-publisher`

This record was created after exact-head full CI succeeded for PR #203 and the PR was squash-merged into the audited `main`.

## Current live safety baseline

Svodka remains fail-closed and provider-inert at this audit point:

1. `content/telegram/channels/svodka.json` has `provider_writes_authorized=false`.
2. `content/telegram/svodka/approved-release-2026-08.json` is absent from `main`.
3. `content/telegram/svodka/publication-ledger.json` is absent from `state/svodka-telegram`.

Therefore the installed canary/scheduler workflows do not have the complete set of prerequisites required for a Telegram provider mutation.

## Hardening waves now present in main

### Exact provider-outcome durability

PR #193 introduced run/attempt-scoped archival of the exact structured Telegram provider outcome after `send-once` and before durable state persistence. A provider-free recovery workflow can reconstruct an already-observed outcome after a later state push failure without retrying Telegram.

The recovery path is intentionally independent from later unrelated `Svodka quality` drift after the provider effect. Pre-provider writers require exact-current-main quality; post-effect recovery instead proves exact source run/attempt/workflow/head, durable dispatch, artifact provenance and provider outcome.

### Single authorization semantics

PR #195 collapsed the Svodka compatibility authorization helper onto the generic exact review gate. An authorized Svodka release requires the current profile, exact current target binding and exact expected reviewed candidate digest; test fixtures no longer legitimize a weaker authorization path.

### Artifact byte integrity and credential boundary

PR #196 strengthened archived-outcome recovery so state mutation is bound to the actual downloaded artifact bytes rather than only GitHub artifact metadata. Recovery verifies the proved artifact id, byte size and SHA-256, requires a single safe outcome JSON member and validates the exact `GenericProviderOutcome` before applying it.

The authenticated GitHub API request does not forward `Authorization` to the temporary external artifact-storage URL. The redirect is handled as a credential boundary and the storage request is credential-free.

### Exact workflow-attempt recovery

PR #198 changed skipped-send reconciliation to use run metadata and jobs from the same exact GitHub Actions attempt. An accidental later Re-run therefore cannot make the older persisted intent unrecoverable merely because the generic run endpoint now describes a newer attempt.

### Low-level ledger authorization

PR #199 moved the immutable-release authorization invariant into the low-level generic `initialize_ledger()` helper itself. The library entry point is no longer weaker than the CLI/workflow boundary.

### Lossless state-writer serialization and stale-runtime rejection

PR #200 applies the same explicit state-writer concurrency contract to the complete Svodka state-writing surface:

- `group: svodka-telegram-publisher`;
- `cancel-in-progress: false`;
- `queue: max`;
- `runs-on: ubuntu-24.04`.

The covered writers are ledger initialization, stale-window skipping, manual canary, scheduled publishing, skipped-send reconciliation and archived-provider-outcome reconciliation.

Because `queue: max` may preserve an older pending workflow until after `main` advances, archived-outcome recovery separately proves `origin/main == $GITHUB_SHA` immediately before its durable state commit. Other state writers already use the exact-current-main quality gate before durable mutation.

### Obsolete self-mutating migrations retired

PR #202 removed four residual one-time Svodka migration executors:

- `svodka-consolidate-once.yml`;
- `svodka-editorial-source-hardening-once.yml`;
- `svodka-rebind-stable-profile-once.yml`;
- `svodka-runtime-quality-once.yml`.

Those files were `push`-triggered, had `contents: write`, modified canonical repository state and pushed directly back to `main`. Their intended migration state was already present. The retirement merge used a `[skip ci]` commit and the resulting main commit produced no workflow runs, preventing the removed path-triggered executors from starting on their own deletion commit.

A regression now forbids both residual `svodka-*-once.yml` files and Svodka workflows that combine a `push` trigger with `contents: write`.

### Permanent Svodka runner pin

PR #203 pinned the two remaining permanent workflows — `svodka-quality.yml` and `svodka-telegram-preflight.yml` — to `ubuntu-24.04`. The six state writers were already pinned by PR #200.

A regression scans every current and future `.github/workflows/svodka-*.yml`, requires every `runs-on:` entry to be `ubuntu-24.04` and rejects `ubuntu-latest` anywhere in a Svodka workflow.

Exact PR #203 head `dfbd8d57dbce0a3373456f6e678823e255a2e2b0` passed full repository CI run #3726 / `31277327848` across Python 3.11, 3.12 and 3.13 plus Windows PowerShell 5.1, Windows PowerShell 7 and Linux PowerShell 7 before merge.

## Incident recovery matrix

The two recovery workflows solve different failure classes and must not be substituted for each other.

### A. Durable intent exists and provider send is proven skipped

Use `Svodka reconcile skipped provider send` only when the exact completed source workflow attempt proves:

- the expected workflow/event/head SHA;
- durable dispatch intent persistence succeeded;
- the provider send step was `skipped`;
- no provider mutation can therefore have occurred in that attempt.

Only then may reconciliation record `confirmed_absent` and restore the item to a safe retryable state.

### B. Provider send completed and exact archived provider outcome exists

Use archived-provider-outcome recovery when the source attempt passed the provider send and archived its exact structured outcome but final durable state persistence did not succeed.

Recovery is provider-free. It must bind the requested publication and persisted dispatch to the exact run id, run attempt, workflow, event, source head SHA, artifact id, artifact digest/size, downloaded ZIP bytes and structured provider outcome. It must never compensate for uncertainty with a blind Telegram retry.

If neither the exact skipped-send proof nor the exact archived-outcome proof exists, do not guess. A `may_exist` dispatch remains blocking until it is reconciled with sufficient evidence.

## State-machine invariants rechecked

The hardened path retains these safety invariants:

- exact target/profile/release/ledger identity before provider eligibility;
- strict-next ordering;
- verified daily publication limit;
- verified manual canary before scheduled provider activity;
- bounded freshness window;
- durable `dispatching/may_exist` intent before Telegram mutation;
- exact-current-main quality reproof immediately before normal provider mutation;
- zero mutation transport retries;
- ambiguous post-mutation transport/provider drift remains `may_exist` and is not retryable;
- exact structured provider outcome archived before normal final state persistence;
- state writers serialized through one shared lossless queue.

## Documentation drift found at this audit point

`docs/operations/svodka-readiness.md` still reflects an earlier implementation in two material places:

1. it documents skipped-send reconciliation but not the later archived-provider-outcome recovery path;
2. its library-level defense note still says `initialize_ledger()` lacks its own authorization check, which became false after PR #199.

The operational runbook must be synchronized before activation. This successor audit records the discrepancy so the historical record does not silently inherit the stale statement.

## Supply-chain status

`requirements/telegram-publisher.txt` is a complete exact-version pinned minimal runtime closure and production installation already uses `--only-binary=:all:`. The lock currently has no package hashes and installation does not yet use `--require-hashes`.

Before calling supply-chain reproducibility complete, create a complete hash-checked production lock for every artifact accepted by the pinned Ubuntu 24.04 / Python 3.11 Telegram runtime and make every production/minimal-runtime install fail closed with `--require-hashes`. Do not introduce a partial hash set: hash-checking must be complete for the dependency closure used by that runtime.

## Repository governance status

The available GitHub connector did not expose branch-protection/ruleset administration, so this audit does not claim that repository-side protection is enabled. No `CODEOWNERS` file was found by repository code search at this point.

External repository controls therefore remain to be independently verified/configured:

- protect `main` against force-push and deletion;
- require the intended CI/review policy for changes to critical production paths;
- protect state branches against force-push/deletion while still allowing the publisher's normal fast-forward state writes;
- decide whether critical Telegram/runtime/workflow paths should have explicit CODEOWNERS review ownership.

These are governance controls, not substitutes for the fail-closed runtime invariants above.

## Activation remains out of scope for this record

Do not activate Svodka merely because hardening is green. Activation still requires a separate exact-current-main production sequence: successful `Svodka quality`, fresh read-only target preflight, review of the exact 14-item candidate, exact immutable release authorization, explicit write-gate change, fresh quality on the activation SHA, one-time ledger initialization, strict-next manual canary and verified durable receipt before scheduled publishing becomes eligible.
