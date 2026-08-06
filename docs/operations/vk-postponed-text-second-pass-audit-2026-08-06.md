# VK postponed-text editor: second-pass audit and hardening record

Date: 2026-08-06–07  
Owning issue: #152  
Owning delivery: PR #153  
Baseline reviewed: `main@c0b8a303598788b2870862042d2e2868a97b3005`  
Initial capability merge: `c04f0a4f948174ced6287e4bae87e4bf1be2be52`  
Hardening implementation commit: `f7e0a7dc0a6ad965045783638c25384d69fe6b08`

## Executive verdict

Two conclusions must remain separate.

### Historical operation

The 2026-08-06 Lord God cleanup is verified:

- project `lord-god-strength`;
- community `60805374`, owner `-60805374`;
- attachment-free target postponed IDs `12513..12541`;
- `29/29` exact after-state;
- `0` pending;
- postponed count `66/66`;
- 37 non-target postponed rows unchanged;
- first published quote post untouched;
- final status `succeeded`.

No replay is needed or authorized.

### Reusable capability

The initial PR #150 implementation contained strong safety controls but overstated several generic guarantees. Issue #152 and PR #153 harden those gaps. Correct pre-merge status:

`HISTORICAL_OPERATION_VERIFIED / HARDENING_IMPLEMENTED / EXACT_HEAD_CI_REQUIRED / NO_ACTIVE_PROVIDER_MUTATION`

## Sources reviewed

- full conversation and pasted PowerShell/VK outputs;
- issue #147 and PRs #150/#151;
- issue #152 and PR #153;
- production module, CLI, lock helper, wall snapshots, tests, wrapper, runbook, `AGENTS.md`, current state, and audit registers;
- GitHub Actions queue/cancellation evidence for #3208/#3209.

## Positive controls retained

The implementation continues to provide:

1. exact project/community/owner validation;
2. sorted unique explicit post IDs;
3. immutable request and plan digests;
4. exact before/after text and SHA-256 evidence;
5. complete published/postponed preflight;
6. exact `before`, `after`, and `conflict` states;
7. resume by skipping exact-after operations;
8. intent-before-dispatch;
9. explicit owner, post, message, and original publication date;
10. exact live readback rather than HTTP-success trust;
11. transient retry only after confirmed no effect and delayed re-read;
12. CAPTCHA stop without OCR or bypass;
13. unknown-outcome stop;
14. final target and non-target postconditions;
15. conservative 25-second default cadence;
16. durable operation history.

These controls explain why the historical partial runs were safely resumable.

## Findings and remediation

### A1 — lock depended on output directory

**Original defect:** two runs with different result folders used different lock files for the same VK community.

**Remediation:** PR #153 derives one lock from configured data directory, account alias, and community ID:

```text
data/locks/vk/<account-alias>-<community-id>.lock
```

The lock is acquired before live preflight and held through final postconditions.

**Regression:** a held lock blocks execution from a second output directory before any `wall.edit`.

### A2 — publication safety checked only once

**Original defect:** a long batch could cross `minimum_future_seconds` before a later dispatch.

**Remediation:** timezone-aware publication distance is checked during initial readiness, immediately before each dispatch, and immediately before every controlled retry.

**Regressions:** later-operation threshold crossing and retry-time threshold crossing stop with zero additional mutations.

### A3 — delayed reconciliation journal could remain stale

**Original defect:** aggregate result could say `verified_after_delayed_reconciliation` while the attempt journal still said `transient_confirmed_absent_waiting_retry`.

**Remediation:** the same journal is rewritten terminally with `provider_effect=verified`, reconciliation time, and finish time before aggregate success is recorded.

**Regression:** durable journal and result are asserted equal in meaning.

### A4 — attachment preservation was overstated

**Original defect:** target attachment tokens were sorted; snapshot fingerprints omitted unsupported attachment forms. The no-attachment historical run did not prove generic attachment preservation.

**Remediation:** schema v1 now rejects `allow_attachments=true` and every target with any attachment. Target `wall.edit` always carries an explicit empty attachment parameter.

Non-target postconditions hash the ordered raw attachment payload, including access-key-bearing data and unsupported attachment shapes, instead of relying only on sorted canonical tokens.

**Regressions:** attached targets fail closed and non-target attachment-order changes fail final postcondition.

### A5 — output evidence could be overwritten or mixed

