# Repository post-release control audit — 2026-08-09

Status: point-in-time repository/control audit after the «Чёрный человек» YouTube rollout. This document is evidence and prioritization, not provider authorization.

## Audit baseline

Audit began from `main@69682b09f3ee1613f83c552278fa85350babab12`.

During the audit, the independent GitHub-governance closure PR #230 passed exact-head CI and was merged as:

```text
main@4625b872dd7df70c19e19c0596b19f377fa27b5b
```

All proposed repository changes in successor PR #233 were rebuilt directly on that exact current-main baseline rather than carrying a stale branch forward.

Observed open implementation issues after the audit split:

- #154 — Black Man album: current-policy **artifact** completion remains open;
- #232 — future current-main guarded YouTube provider executor/adoption implementation; provider execution is not authorized by that issue.

Observed focused audit/hardening PR:

- #233 — release retrospective, live-state evidence, semantics/handoff/retirement hardening.

## Executive conclusion

The repository is materially stronger than the one-off operational path that actually released the Black Man album.

That creates one important asymmetry:

- **repository policy is safer than the historical release mechanism**;
- **remote provider state is newer than the repository’s previous current-state document**;
- **artifact provenance is stricter than the bytes that were historically uploaded**.

The correct response is not to erase any of those facts. The repository must represent all three dimensions separately:

1. current supported code/runtime;
2. exact artifact provenance level;
3. observed live provider state.

PR #233 implements that separation for the Black Man target and turns the release failures into durable rules/tests.

## 1. Repository operating model

### Good / current

`AGENTS.md` now has the right durable model:

- `main` is the only supported runtime/code baseline;
- closed/unmerged/superseded branches are evidence only;
- stable object identity is separate from attempt metadata;
- accepted/unknown provider outcomes block blind replay;
- child operations preserve prior verified success;
- PowerShell must orchestrate one repository-owned provider implementation;
- repository implementation, artifact completion and provider rollout are separate closure states.

This model directly addresses multiple failures observed during the Black Man release.

### Gap found

The Windows handoff supplement was still too generic for the actual chat/client failure mode. It did not explicitly require:

- one executable block only;
- ordinary full-block Ctrl+C/Ctrl+V safety;
- no adjacent pseudo-output blocks;
- no raw description bodies in PowerShell;
- no manual repair of `\_` / `\:` chat escapes;
- downloadable `.ps1` fallback when inline serialization is unreliable;
- no direct provider HTTP client hidden in generated shell/Python wrappers.

PR #233 adds those exact rules and regressions.

## 2. YouTube / Legendary Poet

### Current supported repository implementation

Current `main` already has strong local/provider-inert primitives:

- exact project/account/channel identity gate;
- quality-master-bound timing/render/package chain;
- source-first YouTube copy authoring;
- media-derived chapters tied to exact package evidence;
- stable same-media upload identity;
- local upload `plan/status/abandon` only;
- no supported current-main provider execute command.

### Observed live provider state

The historical media target now exists publicly as:

```text
video_id = x-puy27S2qs
media_sha256 = sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0
visibility = public
```

Custom thumbnail, both intended playlist memberships and a top-level comment were verified during the release session. AI-use disclosure was positively observed in YouTube Studio even though the Data API omitted the corresponding field from readback.

PR #233 records this live state and prevents future agents from assuming that “no v2 stable journal” means “no remote video exists.”

### Artifact/provider conflict that must remain explicit

The public video uses the historical pre-#213 MP4. Issue #154 correctly says that those bytes do not satisfy the newer accepted-quality-master provenance contract.

Therefore:

```text
provider rollout = verified public
current-policy artifact completion = not proven
```

Do not reupload to make those two labels match. A future artifact rerender, if/when exact accepted masters become available, creates a separate replacement/migration decision rather than an automatic overwrite.

### P0 remaining implementation gap

Issue #232 is now the exact owner for a future reusable provider executor. It must add read-only adoption of existing targets before upload execution, then separately journal upload/metadata/thumbnail/playlist/publication/comment child operations.

No canary/provider write is authorized by #232 itself.

## 3. YouTube failure taxonomy captured from the release

The release exposed four provider/verification defects that deserve reusable semantics:

1. **tag order** — provider returned the same values reordered; raw list equality was wrong;
2. **optional status observability** — missing `containsSyntheticMedia` readback is not equivalent to false;
3. **eventual playlist readback** — an accepted insert was absent from immediate readback but later proved present;
4. **historical remote identity adoption** — a stable local journal can be absent even when the provider target already exists.

PR #233 adds pure provider-free helpers/tests for the first three and documents the required adoption contract for #232.

## 4. YouTube description/editorial state

### Good / current

#214 replaced the stale multi-version description branch with one canonical source-first body and a media-derived chapter placeholder. It correctly keeps review planning provider-inert.

