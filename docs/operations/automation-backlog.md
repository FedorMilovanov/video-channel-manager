# Operational automation backlog

Updated: 2026-08-04

This backlog is subordinate to [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md) and the machine-readable [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json). It must not re-activate retracted findings, retired executors, or completed destructive operations.

## Active tracking

- #31 — reconcile the 26-item long-form upload result and ledger;
- #32 — inventory the real VK Clips surface and classify the Shorts queue;
- #33 — organize and publish the verified VK catalog after dependencies;
- #36 — universal upload/wall separation and postponed publishing;
- #37 — exact approved Shorts wall-cleanup scope;
- #38 — VK Shorts upload modes and final type/player behavior;
- #64 — master reliability roadmap;
- #65 — completed Wave 1 upload state machine and recovery;
- #66 — merged Wave 1 implementation.

Issue #33 remains blocked until #31, #32/#38, and #36 have no silent unknown outcomes. Wave 1 now prevents blind reservation/upload retries, but live queue continuation remains blocked until exact historical journal reconciliation.

## Wave 0 — canonical state

- [x] Add the master reliability audit and wave roadmap.
- [x] Add a machine-readable finding register with status, severity, owner issue, and wave.
- [x] Update `current-state.md` with PR #61–63, completed article wave, separate project queues, and current blockers.
- [x] Link the operations index to the new sources of truth.
- [x] Create focused Wave 1 issue #65.
- [x] Expand issue #64 with all omitted P0/P1 findings and wave dependencies.
- [x] Append the project-memory changelog.
- [x] Close superseded draft PR #29 after preserving its reusable ledger/reconciliation lessons.
- [x] Update root `AGENTS.md` to require the master audit/register before code or provider work.

Wave 0 is complete. It performed no provider writes.

## Wave 1 — upload state machine and recovery

Completed by PR #66, merge `56da03247f60ec9d25f1646fb9ccdfbb651aff9c`.

- [x] Persist reservation intent before `video.save`.
- [x] Persist a separate dispatch marker so pre-dispatch restart and ambiguous dispatch are distinguishable.
- [x] Persist exact upload ticket immediately after reservation.
- [x] Add explicit `unknown_requires_reconciliation` behavior.
- [x] Require verified stage or full exact reconciliation before reuse.
- [x] Define identity/title/duration/type/processing/playability readiness contract.
- [x] Add crash fault-injection tests after every state boundary.
- [x] Prove verified replay is a no-op and ambiguous boundaries cannot create a second reservation or upload.
- [x] Migrate legacy upload records fail closed.
- [x] Keep orphan cleanup, live queue reconciliation, wall work, and provider-protocol invention out of scope.
- [x] Pass exact-head CI on Python 3.11, 3.12, and 3.13.

Wave 1 is complete. It performed no VK or YouTube writes.

## Wave 2 — fail-closed content and project pipeline

Next engineering wave. It must be split into one focused issue and one isolated PR from the Wave 1 merge baseline.

- [ ] Run full per-record validation inside every load/preview/plan path.
- [ ] Remove implicit project defaults from reusable parsing.
- [ ] Require complete targets↔operations coverage.
- [ ] Make base sync project-aware or internal-only.
- [ ] Keep exactly one supported public sync entrypoint.
- [ ] Add cross-project and direct-bypass behavioral tests.
- [ ] Preserve the Wave 1 lifecycle and no-live-retransmission boundary.

## Wave 3 — transport, retries, and limiter

- [ ] Move `YouTubeCommentWriter` to the shared HTTP ownership lifecycle.
- [ ] Inventory all remaining `httpx.Client()` sites.
- [ ] Centralize request construction, redaction, parsing, and provider error taxonomy.
- [ ] Add bounded read-only retry/backoff for YouTube.
- [ ] Add configurable proactive VK limiter after provider-policy verification.
- [ ] Keep ambiguous mutation retry policy separate and fail closed.
- [ ] Cache the YouTube uploads playlist ID for the client lifecycle.

## Wave 4 — wall safety subsystem

- [ ] Preserve proven `wallpost=0` upload behavior.
- [ ] Research disputed `auto_publish`/`repeat` provider contract before a universal mandate.
- [ ] Require `wall_mutation_authorized=false` in upload manifests.
- [ ] Add before/after wall delta audit for uploads.
- [ ] Use postponed publication as the default path.
- [ ] Scan published and postponed posts and exact schedule-slot collisions.
- [ ] Treat `guid` as an additional guard, not complete idempotency.

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
- [ ] Dependency injection instead of production monkeypatching.
- [ ] Remove private cross-script imports.
- [ ] One versioned journal schema with guarded migrations.
- [ ] One canonical text/URL normalizer.
- [ ] Archive retired executors only after reference scans.

## Wave 7 — risk-based tests

- [ ] Module-specific coverage gates for clients, writers, CLI, and executors.
- [ ] Preserve and extend the Wave 1 fault matrix for intent, acceptance, lost response, delayed visibility, journal write, and restart.
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
- [ ] Record architecture decisions for state machine, retry taxonomy, project identity, and wave engine.
- [ ] Convert every live incident into a regression test and durable rule.

## Definition of done

A code wave is complete only when:

- the exact issue scope and non-goals are preserved;
- no unrelated provider mutation is included;
- exact-head CI is green on Python 3.11, 3.12, and 3.13;
- every ambiguous provider outcome remains fail closed;
- `current-state.md`, audit register, changelog, and issue state are synchronized;
- live canary work, when authorized, has exact before/after evidence and a safe recovery decision.
