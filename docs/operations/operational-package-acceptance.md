# Operational package acceptance contract

This contract prevents an editorial, preview, or self-tested artifact from being represented as a provider-ready operational package.

## Truth levels

Every package or handoff must declare exactly one evidence level:

1. `editorial_prepared` — texts, dates, assets, and source references are prepared; no executable path is implied.
2. `preview_validated` — deterministic local validation passed; no provider adapter or write path is implied.
3. `self_tested` — the packaged runtime passed offline tests against fixtures; current provider state is not proven.
4. `canary_verified` — one separately reviewed exact operation reached its exact remote postcondition and durable result.
5. `batch_verified` — every reviewed batch operation has a durable final result and exact remote postcondition, with no silent unknown outcome.

Evidence levels are monotonic only when the retained evidence proves the next level. A filename, ZIP, README, successful local preview, prompt for confirmation, or green CI cannot upgrade the level by itself.

## Package kinds

A manifest must declare one of:

- `editorial_bundle`;
- `read_only_evidence_bundle`;
- `provider_write_bundle`.

An `editorial_bundle` or `read_only_evidence_bundle` must set:

- `provider_adapter_connected=false`;
- `provider_writes_authorized=false`;
- `automatic_execution=false`.

A `provider_write_bundle` is structurally acceptable only when all of the following are true:

- exact registered `project_key` is present;
- exact target community/channel/owner identity is present;
- `supported_entrypoint` equals a current entrypoint from `retirement-registry-v1.json`;
- provider implementation is repository-owned rather than a newly generated Downloads-only executor;
- `provider_adapter_connected=true`;
- `read_only_preflight_required=true`;
- `canary_required=true`;
- `per_operation_results_required=true`;
- `unknown_outcome_requires_reconciliation=true`;
- `blind_retry_prohibited=true`;
- `separate_review_required=true`;
- the package is verified by `python -m video_channel_manager.tools.operational_package_acceptance`.

Passing structural acceptance does not authorize a provider write. A separate reviewed immutable plan and operator confirmation remain mandatory.

## PowerShell and Python ownership

PowerShell is an orchestration and operator-experience boundary. It may:

- locate files with `$PSScriptRoot`;
- validate prerequisites;
- invoke one repository-owned CLI or module;
- display the exact project, mode, manifest digest, result path, and recovery instruction;
- propagate the child exit code.

PowerShell must not duplicate provider rules, permission interpretation, pagination, retry semantics, result classification, or postflight logic already owned by Python.

Python provider logic must live in the repository, use versioned request/result JSON, and remain covered by CI. A generated standalone `executor.py` beside a ZIP is not a supported production adapter merely because it can call the provider.

## VK managed-community preflight

The supported VK client enumerates managed communities with `groups.get(filter=moder, extended=1)` because the managed set includes moderator, editor, and administrator roles. `filter=admin` is not an equivalent capability check and can produce a false negative for a valid management token.

The returned response shape must be normalized before project matching. A successful permission preflight still must bind the exact registered community and owner; membership in a general managed-community list is not project selection.

## Canary and batch evidence

A canary is a dependency, not ceremonial output. Batch dispatch is blocked until the exact canary postcondition is read back and durably recorded.

Every operation requires its own result object. One final `FINAL_OK` line is supplementary and cannot replace per-operation results. A local timeout or unknown provider response stops automatic execution and enters reconciliation; it never becomes blind retry permission.

## Handoff language

Use the declared truth level literally:

- say “editorial package prepared” for `editorial_prepared`;
- say “preview passed” for `preview_validated`;
- say “offline self-tests passed” for `self_tested`;
- say “canary verified” only with exact canary evidence;
- say “batch verified” only with complete per-operation evidence.

Never say “ready to run”, “fully automatic”, “all posts scheduled”, or “nothing else is needed” unless retained machine evidence supports that exact claim.

## Historical incident boundary

The Lord God sermon-month v1/v2/v3 packages described in the 2026-08-05 operator transcript are historical evidence only. The transcript records an editorial-to-operational handoff failure, a false permission rejection caused by `filter=admin`, a correction to `filter=moder`, and a reported later `30/30` outcome. The original v3 result directory and exact provider readbacks were not supplied to this repository, so the batch outcome is classified as `operator_transcript_reported`, not independently re-verified.

Do not rerun v1, v2, or v3. Any future scheduled-wall workflow must be rebuilt under the supported repository contract and a separately reviewed exact-ID plan.

The registered production write entrypoint is `scripts/operator/Invoke-VideoManager.ps1`; this contract does not create another supported write entrypoint.
