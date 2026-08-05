# Timeline

## Phase 1 — editorial package presented without an executable production path

The transcript records ten prepared Legendary Poet article posts, dates, text hashes, preview commands, and an explicit statement that no working execute command was being provided because the production provider adapter was not connected.

That limitation was accurate. The handoff was still incomplete for the operator's goal because “open all texts” and preview output did not answer the next safe operational step.

Evidence class: `editorial_prepared` / `preview_validated`, not provider-ready.

## Phase 2 — operator reports another error cascade

The operator explicitly reported that the previous ZIP was only an editorial preparation and did not contain the expected PowerShell automation. The response acknowledged this as an error.

Instead of extending the permanent repository contract, a new external package family was created:

- LordGod-VK-SERMON-MONTH v2;
- standalone `RUN-SERMON-MONTH.ps1`;
- standalone Python publisher;
- separate `CHECK-ONLY.ps1` and CMD wrapper;
- thirty texts and target videos;
- canary then remaining twenty-nine operations.

This increased operational surface and duplicated provider logic outside the supported operator.

Evidence class before execution: `self_tested` at most.

## Phase 3 — v2 false permission rejection

The operator ran v2. Local self-test returned success. The read-only VK preflight then stopped with a claim that the token did not confirm administrative access to community `60805374`. The transcript states that no postponed posts were created by v2.

Root cause reported in the transcript:

- v2 used `groups.get(filter=admin)`;
- the repository client used `groups.get(filter=moder)`;
- `moder` covers moderator, editor, and administrator management roles;
- `admin` was therefore an invalid equivalence assumption for the intended capability check.

Permanent regression: the repository test now asserts `filter=moder`, `extended=1`, and bounded pagination parameters.

## Phase 4 — v3 correction

The transcript reports these v3 corrections:

- `groups.get(filter=moder)`;
- normalization of different response forms;
- fallback inspection of `is_admin` / `admin_level`;
- exact target community check;
- canary verification before batch continuation;
- per-operation result JSON;
- token value not printed.

These are valid controls, but the v3 package remained a parallel external implementation rather than the permanent repository operator.

## Phase 5 — transcript-reported batch outcome

The transcript later reports:

- group `60805374` / owner `-60805374`;
- `30/30` operations with `operation_ok`;
- first post `-60805374_12482`;
- last post `-60805374_12511`;
- schedule 6 August–4 September 2026, daily 20:00 Moscow time;
- eleven managed communities returned by the permission query;
- nine postponed posts present before the new queue;
- no detected schedule conflict;
- instruction not to rerun the package.

Evidence class: `operator_transcript_reported_batch_outcome`.

Not available in this repository:

- original v3 ZIP;
- immutable v3 manifest and archive digests;
- the thirty per-operation result files;
- exact canary readback;
- fresh postflight wall snapshot;
- independent provider API verification.

The repository therefore preserves the report without converting it into `batch_verified` operational state.
