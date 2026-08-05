# Representative non-executable snippets

These fragments are retained for learning only. They are not complete scripts and must not be copied into an operational package.

## PowerShell generation churn pattern

Historical shape:

```powershell
# NON-EXECUTABLE HISTORICAL SHAPE
Expand-Archive -LiteralPath $Zip -DestinationPath $Downloads -Force
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "$Folder\RUN-SERMON-MONTH.ps1"
```

The command is not inherently wrong. The failure was architectural: the ZIP contained another standalone provider implementation, so each provider-contract correction produced a new v2/v3 package.

Required future shape:

```powershell
# PSEUDOCODE — parameter names intentionally omitted
$Operator = Join-Path $RepositoryRoot "scripts/operator/Invoke-VideoManager.ps1"
# validate exact request, manifest digest, project identity, result path
# invoke the repository operator and propagate its exit code
```

PowerShell owns location, validation, presentation, and child-process semantics. It does not reimplement provider permission or write logic.

## Permission-filter defect

Rejected historical assumption:

```python
# NON-EXECUTABLE ANTI-PATTERN
vk_call("groups.get", filter="admin")
```

Supported read-only enumeration concept:

```python
# NON-EXECUTABLE CONTRACT EXCERPT
vk_call("groups.get", filter="moder", extended=1, count=1000, offset=0)
```

The returned list still does not select a project. Exact registered `project_key`, `community_id`, and `owner_id` must match separately.

## Stable result boundary

A useful per-operation result shape:

```json
{
  "operation_id": "exact stable ID",
  "project_key": "lord-god-strength",
  "stage": "verified | unknown_requires_reconciliation | rejected",
  "target_id": "exact ID or null",
  "expected_postcondition": "versioned object",
  "observed_postcondition": "versioned object or null",
  "provider_request_accepted": false,
  "automatic_retry_authorized": false,
  "result_sha256": "lowercase SHA-256"
}
```

A batch summary may aggregate these objects, but may not replace them.

## Truth-level declaration

```json
{
  "schema_name": "video-manager.operational-package-acceptance",
  "schema_version": "1.0",
  "package_kind": "provider_write_bundle",
  "evidence_level": "self_tested",
  "supported_entrypoint": "scripts/operator/Invoke-VideoManager.ps1",
  "provider_adapter_connected": true,
  "canary_required": true,
  "per_operation_results_required": true,
  "unknown_outcome_requires_reconciliation": true,
  "provider_writes_authorized": false,
  "automatic_execution": false
}
```

Even a structurally valid declaration does not authorize provider writes.
