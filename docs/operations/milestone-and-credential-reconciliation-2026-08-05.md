# Milestone and credential reconciliation — 2026-08-05

Issue: #122  
Baseline: `main@0552b026256fd80cb5fa2857ef3bfb3d2f9bffa1`  
Provider queries: `0`  
Provider writes: `0`  
Write plans: `0`

## Credential semantics

The configured VK credential is one **user access token source**. It may enumerate and access multiple communities that the same VK user is allowed to manage.

Current configured source:

- external file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`;
- key: `VK_API_TOKEN`;
- local stored VK alias where used by the CLI: `legendary-poet`.

The VK alias names the stored credential. It is not a project selector and it does not mean that each community requires a separate token.

Project isolation is provided by exact operation identity:

- `project_key`;
- VK `community_id`;
- VK `owner_id`;
- exact manifest, plan, journal, result, and link profile.

The strings `fedor-milovanov` and `legendary-poet` in the YouTube sections are **YouTube OAuth account aliases**. They select separately stored YouTube OAuth authorizations and must resolve to the exact expected YouTube channel ID.

Therefore the correction in issues #31 and #32 remains valid: their YouTube OAuth alias is `fedor-milovanov`. This does not imply a second VK token.

## Stale milestone reconciliation

### #2 — YouTube OAuth and read-only inventory

Disposition: completed in the current supported architecture.

Implemented evidence includes:

- desktop OAuth flow and refresh-token storage outside the repository;
- local YouTube account aliases;
- exact channel discovery and explicit channel selection;
- paginated channel, uploads, playlist, and membership inventory;
- provider raw payload retention and deterministic revisions;
- immutable `AuditPackage` JSON export;
- retry, pagination, OAuth, token-store, and client tests.

The original DB-centric wording was replaced by immutable export artifacts and exact rerunnable read-only scans. No provider mutation is implied.

### #3 — deterministic audits and external-AI packages

Disposition: superseded by the current specialized audit/editorial architecture.

The repository now has versioned `AuditPackage`, deterministic YouTube copy validators, unified content validation/rendering, VK catalog/editorial audits, exact comparison reports, and operational evidence packages. The originally proposed generic `audit run/report/export --profile ...` command family is not a supported current contract and is not silently represented as completed.

No active live operation depends on keeping the broad milestone issue open.

### #4 — safe YouTube playlist and metadata execution

Disposition: superseded, with the genuinely unimplemented playlist portion preserved in issue #123.

Implemented supported paths include:

- ChangePlan schema validation and preview;
- exact-channel guarded YouTube description writes;
- guarded top-level comment writes;
- explicit write scope, lock, locked re-preflight, backup, journal, bounded retry, postflight, recovery, and no-blind-replay behavior.

Not implemented as one supported generic executor:

- playlist create/update;
- membership add/remove/reorder;
- generic plan import/approve/execute/status lifecycle for those operations.

Issue #123 owns that deferred product scope and authorizes no provider write.

### #5 — VK organizer, comparison, and resumable transfer

Disposition: completed/superseded by the current guarded architecture and project-bound operational owners.

Implemented evidence includes:

- VK user-token validation and managed-community enumeration;
- read-only community/video/album/membership inventory;
- snapshot and plan comparison;
- exact project identity and cross-platform mapping rules;
- resumable upload lifecycle, media authority, processing readback, wall separation, durable journals, and no-blind-replay controls;
- guarded VK catalog, metadata, thumbnail, wall, and article workflows.

The remaining live truth is not a missing milestone implementation. It is project-bound reconciliation and later reviewed operations owned by #31, #32, #33, #38, #99, and #119.

## Completed cleanup issue

### #37 — Shorts wall cleanup after post 12400

Disposition: completed historical operation.

Canonical repository memory records:

- 34 reviewed low-view Shorts were replaced;
- the associated generated wall posts were removed;
- protected post `12400` remained present;
- no broad cleanup permission was implied;
- the historical reset executor is retired and must not be rerun.

Issue #37 is no longer an active operational owner. Any future cleanup requires a new exact reviewed object set and separate authorization.

## Active graph after reconciliation

Active live and gate owners remain:

- #31 — Lord God long-form read-only reconciliation;
- #32 — Lord God Shorts/Clips read-only reconciliation;
- #119 — Legendary Poet Shorts/Clips read-only reconciliation;
- #38 — shared provider-mode/final-type contract;
- #33 — later Lord God video catalog/publication gate;
- #99 — separate Legendary Poet article-wall workflow;
- #123 — deferred YouTube playlist mutation contract;
- #64 — canonical roadmap.

Stale milestones #2–#5 and completed cleanup #37 must not be used as parallel active owners.