**Remediation:** an existing `result.json` must match the same plan digest. Journal filenames are never overwritten; repeated use gets a new durable suffix.

### D1/D2 — missing PowerShell wrapper and Pester coverage

**Remediation:** `scripts/Invoke-VkPostponedTextEdit.ps1` now:

- uses strict/fail-fast behavior;
- resolves input with `-LiteralPath`;
- validates read-only versus apply parameters;
- requires a full lowercase `sha256:<64 hex>` confirmation and explicit write switch;
- forwards safety timing controls;
- checks native exit code;
- invokes only `video_channel_manager.cli.vk_postponed_text`;
- contains no token or direct provider transport.

`tests/powershell/VkPostponedTextEdit.Tests.ps1` covers read-only argument construction, apply refusal, guarded apply forwarding, native exit propagation, and absence of token/provider code.

### D3/D4 — missing edge regressions

Python tests now cover:

- ambiguous post-dispatch read failure → `unknown_requires_reconciliation` with no retry;
- same community lock across different output directories;
- publication threshold crossing before dispatch;
- threshold crossing before a retry;
- delayed journal terminal consistency;
- attachment authority rejection;
- attached-target rejection;
- non-target raw attachment-order mutation;
- existing 429, CAPTCHA, partial resume, conflict, and non-target text mutation cases.

### S1/S2 — stale entry and conflated baselines

**Remediation:** `AGENTS.md` is now a compact current entry contract. `current-state.md` explicitly distinguishes:

- repository baseline entering hardening `c0b8a303...`;
- initial capability merge `c04f0a4...`;
- hardening implementation commit `f7e0a7dc...`;
- active repository-only issue #152 / PR #153.

The runbook now states attachment-free schema v1 and documents the global lock, per-dispatch time check, terminal journals, wrapper, and raw non-target fingerprints.

## CI and merge-process audit

PRs #150/#151 were merged without the repository-required green CI because Actions runs #3208/#3209 never started and normal/force cancellation returned HTTP 502.

Accurate interpretation:

- known failing test: none observed;
- green proof: not obtained;
- manual source review: performed;
- infrastructure exception: real;
- policy compliance: incomplete.

PR #153 must not merge until its exact final head receives all six green CI jobs. The infrastructure exception is historical context, not a waiver.

## Chat-level negative examples

### N1 — incomplete endpoint scope presented as complete inventory

A connector query returned one PR-associated run, while a later direct Actions query found both #3208 and #3209.

**Rule:** state endpoint/filter limitations and confirm a complete inventory through the authoritative workflow-run surface.

### N2 — expected cancellation stated as guaranteed

The assistant predicted force-cancel would close the runs. GitHub returned HTTP 502 and readback showed both still queued.

**Rule:** no mutation, cancellation, or merge is complete until exact readback confirms it.

### N3 — completion announced before deliverable-by-deliverable audit

The work was called fully complete before checking the missing wrapper, Pester coverage, ambiguous-outcome test, stale `AGENTS.md`, and generic edge guarantees.

**Rule:** compare every owning-issue requirement against actual files and tests before closure.

### N4 — historical success generalized beyond exercised conditions

The successful operation had no target attachments and did not exercise concurrent writers or publication-threshold crossing.

**Rule:** exercised evidence supports only the exercised branch. Unsupported branches remain unproved.

### N5 — infrastructure exception substituted for verification

Manual review was useful but was treated as sufficient to merge.

**Rule:** infrastructure failure can explain missing CI but cannot become green CI.

### N6 — confidence language exceeded readback

Several responses said a command “will” cancel or that repository work was “fully done” before verification.

**Rule:** use conditional language until postcondition readback exists, then report the exact observed state.

## Provider boundary

Hardening work is `local_only` plus GitHub repository writes. It performs:

- VK provider reads: `0`;
- VK provider writes: `0`;
- historical executor runs: `0`;
- CAPTCHA handling: `0`.

The credential token is never printed, copied, packaged, committed, or requested.

## Closure gates

Issue #152 may close only after:

1. exact final PR head is known;
2. all six CI jobs are green on that head;
3. changed scope is reviewed;
4. review threads are empty/resolved;
5. newest machine-state overlay records exact quality proof and merge;
6. provider activity remains `0/0`;
7. no historical plan is replayed;
8. PR #153 is merged into `main` with the expected head unchanged.
