# Package A runbook — Wave 9A, Wave 9B and Wave 10

Package A is a provider-read-only control plane for exact local-ledger reconciliation, recovery decision support, and static operator reporting.

It does not query YouTube or VK. It does not create a `WavePlan`, reserve an upload, upload media, edit metadata, save a thumbnail, publish to a wall, or authorize any provider mutation. Package A does not authorize provider writes.

## Evidence levels

Package A can prove only what its supplied immutable inputs prove.

- `read_only_reconciliation` — exact local records and bounded provider snapshots were structurally reconciled.
- `read_only_decision_support` — the recovery ledger derived safe next-action classes from that reconciliation.
- `read_only_control_plane` — the operator board rendered those same immutable objects without adding authority.

Green CI proves the contracts and fixtures. It does not prove current live provider state.

## Supported entrypoint

```powershell
video-manager-package-a run `
  .\package-a-request.json `
  --input-root .\package-a-input `
  --output-directory .\package-a-output `
  --evaluated-at 2026-08-05T01:00:00Z
```

Verification:

```powershell
video-manager-package-a verify .\package-a-output
```

Schema export:

```powershell
video-manager-package-a schema --output-directory .\schemas\package-a
```

The CLI intentionally has no `--enable-provider-writes` option.

## Required inputs

Every path is relative to one explicit `--input-root`. Every file is bound by a lowercase SHA-256 in `package-a-request.json`.

Required:

1. `BoundedSourceSnapshot` JSON;
2. `BoundedTargetSnapshot` JSON;
3. one local-record source:
   - canonical `LocalReconciliationRecord[]` JSON; or
   - one SQLite ledger plus an explicit reviewed `SqliteLedgerContract`.

The source and target snapshots must:

- bind the same exact registered project;
- cover the same sorted source-ID set;
- be within the configured freshness window;
- have valid snapshot IDs and self-digests;
- represent complete bounded coverage for the declared surface.

## Canonical JSON local records

The JSON file is an array of strict `LocalReconciliationRecord` objects. It must contain exactly one row for every bounded source ID.

Accepted local stages are defined by the Wave 9 contract. Accepted, processing, verified, intent-persisted and unknown stages never become replay authorization merely because a later readback is empty.

## Reviewed SQLite contract

Package A never guesses a table, column, or status mapping.

Example request fragment:

```json
{
  "input_mode": "sqlite_ledger",
  "sqlite_ledger": {
    "path": "inputs/upload-ledger.db",
    "sha256": "<exact-lowercase-sha256>"
  },
  "sqlite_contract": {
    "table_name": "current_state",
    "source_video_id_column": "source_id",
    "stage_column": "stage",
    "remote_id_column": null,
    "remote_owner_id_column": "owner_id",
    "remote_object_id_column": "object_id",
    "evidence_digest_column": "evidence_digest",
    "stage_map": [
      {"raw_stage": "accepted", "stage": "accepted"},
      {"raw_stage": "failed_before_upload", "stage": "pre_dispatch_failed"},
      {"raw_stage": "planned", "stage": "never_dispatched"},
      {"raw_stage": "processing", "stage": "processing"},
      {"raw_stage": "verified", "stage": "verified"}
    ]
  }
}
```

SQLite safety rules:

- database URI uses `mode=ro`;
- the connection enables `PRAGMA query_only = ON`;
- table and column names must be simple reviewed identifiers;
- every raw status must appear in the explicit stage map;
- the selected query must return exactly one current-state row per source ID;
- duplicate source rows, partial remote identities, unknown statuses and wrong types fail closed;
- the database file SHA-256 is verified before opening.

A history/event table is not a current-state table unless a reviewed view or query contract reduces it to exactly one row per source before Package A is run.

## Wave 9A output

`reconciliation-evidence.json` classifies each bounded source as:

- `present`;
- `duplicate`;
- `missing`;
- `unknown`;
- `requires_attention`.

Package A never infers absence from incomplete coverage. Exact reserved-ID coverage cannot prove absence for sources without known remote IDs.

## Wave 9B recovery decision ledger

`recovery-decisions.json` maps reconciliation evidence to only four decisions:

- `no_action` — exactly one verified remote object is present;
- `reconcile_only` — processing, unknown, binding mismatch or another unresolved state requires another bounded readback;
- `blocked` — duplicate or conflicting remote identity must be reviewed and cannot be replayed;
- `eligible_after_separate_review` — absence is proven and no mutation may have reached the provider.

`eligible_after_separate_review` is not a write plan. It carries:

- `provider_write_authorized=false`;
- `automatic_execution=false`;
- `separate_review_required=true`.

Separate review is mandatory before any later exact-ID write plan can be prepared. A later mutation requires a different reviewed exact-ID plan under the permanent production operator contract.

## Wave 10 operator board

Package A writes:

- `operator-board.json` — immutable machine evidence;
- `operator-board.md` — reviewable text report;
- `operator-board.html` — static local presentation with no JavaScript, forms, provider clients or mutation controls.

The board has no independent state. It binds the reconciliation and recovery digests and renders their exact totals and item decisions.

Board priority is fail-closed:

1. any duplicate/conflict → `blocked`;
2. any unknown/processing/attention item → `reconciliation_required`;
3. any proven missing item → `separate_review_required`;
4. otherwise → `complete`.

## Output verification

`run-summary.json` binds the project, request digest, reconciliation digest, recovery digest, board digest and SHA-256 of every generated board/evidence file.

Run `video-manager-package-a verify` after copying, restoring, or handing off an output directory. Any changed file, mismatched digest or cross-project object fails verification.

## Recovery and rollback

Package A has no remote rollback because it performs no provider mutation.

Local recovery rules:

1. Never edit an evidence JSON to “fix” a status.
2. Preserve the rejected request and input files unchanged.
3. Correct the upstream snapshot, reviewed SQLite mapping, or current-state export.
4. Generate a new request with new exact file SHA-256 values.
5. Write outputs into a new directory; do not overwrite a reviewed prior run.
6. Verify the new output directory.
7. Compare old and new immutable digests in the owning issue.

For `unknown`, `processing`, accepted-but-not-visible, or binding mismatch states, obtain another fresh bounded read-only provider snapshot. Do not retransmit.

## Project-specific live handoff

Actual fresh conclusions remain owned by:

- issue #31 — Lord God long-form ledger reconciliation;
- issues #32 and #38 — Legendary Poet Shorts/Clips reconciliation;
- issue #33 — any later separately reviewed catalog/publication or canary gate.

Historical retained counts may seed test fixtures or review context, but they are not substitutes for fresh local ledgers and provider snapshots.

## Historical archive boundary

`docs/history/operational-attempts/` contains documentation-only snapshots of failed, partial, superseded and successful experiments.

- archive files are Markdown or manifest JSON only;
- fenced historical code is not a supported entrypoint;
- no archived package, V1/V2/V3/V4 launcher, “48 clips” workflow or VK Audio browser experiment may be executed from the archive;
- fresh operational state remains in current evidence and owning issues, never in history files.
