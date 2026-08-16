# Milovi Issue #323 provider continuation runbook

This runbook covers the canonical promotion continuation path merged through PR #407. It is intentionally multi-invocation. Do not collapse preview, durable intent, provider dispatch, and reconciliation into one command.

## Scope and safety boundary

- Issue: #323, Milovi Cake exact 12-source rollout.
- Canonical command: `video-manager vk milovi-323-continue`.
- Read-only provider probe: `video-manager vk milovi-323-status`.
- Promotion mutations are limited to the existing exact Clip-description and wall-text edit primitives.
- This continuation path does not grant upload, repost, create, delete, or broad cleanup authority.
- A provider dispatch may cross at most one existing exact mutation boundary in one invocation.
- `EDIT_DISPATCH_STARTED` and `UNKNOWN_REQUIRES_RECONCILIATION` are no-replay barriers. Reconcile them with a fresh invocation; never blindly repeat provider confirmation.
- The superseded extra-finalizer draft PR #374 is not a valid execution path.

## Preconditions

1. Start from a clean checkout of current `main` that contains merged PR #407.
2. Use the exact reviewed 12x2 PromotionSpec. Do not regenerate or silently edit public copy during the run.
3. Preserve the existing rollout journal, frozen schedule, prepared-source manifest, and any existing promotion journal. Never replace a durable journal merely to obtain a new plan.
4. Confirm the target is the Milovi VK community `68859909` / owner `-68859909` and the expected account alias from fresh status evidence.
5. Any blocker, digest drift, identity drift, multiple unresolved dispatches, or ambiguous provider outcome is a STOP.

Set the two explicit paths used below:

```powershell
$PROMOTION_SPEC = "<exact-reviewed-promotion-spec.json>"
$PROMOTION_JOURNAL = "<durable-promotion-journal.json>"
```

The rollout journal, schedule, prepared manifest, status output, and continuation output use the CLI defaults unless an operator deliberately supplies different reviewed paths.

## 1. Fresh read-only status

```powershell
video-manager vk milovi-323-status
```

Expected invariant: provider writes are `0`. Inspect the generated status evidence before continuing. A blocked status is not authorization to improvise a mutation.

## 2. Build the fresh whole-batch continuation preview

If the durable promotion journal already exists:

```powershell
video-manager vk milovi-323-continue `
  --promotion-spec $PROMOTION_SPEC `
  --promotion-journal $PROMOTION_JOURNAL
```

If the promotion journal does not yet exist, initialize it exactly once:

```powershell
video-manager vk milovi-323-continue `
  --promotion-spec $PROMOTION_SPEC `
  --promotion-journal $PROMOTION_JOURNAL `
  --confirm-journal-init INITIALIZE_REVIEWED_PROMOTION_JOURNAL
```

Journal initialization is local-only and does not authorize a VK mutation.

For a fresh executable plan with no existing intent, the expected continuation status is `ready_for_digest_confirmation`. Review the full output, especially:

- `promotion_preflight_confirmation_digest` — stable operator confirmation digest;
- `promotion_preflight_evidence_digest` — volatile evidence digest;
- `promotion_provider_state_digest`;
- `promotion_preflight.planned_mutations`;
- `promotion_preflight.expected_provider_writes`;
- `blockers`.

Do not use the volatile evidence digest as the human confirmation token.

If the command instead reports an existing `EDIT_INTENT`, STARTED/UNKNOWN dispatch, `no_promotion_mutations_required`, or a blocker, follow that state rather than forcing a new intent.

## 3. Persist exactly one durable EDIT_INTENT

After reviewing the fresh whole-batch plan, copy the exact stable confirmation digest from the output and run a separate invocation:

```powershell
$PREFLIGHT_DIGEST = "sha256:<reviewed-stable-confirmation-digest>"

video-manager vk milovi-323-continue `
  --promotion-spec $PROMOTION_SPEC `
  --promotion-journal $PROMOTION_JOURNAL `
  --confirm-preflight-digest $PREFLIGHT_DIGEST
```

Expected status: `intent_persisted_requires_separate_provider_dispatch_confirmation`.

Expected invariant: provider writes are still `0`. This invocation only records the first deterministic planned mutation as durable `EDIT_INTENT` bound to the reviewed whole-batch confirmation digest, exact remote identity, and exact BEFORE state.

