# VK postponed-text editor: second-pass audit of chat, operation, and repository

Date: 2026-08-06  
Owning follow-up: issue #152  
Historical operation: Lord God postponed quote cleanup  
Repository baseline reviewed: `main@c0b8a303598788b2870862042d2e2868a97b3005`

## Executive conclusion

The completed VK cleanup itself is supported by exact final evidence:

- project `lord-god-strength`;
- community `60805374`, owner `-60805374`;
- target postponed IDs `12513` through `12541`;
- `29/29` targets exact after-state;
- `0` pending targets;
- postponed count `66` before and after;
- `37` non-target postponed rows unchanged;
- final status `succeeded`.

That successful no-attachment operation does **not** prove that every advertised property of the reusable repository implementation is correct. A second-pass comparison of the chat, issue #147, PRs #150/#151, tests, and current source found material gaps. Therefore the correct status is:

`HISTORICAL_OPERATION_VERIFIED / REUSABLE_CAPABILITY_MERGED_BUT_HARDENING_REQUIRED / NO_ACTIVE_PROVIDER_MUTATION`

No completed VK edit must be replayed. This audit authorizes repository-only work.

## Sources reviewed

- the complete 2026-08-06 conversation and pasted PowerShell/VK outputs;
- issue #147 and its required safety/deliverable list;
- PR #150 exact head `0bfb1260c37411e8df686f26120ceea85e2f8116`;
- code merge `c04f0a4f948174ced6287e4bae87e4bf1be2be52`;
- state-sync PR #151 and repository head `c0b8a303598788b2870862042d2e2868a97b3005`;
- `postponed_text_edit.py`, CLI, tests, lock helper, wall snapshot implementation, runbook, `AGENTS.md`, `current-state.md`, and audit register v10;
- GitHub Actions run/cancellation evidence for #3208 and #3209.

## Positive controls that are correctly implemented

The following properties are present and materially useful:

1. Exact project/community/owner validation.
2. Sorted unique explicit target post IDs.
3. Immutable request and plan self-digests.
4. Exact before and after text with SHA-256 evidence.
5. Complete postponed/published preflight requirement.
6. Exact `before`, `after`, and `conflict` reconciliation states.
7. Existing exact-after targets are skipped during resume.
8. Intent is persisted before `wall.edit` dispatch.
9. `owner_id`, `post_id`, `message`, `publish_date`, and attachment parameter are sent explicitly.
10. HTTP success alone is not accepted as completion; exact live readback is required.
11. HTTP 429/transient retry is permitted only after readback confirms exact before-state and after a delayed second read.
12. CAPTCHA/error 14 stops without OCR or bypass.
13. Unknown postflight state stops for reconciliation.
14. Final target exact-after proof and non-target fingerprint comparison exist.
15. The conservative default inter-operation delay is 25 seconds.
16. Historical failure modes and the final 29/29 operation are documented.

These controls explain why the exact historical operation was safely resumable after partial success.

## Confirmed high-priority implementation gaps

### A1. The community write lock is not actually global

`local_vk_write_lock()` states that it prevents two local processes from mutating the same VK community. The postponed editor calls it with:

```python
output_dir / "vk-postponed-text-edit.lock"
```

Two executions using different output directories therefore use different lock files and can both run against the same account/community.

**Risk:** concurrent exact plans can interleave reads and writes, creating conflicts or ambiguous evidence.

**Required correction:** derive one stable lock path from the configured data directory, account alias, and community ID. `output_dir` may contain run journals, but it must not define writer exclusivity.

### A2. Publication-distance safety is checked only once

The code calculates the current epoch and checks all pending publication dates before entering the batch loop. It does not repeat that check immediately before each later dispatch or controlled retry.

**Risk:** a long batch can begin safely and later cross `minimum_future_seconds` before a subsequent `wall.edit`.

**Required correction:** validate timezone-aware current time and the exact operation's `publish_date` immediately before every dispatch and before every retry.

### A3. Delayed reconciliation can contradict its journal

After a transient failure, the journal is written as:

`transient_confirmed_absent_waiting_retry`

If the delayed read then discovers exact after-state, the aggregate result records:

`verified_after_delayed_reconciliation`

but the journal file is not rewritten to a terminal verified state.

**Risk:** durable child evidence and the final aggregate disagree about provider effect.

**Required correction:** update the same attempt journal with terminal state, verified provider effect, reconciliation timestamp, and finished time before adding the aggregate result.

### A4. Attachment preservation claims exceed the implementation

The target attachment helper sorts canonical tokens before putting them in the plan and before sending them to `wall.edit`. The wall snapshot fingerprint also sorts attachments and silently drops attachments that cannot be represented as `type<owner>_<id>`.

Consequences:

- original attachment order is not preserved;
- access-key-dependent attachment identity is not preserved;
- unsupported attachment forms can be invisible in non-target comparison;
- a no-attachment historical success cannot prove arbitrary attachment safety.

**Required correction:** for schema v1, fail closed on every target attachment and narrow documentation accordingly, or introduce a new reviewed schema that preserves exact ordered API tokens including access keys. Non-target reads must fail closed when attachment identity cannot be represented rather than silently omitting it.

## Required deliverables that were declared complete but are absent

### D1. Repository-owned PowerShell wrapper

