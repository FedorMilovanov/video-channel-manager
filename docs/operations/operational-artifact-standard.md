# Operational artifact and handoff standard

This standard applies to every ZIP, PowerShell launcher, manifest, or executor handed to an operator. It is supplemented by [`operational-package-acceptance.md`](operational-package-acceptance.md), which defines truth levels and provider-readiness claims.

## Goals

An operational artifact must be:

- self-locating;
- deterministic;
- restartable;
- inspectable;
- safe against duplicate writes;
- explicit about covered and uncovered provider surfaces;
- executable from the documented path without guessing.

## Required package structure

Preferred provider-write handoff ZIP:

```text
package.zip
├── run-operation.ps1
├── manifest.json
├── README.txt
└── SHA256SUMS.txt
```

The PowerShell launcher invokes the installed repository-owned implementation. A generated standalone `executor.py` beside the ZIP is not part of the supported provider-write structure.

A nested root is allowed only when the documented launch command includes it exactly. Flat ZIPs are the default for user handoffs.

The package must not contain:

- tokens or OAuth client secrets;
- downloaded media unless explicitly intended and reviewed;
- local SQLite ledgers;
- provider response logs containing credentials;
- `.git` directories;
- absolute-path copies of local ignored data;
- duplicate package root directories.

## Required launcher behavior

The PowerShell entrypoint must:

1. set `$ErrorActionPreference = "Stop"`;
2. resolve `$PSScriptRoot` and locate sibling files relative to itself;
3. validate every required file before network work;
4. print source and target identities;
5. print manifest SHA-256;
6. print mode: read-only, dry-run, canary, or execute;
7. print ledger and result paths;
8. avoid dependence on the caller's current directory;
9. preserve successful intermediate artifacts;
10. stop on an unknown write outcome and explain reconciliation;
11. return a non-zero exit code on failure;
12. print a final machine-readable summary path.

## Required manifest fields

At minimum:

```json
{
  "schema_name": "...",
  "schema_version": "...",
  "created_at": "timezone-aware timestamp",
  "source": {
    "platform": "youtube",
    "channel_id": "exact ID",
    "url": "canonical URL",
    "snapshot_id": "exact snapshot ID"
  },
  "target": {
    "platform": "vk",
    "community_id": "60805374",
    "owner_id": "-60805374",
    "url": "https://vk.com/gospod_bog",
    "snapshot_id": "exact snapshot ID"
  },
  "coverage": {
    "included_surfaces": [],
    "excluded_surfaces": [],
    "known_limitations": []
  },
  "operations": []
}
```

Every operation must include:

- exact source ID;
- exact source URL;
- title;
- duration when available;
- target identity;
- decision/evidence;
- ordinal or stable operation ID;
- expected postcondition.

## Required ledger states

Use explicit states rather than one generic success flag:

- `planned`
- `preflight_present`
- `downloading`
- `downloaded`
- `upload_url_acquired`
- `uploading`
- `accepted`
- `processing`
- `verified`
- `rejected`
- `unknown`
- `skipped_already_present`

An `unknown` state is terminal for automatic retry until reconciliation has inspected the provider and the ledger.

## Idempotency requirements

- One source platform ID maps to at most one accepted target ID in a ledger.
- Before requesting an upload URL, record intent.
- After provider acceptance, persist the returned target ID immediately.
- Before every resume, reconcile `accepted`, `processing`, and `unknown` records against live target state.
- Never infer failure solely from a local timeout after upload bytes may have reached the provider.
- Never re-download a verified local source file with a matching fingerprint.

## Inventory and matching requirements

- Verify source identity before scanning.
- Store expected and observed channel IDs.
- Use canonical page membership for public content surfaces.
- Use provider APIs for metadata and exact writes.
- Record endpoint coverage explicitly.
- Ordinary VK videos and VK Clips are separate surfaces.
- Titles are comparison attributes, not identities.
- Exact source URLs/IDs are preferred evidence.
- Ambiguous matches never enter an upload manifest.

## Required outputs

Every execution must write:

- immutable input manifest copy;
- manifest SHA-256;
- SQLite ledger or equivalent durable journal;
- per-attempt append-only log;
- result JSON;
- unresolved/unknown report;
- exact verified target IDs;
- resume command or explicit statement that resume is unsafe.

## Bundle verification

Before handoff, run:

```powershell
python -m video_channel_manager.tools.operational_package_acceptance `
  .\path\package.zip `
  --entrypoint run-operation.ps1 `
  --require manifest.json `
  --require README.txt `
  --require SHA256SUMS.txt `
  --require-flat
```

The repository-owned acceptance verifier first runs the stable digest-bound structural verifier, then validates manifest truth level, package kind, exact project binding, supported entrypoint, adapter readiness, canary dependency, per-operation results, and unknown-outcome reconciliation. A passing result always reports `provider_writes_authorized=false`; structural acceptance is not a write authorization.

The verifier must pass before sharing the archive and launch command.

## Handoff template

Every user-facing handoff should state:

```text
Purpose:
Scope/count:
Manifest SHA-256:
Archive SHA-256:
Source identity:
Target identity:
Covered surfaces:
Excluded surfaces:
Exact command:
Ledger path:
Result path:
Canary behavior:
Resume behavior:
Unknown-outcome behavior:
Expected final line:
```

## Evidence wording

Use `editorial_prepared`, `preview_validated`, `self_tested`, `canary_verified`, or `batch_verified` exactly. Do not call a package operational, automatic, or complete at a stronger level than retained evidence proves. A standalone generated Python executor is not a connected production adapter.

## Completion definition

An operation is complete only when:

1. every intended item is either verified, skipped as already present, or explicitly unresolved;
2. there are no silent unknown outcomes;
3. target IDs and postconditions are recorded;
4. the result JSON reports final counts;
5. the current-state document is updated.