Never supply `--confirm-preflight-digest` and `--confirm-provider-dispatch` in the same invocation.

## 4. Re-read fresh evidence before provider authorization

Run the canonical continuation again with no confirmation flag:

```powershell
video-manager vk milovi-323-continue `
  --promotion-spec $PROMOTION_SPEC `
  --promotion-journal $PROMOTION_JOURNAL
```

Expected status for a still-valid unstarted intent: `intent_ready_for_provider_dispatch_confirmation`.

This invocation rebuilds the exact dispatch envelope from fresh whole-batch evidence. Review:

- `provider_dispatch_confirmation_digest`;
- `promotion_dispatch_envelope`;
- exact target source/field/remote ID;
- exact BEFORE and AFTER text hashes;
- full wall incarnation when the target is a wall field;
- `blockers`.

Any drift blocks dispatch. Do not replace the durable intent to work around drift.

## 5. Provider dispatch — only after explicit operator authorization

This is the first step that may write VK. Use the exact durable stable digest reported for the existing `EDIT_INTENT`:

```powershell
$DISPATCH_DIGEST = "sha256:<exact-durable-provider-dispatch-confirmation-digest>"

video-manager vk milovi-323-continue `
  --promotion-spec $PROMOTION_SPEC `
  --promotion-journal $PROMOTION_JOURNAL `
  --confirm-provider-dispatch $DISPATCH_DIGEST
```

The command re-runs fresh status/evidence checks and rebuilds the frozen dispatch envelope before entering the existing community write lock. The durable journal is moved to `EDIT_DISPATCH_STARTED` before provider handoff.

A successful writer response does **not** mark the operation VERIFIED in this invocation. Expected status is `provider_dispatch_started_requires_fresh_reconciliation`, and the next step must be a fresh invocation.

If the provider effect is ambiguous, the durable state becomes `UNKNOWN_REQUIRES_RECONCILIATION`. Do not repeat `--confirm-provider-dispatch`.

## 6. Fresh reconciliation — never replay the edit

Run the canonical continuation again with no confirmation flag:

```powershell
video-manager vk milovi-323-continue `
  --promotion-spec $PROMOTION_SPEC `
  --promotion-journal $PROMOTION_JOURNAL
```

The command consumes fresh provider evidence and attempts exact AFTER verification for the existing STARTED/UNKNOWN operation.

Possible safe outcomes include:

- `dispatch_reconciled_verified_ready_for_next_plan` — exact AFTER proven; the next invocation may build the next whole-batch plan;
- `dispatch_unknown_requires_reconciliation` — exact outcome still not proven; STOP and investigate read-only evidence;
- `blocked` — STOP;
- `no_promotion_mutations_required` — promotion copy is already complete under the reviewed spec.

Never use a new provider confirmation to resolve STARTED/UNKNOWN. Reconciliation owns that state.

## Iteration rule

Repeat steps 2–6 one deterministic promotion mutation at a time. Every provider mutation requires:

1. fresh whole-batch provider evidence;
2. a reviewed stable digest;
3. durable `EDIT_INTENT` in a separate invocation;
4. fresh envelope reconstruction;
5. a separate exact provider-dispatch confirmation;
6. durable STARTED before handoff;
7. fresh exact reconciliation before any later mutation.

## Hard STOP conditions

Stop without provider mutation if any of these occurs:

- fresh status cannot produce typed promotion observation;
- PromotionSpec or journal binding is invalid;
- the reviewed stable confirmation digest changes;
- exact target remote identity changes;
- exact BEFORE text/hash changes;
- the wall incarnation changes unexpectedly;
- more than one unresolved dispatch or more than one unstarted intent exists;
- STARTED and unstarted intent coexist;
- a writer reports an ambiguous outcome;
- exact AFTER cannot be proven;
- any command requests a path outside the exact Issue #323 promotion authority.

Do not fall back to the historical finalizer, upload, delete, repost, or a manual VK mutation to bypass a STOP.

## Completion

Do not close Issue #323 merely because the code path or promotion journal reaches a terminal state. The Issue body requires fresh provider evidence proving the full 12-source Clip and logical wall-mapping completion contract. Keep the Issue open until those completion predicates are all proven by the current provider state.
