# Lord God sermon-month package incident — 2026-08-05

Project: `lord-god-strength`  
Evidence source: operator chat transcript `Вставленный текст(290).txt`  
Archive status: `documentation_only_non_executable`  
Execution authority: `false`  
Provider-write authority: `false`

## Why this incident is retained

This incident shows how a workflow can descend into repeated ZIP, PowerShell, and Python rewrites when package readiness is described more strongly than the evidence supports.

The transcript begins with an editorial/preview package for ten Legendary Poet article posts. The handoff correctly acknowledged that the current repository had no connected production provider adapter for that path. Later, after the operator reported that the package did not provide a usable next step, a separate Lord God sermon-month v2 package was generated with a standalone PowerShell launcher and Python publisher. Its local self-test passed, but the read-only VK permission preflight falsely rejected a valid management token because it used `groups.get(filter=admin)` instead of `filter=moder`.

A v3 package corrected the permission query, normalized response shapes, retained canary-first execution, and wrote per-operation result files. The transcript later reports `FINAL_OK — 30/30`, first post `-60805374_12482`, last post `-60805374_12511`, daily at 20:00 Moscow time from 6 August through 4 September 2026.

The original v3 result directory, manifests, operation result files, and exact provider readbacks were not supplied to this repository. Therefore the later outcome is classified as `operator_transcript_reported`, not independently re-verified live state.

## Permanent boundary

- Do not rerun sermon-month v1, v2, or v3.
- Do not copy their historical PowerShell or Python into `scripts/` or `src/`.
- A local preview, a ZIP, or a `FINAL_OK` line is not sufficient batch evidence.
- The supported repository operator and exact project binding remain mandatory for future write workflows.
- A future sermon scheduling workflow must start from fresh read-only wall inventory and a separately reviewed exact-ID plan.

See:

- [`TIMELINE.md`](TIMELINE.md)
- [`LESSONS.md`](LESSONS.md)
- [`REPRESENTATIVE-SNIPPETS.md`](REPRESENTATIVE-SNIPPETS.md)
- [`SOURCE-METADATA.json`](SOURCE-METADATA.json)