Issue #147 explicitly required a PowerShell wrapper. PR #150 contains a Python CLI and documentation snippets, but no repository-owned wrapper file dedicated to this capability.

**Required correction:** add a strict fail-fast wrapper that invokes only the package CLI, defines every path/variable, checks native exit codes, and never handles a token.

### D2. Pester coverage for the wrapper

No capability-specific Pester tests were added.

**Required correction:** test path validation, argument forwarding, refusal without confirmation/write flag, preservation of nonzero native exit codes, and absence of provider logic in PowerShell.

### D3. Ambiguous postflight regression

The Python tests cover plan creation, before/after/conflict, successful resume, HTTP 429, CAPTCHA, and non-target mutation. They do not simulate post-dispatch read failure/incomplete read and assert `unknown_requires_reconciliation` with no retry.

**Required correction:** add the missing regression plus exact journal assertions.

### D4. Concurrency, threshold-crossing, and journal-consistency regressions

No tests prove:

- two output directories still contend on one community lock;
- a later operation crossing the future threshold stops before dispatch;
- a controlled retry rechecks the threshold;
- delayed reconciliation rewrites the journal terminally.

## Documentation and state inconsistencies

### S1. `AGENTS.md` is stale

The entry document still lists the Wave 16 baseline and six-job-green merge rule, while `current-state.md` says it overrides the stale paragraph. Entry-point guidance should not require a reader to discover that its own baseline is superseded.

**Required correction:** add audit register v10 and this audit to the mandatory reading order; distinguish current repository head from production-code head; record issue #152 as active repository hardening only.

### S2. Production-code baseline and repository head are conflated

`current-state.md` calls `c04f0a4...` the current code baseline, but the actual repository head after state sync is `c0b8a303...`.

**Required correction:** record both explicitly:

- production capability merge: `c04f0a4...`;
- current repository head before hardening: `c0b8a303...`.

### S3. “Fully complete” was claimed too early

Issue #147 was closed and the user was told the work was complete before verifying every deliverable and edge-case claim against the issue.

**Required correction:** issue #152 remains open until all remediation and quality proof are complete.

## CI and merge-process audit

The repository's own `AGENTS.md` says substantial work merges only after exact-head six-job green CI. PRs #150 and #151 were merged without that proof because GitHub Actions runs #3208/#3209 remained queued and both normal cancellation and force-cancel returned HTTP 502.

The exception was honestly documented and no known failing test was hidden. Nevertheless, this is a process deviation, not a green result.

Correct status:

- CI service outcome: unavailable/queued;
- failing test observed: no;
- green proof obtained: no;
- manual source review performed: yes;
- post-merge verification still required: yes.

Issue #152 must not close without an actual quality proof covering compile, dependency graph, Ruff, format, mypy, pytest, and PowerShell tests, or the repository's normal six-job CI.

## Chat-level negative examples

These examples are preserved because they teach response discipline as well as code discipline.

### N1. Incomplete tool scope was presented as complete inventory

The connector query showed one queued PR-associated run, and the assistant said only one active run remained. A later direct Actions API query found two: #3208 and #3209.

**Lesson:** state the endpoint/filter scope before claiming a complete inventory. Cross-check workflow runs by exact head through the authoritative Actions endpoint.

### N2. Expected cancellation was stated as guaranteed

The assistant said force-cancel would leave no active CI. Both normal cancel and force-cancel returned HTTP 502, and both runs remained queued.

**Lesson:** mutation/cancellation completion is established only by readback. Use conditional language before confirmation.

### N3. Completion was announced before line-by-line deliverable review

The assistant said everything requested was finished. The second pass found the missing PowerShell wrapper, missing regressions, stale `AGENTS.md`, and generic safety gaps.

**Lesson:** compare implementation against every owning-issue requirement before closing or announcing completion.

### N4. Historical success was over-generalized

The final VK operation contained no target attachments and did not exercise concurrent writers or publication-threshold crossing. Documentation nevertheless described general attachment preservation and a fully supported capability.

**Lesson:** distinguish exercised evidence from inferred capability. Unsupported branches remain unproved even when one exact operation succeeds.

### N5. Infrastructure exception became a substitute for verification

Manual review was appropriate as an emergency diagnostic, but it was used to merge instead of deferring until a quality proof existed.

**Lesson:** an infrastructure incident can explain missing CI; it does not transform manual review into green CI.

## Historical operation verdict

The completed 29-post cleanup remains valid. The findings above do not imply that those posts were changed incorrectly:

- target IDs were exact and attachment-free;
- final readback showed every target exact after-state;
- queue count remained 66;
- all 37 non-target postponed rows remained unchanged;
- no replay is needed or authorized.

The audit changes only the confidence level assigned to the reusable code and documentation.

## Closure criteria for issue #152

Issue #152 can close only when all of the following are true:

1. Stable account/community lock independent of output directory.
2. Per-dispatch and per-retry publication-distance checks.
3. Terminally consistent delayed-reconciliation journal.
4. Attachment support either made exact and ordered or explicitly rejected in schema v1.
5. Repository-owned PowerShell wrapper and Pester tests.
6. Ambiguous readback, concurrency, threshold, and journal regressions.
7. `AGENTS.md`, `current-state.md`, and machine state synchronized.
8. Actual green six-job CI or equivalent recorded local quality proof.
9. PR review confirms no VK provider calls or writes occurred during hardening.
10. No historical plan or executor is replayed.
