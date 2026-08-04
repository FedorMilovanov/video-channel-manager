# Operational automation backlog

Updated: 2026-08-04

This backlog is subordinate to [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md) and the machine-readable [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json). It must not re-activate retracted findings, retired executors, or completed destructive operations.

## Active tracking

- #31 — reconcile the 26-item long-form upload result and ledger;
- #32 — inventory the real VK Clips surface and classify the Shorts queue;
- #33 — organize and publish the verified VK catalog after dependencies;
- #36 — active Wave 4 upload/wall firewall and postponed publishing;
- #37 — exact approved Shorts wall-cleanup scope;
- #38 — VK Shorts upload modes and final type/player behavior;
- #64 — master reliability roadmap;
- #65/#66 — completed Wave 1 issue and implementation;
- #67/#68 — completed Wave 2 issue and implementation;
- #69/#70 — completed Wave 3 issue and implementation.

Issue #33 remains blocked until #31, #32/#38, and #36 have no silent unknown outcomes. Waves 1–3 prevent blind reservation/upload retries, project-identity bypass, and transport-level mutation retry, but live queue continuation remains blocked until exact historical journal reconciliation.

## Wave 0 — canonical state

- [x] Add the master reliability audit and wave roadmap.
- [x] Add a machine-readable finding register with status, severity, owner issue, and wave.
- [x] Update `current-state.md` with verified repository and operational state.
- [x] Link the operations index to the sources of truth.
- [x] Expand issue #64 with the Waves 0–10 roadmap.
- [x] Append the project-memory changelog.
- [x] Close superseded draft PR #29 after preserving reusable recovery lessons.
- [x] Update root `AGENTS.md` to require the master audit/register before work.

Wave 0 is complete. It performed no provider writes.

## Wave 1 — upload state machine and recovery

Completed by PR #66, merge `56da03247f60ec9d25f1646fb9ccdfbb651aff9c`.

- [x] Persist reservation intent before `video.save`.
- [x] Persist a separate dispatch marker.
- [x] Persist exact upload ticket immediately after reservation.
- [x] Add explicit `unknown_requires_reconciliation` behavior.
- [x] Require verified stage or full exact reconciliation before reuse.
- [x] Define identity/title/duration/type/processing/playability readiness.
- [x] Add crash fault-injection after every state boundary.
- [x] Prove verified replay is a no-op and ambiguous boundaries cannot replay provider mutation.
- [x] Migrate legacy upload records fail closed.
- [x] Pass exact-head CI on Python 3.11, 3.12, and 3.13.

Wave 1 is complete. It performed no VK or YouTube writes.

## Wave 2 — fail-closed content and project pipeline

Completed by PR #68, merge `19c2671bf91c8376def527a592e0bb7674841d03`, exact-head CI run `30867659234`.

- [x] Remove implicit project defaults from reusable canonical/legacy parsing.
- [x] Require every record and batch to resolve to one registered project.
- [x] Add expected project/channel validation before preview and plan rendering.
- [x] Reject mixed-project batches.
- [x] Bind plan schema v2 operations and digests to `project_key`.
- [x] Require complete bidirectional targets↔operations coverage.
- [x] Make base sync internal-only with immutable `SyncRuntime`.
- [x] Keep exactly one supported dependency-injected sync entrypoint.
- [x] Remove production monkeypatching from the supported path.
- [x] Add cross-project and direct-bypass behavioral tests.
- [x] Preserve the Wave 1 lifecycle and no-live-retransmission boundary.
- [x] Pass exact-head CI on Python 3.11, 3.12, and 3.13.

Wave 2 is complete. It performed no VK or YouTube writes.

## Wave 3 — transport, retries, and limiter

Completed by PR #70, merge `995167bdadc90d8d53414570cc3e5010bc4a93f2`, exact-head CI run `30871435907`.

- [x] Inventory every remaining direct `httpx.Client()` construction.
- [x] Classify each lifecycle as owned, borrowed, or intentional one-shot.
- [x] Move `YouTubeCommentWriter` and all reusable paths to explicit ownership.
- [x] Centralize redaction-safe transport, response, and provider-error taxonomy.
- [x] Define explicit `SAFE_READ` versus `AMBIGUOUS_MUTATION` operation classes.
- [x] Add bounded retry/backoff only for classified safe reads.
- [x] Respect bounded valid `Retry-After`; invalid values cannot create unbounded sleep.
- [x] Keep ambiguous mutation attempts single-shot and externally `retryable=false`.
- [x] Cache the YouTube uploads playlist ID for the client lifecycle.
- [x] Add an injectable thread-safe VK limiter with a zero default instead of an invented provider rate.
- [x] Add deterministic fake-clock/fault/redaction/ownership tests and preserve the Wave 1 crash matrix.
- [x] Cover YouTube inventory/comments/descriptions/OAuth and VK inventory/video/thumbnail paths.
- [x] Pass exact-head CI on Python 3.11, 3.12, and 3.13 with zero provider writes.

