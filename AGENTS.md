# Repository agent operating contract

This file contains **durable rules**, not a history of old waves or commit SHAs. Historical audits remain evidence; they do not control new work.

## Read order

Before changing provider-facing, workflow, state, release, or artifact code, read only the sources relevant to the task, in this order:

1. `docs/operations/current-state.md` — current operational interpretation and provider boundaries.
2. `docs/operations/project-identity-registry.md` — canonical project/provider identities.
3. The exact owning issue for the requested scope.
4. The relevant runbook/contract, especially:
   - `docs/operations/operational-artifact-standard.md`
   - `docs/operations/operational-package-acceptance.md`
   - `docs/operations/retirement-registry-v1.json`
   - `docs/operations/operator-output-handoff-rule.md`
5. Historical audits only when provenance or a past defect must be understood.
6. `.github/copilot-instructions.md` for Windows/operator handoff details.

Current durable/provider state overrides old chats, screenshots, remembered counts, filenames, stale issue text, and historical packages. Never infer a current authorization from historical success.

## Adaptive reasoning contract

Before implementation or provider-capable handoff, establish:

- requested outcome independent of the old mechanism;
- exact `project_key`, provider surface, target/object type, and owning issue;
- one transport per phase: `local_only`, `official_api_read`, `official_api_write`, `internal_web_read`, `browser_ui_read`, or `browser_ui_write`;
- allowed and forbidden side effects;
- current phase and provider-effect state: `impossible`, `not_dispatched`, `confirmed_absent`, `may_exist`, or `verified`;
- exact completion postcondition;
- one falsifiable hypothesis, one smallest bounded probe, and one stop condition when diagnosing uncertainty.

Preserve partial success. Resume from the first unverified child operation instead of replaying successful parents. Do not add ceremony that cannot change a decision, block a defect class, or prove a postcondition.

## Identity and provenance

Identity must be stable under irrelevant changes.

- Provider/project identity is selected by canonical project + exact target IDs, never by credential name alone.
- Durable same-object keys must not include timestamps, display copy, generated filenames, or other attempt metadata.
- Operational enable/disable flags must not be part of immutable object identity.
- Attempt identity and durable object identity are separate when retries/re-plans are possible.
- Exact accepted bytes are authoritative: bind SHA-256, exact path/ID, and required probe/metadata evidence.
- A final artifact must consume the exact accepted upstream artifacts it claims. If the provenance policy changes, an older final MP4/ZIP/result is historical evidence until regenerated and re-verified under the new policy.
- Content presented as a quotation must map to a contiguous source passage; synthesis/paraphrase must not be formatted as a quote.
- Never select an artifact by newest file, broad wildcard, title-only match, or remembered path when exact identity is available.

## Provider mutation boundary

Release/content approval and provider execution authority are separate gates.

Before any provider mutation:

1. prove canonical project/target identity before credentials are relied on;
2. freeze the exact payload and accepted input digests;
3. prove the relevant review/release gate;
4. prove an explicit execution/write gate for that exact operation;
5. persist durable intent before dispatch;
6. re-check any required exact-current-main / state preconditions immediately before the provider call;
7. use zero blind mutation retries;
8. verify the provider-visible postcondition and persist the result.

A green CI run, review approval, release artifact, credentials, HTTP success, stdout, screenshot, visible UI state, or existing file is not provider execution authority.

Unknown provider outcomes remain blocking. `may_exist`, accepted, processing, or otherwise ambiguous remote effects block replay until read-only reconciliation proves the next safe state.

Upload, processing/visibility, metadata, thumbnail, playlist creation, membership, wall publication, and other remote changes are separate child operations. Preserve verified parent/child success and resume only the first unverified child.

## Runtime and state writers

- One provider account/browser profile/state branch/concurrency namespace has one write owner at a time.
- Parallel agents may work read-only or in disjoint scopes; do not open competing mutation/hardening branches against the same shared runtime.
- Every state writer sharing a durable ledger namespace must share compatible serialization/concurrency rules and be covered by discovery-based regressions where possible.
- A timeout or failed final state push after a provider response is an incident to reconcile, not permission to send again.
- Machine state belongs in durable journals/results/ledgers, not only logs or chat.

## Branch lifecycle

- `main` is the only supported repository code/runtime execution baseline.
- `state/lordchrist-telegram` and `state/svodka-telegram` are durable state-only refs; never use them as code/runtime sources.
- Every other `agent/`, `work/`, `feature/`, `integration/`, `ops/`, `research/`, `arena/`, `tmp*`, or ad-hoc branch is ephemeral.
- After its PR/scope closes, delete an ephemeral ref where supported; if ref deletion is unavailable, align it to exact current `main`.
- Never execute, deploy, recover, or start new work from a closed, unmerged, superseded, or retired branch. Preserve genuinely unique useful work through a focused current-main PR before retiring its ref.

## Browser and wrapper rules

For browser UI work, bind the active page/modal root, prove visibility/hit testing and ownership of the control, capture before-state, perform one action, then verify the exact transition/postcondition. Playback, selection, modal closure, or matching visible text are not substitutes for separate-field readback.

PowerShell and shell wrappers orchestrate one repository-owned implementation. They must not become a second provider client or duplicate retry, pagination, upload, publication, or postflight logic. Do not create generated `executor.py` files or v2/v3/v4 ZIP families as a shortcut; fix repository code and regress the defect.

Retired executors/packages never become runnable again merely because their files still exist. Consult `docs/operations/retirement-registry-v1.json`.

## Artifact and operator handoff

Local/operator artifacts require exact filenames, paths, hashes and success markers. User-facing outputs go to the repository `operator-output` contract unless the user chooses another location. A handoff that requires the operator to search for the produced file is a workflow defect.

For local media/artifact completion, require the evidence demanded by the owning contract (for example SHA-256, ffprobe/QC, timing/package hashes and exact accepted master bindings). Do not call an artifact-level issue complete from code tests alone.

## CI and merge discipline

Substantial work uses one `agent/{description}` branch and one focused PR.

Merge only when all are true:

- the branch is based on/reconciled with current `main`;
- required full CI is green for the exact current PR head/synthetic merge;
- no quality threshold was weakened to obtain green;
- the expected head has not moved;
- scope/diff is reviewed;
- review threads are clean;
- provider side effects performed during implementation/tests are exactly those explicitly authorized (normally zero).

An infrastructure incident or old green run never substitutes for exact-current-head green CI.

Operational-memory/state synchronization is a separate, small change after a runtime/code baseline moves. Do not duplicate historical audit material into `AGENTS.md`.

## Scope closure

Separate three kinds of completion:

- **repository implementation complete** — code/contracts/tests are merged and current-head green;
- **artifact complete** — the exact required final bytes/results are regenerated and verified under the current provenance contract;
- **provider rollout complete** — an explicitly authorized provider operation is verified remotely.

Do not keep repository implementation issues permanently open merely because a future live rollout is intentionally unauthorized. Close the implementation scope when its definition is met and require a new exact owning issue/review for later provider execution. Conversely, do not close an artifact-level issue until its required final artifact evidence exists.

## Current safety defaults

Unless `docs/operations/current-state.md` and an exact reviewed operation prove otherwise:

- provider mutations are unauthorized;
- unknown external settings (for example effective GitHub rulesets/branch protection or Dependency Graph) remain `UNVERIFIED`;
- local/read-only work may proceed only within the owning issue/contract;
- credentials are never printed, committed, packaged, logged, requested for command-line entry, or used as target selectors.