### Drift requiring caution

The live provider description was changed successfully during the release through the earlier #197-era v3 workflow. #197 is now superseded by #214.

This is not evidence that the live description is wrong; it means its equivalence to a **future current-policy rendered description for the same exact media bytes** has not been proved.

Future agents must use read-only comparison before deciding whether any metadata mutation is needed. “Repository copy changed” is not itself a provider-update requirement.

## 5. YouTube artwork/thumbnail process

The final provider thumbnail is verified present and its source input SHA is recorded.

The creative workflow revealed a separate tool-selection defect: non-generative compositing was repeatedly requested while image generation was still invoked during some iterations. Later the operator explicitly requested generation for isolated typography variants, which was a different permission.

Durable lesson:

- generation permission is component/task-specific;
- “do not generate/redraw this source” means preserve those source pixels and use deterministic compositing;
- generated typography may be combined with an original portrait only through declared deterministic composition when that is what the operator requested.

This belongs in future media/artwork workflow design; it is not a reason to modify the already verified remote thumbnail.

## 6. Telegram / Lordchrist legacy publisher

Current operational state remains coherent:

- legacy quote publisher is the live path;
- reviewed durable state includes verified posts 1470, 1472 and 1473;
- concurrency/state-writer rules are hardened;
- intent-before-send, exact-current-main gates, outcome archives and reconciliation semantics exist.

No Black Man work requires modifying this subsystem.

Risk to avoid: do not let a generic YouTube hardening change broaden into shared provider/runtime refactoring that destabilizes the live Telegram writer.

## 7. Telegram / Lordchrist research-v2

Repository implementation is complete but provider-inert. No research sender/scheduler is activated by current state.

No conflict with Black Man work. Keep it separate.

## 8. Telegram / Svodka

Repository implementation exists but provider writes remain disabled and no live release/ledger is authorized by current state.

No conflict with Black Man work. Keep it separate.

## 9. Telegram runtime / dependency supply chain

The production Telegram closure is exact-version/hash locked and intentionally excluded from routine independent Dependabot edits. Recent maintenance work proved that transitive lock updates must remain atomic.

No changes are required from the Black Man release audit. Do not couple YouTube semantics work to the Telegram dependency lock.

## 10. VK

Supported current capability remains the guarded postponed wall text-edit contract. Historical browser/internal-web VK Audio families are retired/experimental evidence.

No changes are required from this audit.

## 11. Local MP3

Supported capability remains read-only intake/manifest. No current rewrite/upload mutation is implied by Black Man work.

No changes are required from this audit.

## 12. GitHub governance

PR #230 closed the current evidence gap while this audit was in progress.

Observed 2026-08-09 state now records:

- `main` branch object `protected=false` at probe time;
- repository ruleset count `0` at probe time;
- Dependency Graph policy-enabled for the public repository;
- documented SBOM REST generation surfaces returned 404 at the read-only probe points.

These are observed point-in-time facts, not permanent assumptions.

## 13. Branch and ownership audit

The audit itself encountered a live example of why current-main ownership discipline matters:

- initial retrospective draft #231 started from `main@69682b09...`;
- independent PR #230 was the active writer for `current-state.md` and advanced main;
- #231 was not merged/rebased by pretending its old base was current;
- its unique work was rebuilt on `main@4625b872...` as #233;
- #231 was closed without merge and its branch was aligned back to current main.

This is the correct pattern for future multi-agent work.

## 14. Priority map after this audit

### P0

- Merge #233 only after exact-current-main CI/review is green.
- Keep `x-puy27S2qs` collision-blocking for media `e5450342...`.
- Keep #154 artifact-open until exact current-policy masters are available and rerender evidence exists.
- Implement #232 before any future automated YouTube provider write.

### P1

- Add existing-target adoption to stable YouTube state under #232.
- Implement durable child-operation journals for thumbnail/playlist/publication/comment rather than one-off wrappers.
- Add field-specific readback policies where provider API observability is incomplete.
- Perform a future read-only live-description/current-policy comparison only when the exact media/package basis is available.

### P2

- Record comment pin only if operator UI evidence confirms it.
- Consider a dedicated media-artwork non-generative composition contract if this workflow repeats across releases.

## 15. Explicit non-actions

This audit intentionally does **not**:

- reupload or replace the Black Man video;
- edit its public metadata again;
- reapply its thumbnail;
- reinsert playlist memberships;
- republish/toggle visibility;
- create another comment;
- claim the comment is pinned;
- close #154;
- activate #232 provider writes;
- revive #171/#197;
- modify Telegram/VK provider state.

The correct repository endpoint of this audit is documentation, pure provider semantics, regression coverage, explicit retirement state and a focused future implementation issue.