Wave 3 is complete. It performed no VK or YouTube writes.

## Wave 4 — wall safety subsystem

Tracked by issue #36. This is the active engineering wave.

- [ ] Preserve proven `wallpost=0` in every supported `video.save` path.
- [ ] Do not mandate unverified `auto_publish` or misuse playback `repeat` as wall safety.
- [ ] Require a versioned upload contract with `wall_mutation_authorized=false`.
- [ ] Reject missing/true/coerced/wrong-project wall authorization before config/network.
- [ ] Bind published+postponed before-snapshot identity/digest to upload plans and journals.
- [ ] Add mandatory postflight wall delta verification after any upload request may have reached VK.
- [ ] Treat any unexpected published/postponed create/edit/delete/move as reconciliation-only; never auto-delete.
- [ ] Make postponed publication the only default wall-write path.
- [ ] Require exact project/community/owner/attachment/text/time/guid/plan binding.
- [ ] Scan published and postponed surfaces for duplicate identity and exact/near schedule-slot collisions.
- [ ] Journal wall intent before dispatch and keep lost responses single-shot/unknown.
- [ ] Block immediate publication without a separate immutable reviewed exception.
- [ ] Keep issue #37 cleanup isolated and perform zero live writes during implementation/CI.
- [ ] Pass exact-head CI on Python 3.11, 3.12, and 3.13.

## Wave 5 — Windows/operator contract

- [ ] One Python/version/venv bootstrap.
- [ ] Structured `preflight-summary.json` and `result.json` for wrappers.
- [ ] No mandatory count parsing from human stdout.
- [ ] `$PSScriptRoot` and repository-root discovery instead of user paths.
- [ ] Exact artifact path and digest instead of newest-ZIP selection.
- [ ] Shared PowerShell guard library and correct exit-code tests.
- [ ] Automatically run the bundle verifier before handoff/apply.

## Wave 6 — stable wave engine

- [ ] Data/policy-driven waves over shared interfaces.
- [x] Dependency injection instead of production monkeypatching in the supported YouTube→VK sync path.
- [ ] Remove remaining private cross-script imports.
- [ ] One versioned journal schema with guarded migrations.
- [ ] One canonical text/URL normalizer.
- [ ] Archive retired executors only after reference scans.

## Wave 7 — risk-based tests

- [ ] Module-specific coverage gates for clients, writers, CLI, and executors.
- [ ] Preserve and extend fault matrices for intent, acceptance, lost response, delayed visibility, journal write, and restart.
- [ ] Property tests for idempotency and project isolation.
- [ ] Windows wrapper integration tests.
- [ ] Test-order/repeat stability where useful.

## Wave 8 — matching, catalog, and media correctness

- [ ] Exact reviewed mapping before fuzzy fallback.
- [ ] Globally consistent pair matching instead of order-sensitive greediness.
- [ ] Duplicate normalized album names become explicit conflicts.
- [ ] Semantic membership comparison ignores position churn.
- [ ] Strict ID parser rejects booleans.
- [ ] Authoritative final media path, ffprobe, A/V, duration, and fingerprint validation.

## Wave 9 — finish live queues separately

Only after the required core gates:

- [ ] Reconcile `lord-god-strength` long-form local result and ledger.
- [ ] Reconcile all accepted/processing Shorts and exact final types.
- [ ] Recover the exact `legendary-poet` V3 canary/apply state before any upload.
- [ ] Build project-separated catalog, editorial, and postponed plans.
- [ ] Keep the VK Audio browser workflow separate until it has a formal interface.

## Wave 10 — retirement and governance

- [ ] Maintain an explicit supported/retired entrypoint registry.
- [ ] Remove dead generations only after proof of no active references.
- [ ] Generate documentation/CLI consistency checks.
- [ ] Record architecture decisions for state machine, retry taxonomy, project identity, wall firewall, and wave engine.
- [ ] Convert every live incident into a regression test and durable rule.

## Definition of done

A code wave is complete only when:

- the exact issue scope and non-goals are preserved;
- no unrelated provider mutation is included;
- exact-head CI is green on Python 3.11, 3.12, and 3.13;
- every ambiguous provider outcome remains fail closed and externally non-retryable;
- `current-state.md`, audit register, changelog, and issue state are synchronized;
- live canary work, when separately authorized, has exact before/after evidence and a safe recovery decision.
