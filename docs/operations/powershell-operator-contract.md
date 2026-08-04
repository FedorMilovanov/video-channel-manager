# PowerShell operator contract

Updated: 2026-08-04  
Owner: Wave 5 / issue #72

## Supported surface

The only supported production PowerShell entrypoint is:

```powershell
scripts/operator/Invoke-VideoManager.ps1
```

The complete reviewed surface contains 23 `.ps1` files:

- 1 `supported` manifest-driven operator;
- 3 `compatibility_only` non-provider-write wrappers;
- 19 `retired` historical provider-write wrappers.

The registry also binds the single Pester `.ps1` test file, so every tracked PowerShell file is classified or explicitly test-only.

Every other tracked `.ps1` is classified in `scripts/operator/powershell-wrappers.json` as either:

- `compatibility_only` — non-provider-write developer/read-only convenience;
- `retired` — historical provider-write path that stops before credential lookup or child execution.

A new unclassified `.ps1`, duplicate registry path, invalid status, or canonical UTF-8/LF wrapper digest change fails CI. Canonical wrapper digests remain stable across Windows CRLF and Linux LF checkouts.

## Exact invocation

The supported entrypoint requires:

- exact request path;
- expected request SHA-256;
- exact output directory;
- optional explicit Python path;
- separate `-EnableProviderWrites` switch for apply mode.

Example plan-only invocation:

```powershell
$Request = "data/operator/request.json"
$Sha256 = (Get-FileHash -LiteralPath $Request -Algorithm SHA256).Hash.ToLowerInvariant()

./scripts/operator/Invoke-VideoManager.ps1 `
  -RequestPath $Request `
  -RequestSha256 $Sha256 `
  -OutputDirectory "data/operator/run-001"
```

No newest-file, glob, or `LastWriteTime` selection is supported.

## Request schema

```json
{
  "schema_name": "video-manager.operator-request",
  "schema_version": 1,
  "mode": "plan",
  "manifest_path": "data/operator/manifest.json",
  "manifest_sha256": "<64 lowercase hex>",
  "confirm_manifest_sha256": "<same digest>",
  "confirm_project_key": "legendary-poet",
  "confirm_community_id": 235216998,
  "confirm_owner_id": -235216998,
  "confirm_source_snapshot_id": "<exact snapshot ID>",
  "confirm_operation_count": 0
}
```

Supported modes:

- `plan` — validates request and manifest and writes evidence without launching a child;
- `dry-run` — executes one allowlisted safe-read CLI command;
- `reconcile` — executes one allowlisted safe-read reconciliation command;
- `apply` — requires an `ambiguous_mutation` manifest, exact project confirmations, positive operation count, non-CI environment, and `-EnableProviderWrites`.

The operator performs no automatic retry.

## Manifest schema

```json
{
  "schema_name": "video-manager.operator-manifest",
  "schema_version": 1,
  "project_key": "legendary-poet",
  "community_id": 235216998,
  "owner_id": -235216998,
  "source_snapshot_id": "<exact snapshot ID>",
  "operation_count": 0,
  "operation_class": "safe_read",
  "provider_mutation": false,
  "entrypoint_id": "video-manager-cli",
  "arguments": ["vk", "scan", "--account", "legendary-poet", "--community", "235216998"]
}
```

Project identities are hard-bound:

- `legendary-poet` → community `235216998`, owner `-235216998`;
- `lord-god-strength` → community `60805374`, owner `-60805374`.

The request must repeat the exact project, community, owner, non-empty snapshot, operation count, and manifest digest. JSON IDs/counts must be integer values rather than numeric strings, arguments must be a non-empty string array, and output artifacts may not overwrite the request or manifest.

## Structured evidence

Every accepted request writes UTF-8 without BOM:

- `preflight-summary.json`;
- `result.json`;
- `stdout.log` and `stderr.log` when a child starts.

Human console text is informational only. Control flow uses native exit codes and structured JSON fields.

Result statuses:

- `planned`;
- `succeeded`;
- `failed` for a failed safe read;
- `unknown_requires_reconciliation` for a nonzero ambiguous mutation;
- `rejected` for preflight/contract failure.

A nonzero ambiguous mutation is never marked retry-safe and is never replayed automatically.

## Interpreter contract

The shared module resolves only Python 3.11, 3.12, or 3.13 from:

1. an exact explicit path;
2. the repository virtual environment;
3. `python3` or `python` from the executable search path.

When an explicit Python path is supplied, fallback is disabled: that exact file must resolve to a supported interpreter.

The old divergent `py -3.11`, PATH-installed `video-manager`, user-home hardcodes, and nested `pwsh` orchestration are not part of the supported surface.

## CI boundary

CI exercises:

- Python static inventory and SHA gates;
- Windows PowerShell 5.1 Pester tests;
- PowerShell 7 on Windows;
- PowerShell 7 on Linux;
- request/manifest digest failures;
- project mismatch;
- UTF-8 without BOM;
- native nonzero exit codes;
- CI apply prohibition;
- retired-wrapper rejection.

Development and CI perform zero VK and YouTube provider writes.
