# Mistakes, corrections, and permanent controls

## 1. A prepared package was described beyond its actual capability

**Mistake:** editorial texts, dates, SHA-256 values, and preview commands were not the live execution path the operator expected.

**Why it happened:** “package complete” combined editorial completeness with operational readiness.

**Permanent control:** every package declares exactly one evidence level: `editorial_prepared`, `preview_validated`, `self_tested`, `canary_verified`, or `batch_verified`.

## 2. The handoff ended at “open the texts”

**Mistake:** the operator was told to inspect files but was not given one supported next action or a clear blocker.

**Permanent control:** every handoff states the exact next command, or states that no execution command exists and names the missing dependency. Never substitute manual file opening for an unavailable provider adapter.

## 3. A parallel Python/PowerShell publisher was generated after the repository boundary had already been identified

**Mistake:** the transcript correctly noted that only the repository operator was supported, then later generated a standalone publisher family outside it.

**Risk:** duplicated permission logic, retry semantics, project binding, result models, and postflight behavior; each fix required another package generation.

**Permanent control:** PowerShell orchestrates one repository-owned CLI. Python provider logic lives under `src/`, uses versioned JSON, and is covered by CI. Downloads-only executors are never a supported adapter.

## 4. Permission semantics were guessed

**Mistake:** `groups.get(filter=admin)` was treated as the management capability check.

**Observed effect:** valid management access was falsely rejected before any write.

**Correction:** use `groups.get(filter=moder, extended=1)`, normalize the response, then separately bind the exact registered community and owner.

**Permanent control:** provider permission parameters are regression-tested literally. A semantically similar parameter is not silently substituted.

## 5. Provider response shape and role fields were under-specified

**Mistake:** one expected response shape and one `is_admin` field were assumed.

**Correction:** normalize list and object-with-items forms; interpret `is_admin` or `admin_level` for management metadata without using either as project selection.

## 6. One final line risked becoming the only success evidence

**Mistake pattern:** `FINAL_OK — 30/30` is easy to treat as the result.

**Permanent control:** every operation owns a durable result. The final line is supplementary. Batch verification requires complete per-operation evidence plus exact postflight.

## 7. Canary was useful but must be a real dependency

**Correction retained:** batch continuation follows exact canary verification.

**Permanent control:** canary evidence includes exact project, operation ID, target ID, expected postcondition, observed postcondition, timestamp, and result digest. A sleep or successful request is not canary verification.

## 8. Unknown outcomes never authorize retry

A timeout after dispatch, interrupted PowerShell process, or incomplete response becomes `unknown_requires_reconciliation`. It is not “failed” and is not automatically retransmitted.

## 9. Project identity must be repeated at every scope transition

The conversation referenced both Legendary Poet (`235216998`) and Lord God (`60805374`). The transition was operationally significant.

**Permanent control:** every launcher and report prints `project_key`, exact channel/community/owner IDs, mode, manifest digest, and result path before any network operation.

## 10. A successful historical run is not a reusable launcher

Even when the reported v3 outcome is accepted as a truthful operator report, the package is retired. Reusing it would rely on stale dates, stale wall state, and an external implementation superseded by repository governance.

## Final retirement instruction

Do not rerun sermon-month v1, v2, or v3. Preserve their outcome only as historical evidence and rebuild any future schedule from fresh exact state under the repository operator.
