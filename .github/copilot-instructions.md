# Windows operator handoff rules

`AGENTS.md` is the repository operating contract. This file adds only Windows/operator-handoff details and never authorizes provider writes.

Also follow `docs/operations/operator-output-handoff-rule.md`.

## Canonical local paths

Unless the user explicitly supplies another location:

```text
Repository:      C:\Users\Fedor\Projects\video-channel-manager
Downloads:       C:\Users\Fedor\Downloads
Operator output: C:\Users\Fedor\Projects\video-channel-manager\operator-output
```

Do not assume a downloaded or generated file is in the current shell directory.

## Self-contained PowerShell

Every copy-paste block must work from an arbitrary current directory.

- Set `$ErrorActionPreference = "Stop"`.
- Define every variable used in the same block; never depend on variables from an earlier message/session.
- Use exact absolute paths or paths derived from `$Repo`, `$Downloads`, and `$OperatorOutput`.
- Use `-LiteralPath` for known paths and validate required inputs with `Test-Path -LiteralPath ... -PathType Leaf`.
- Invoke the exact full entrypoint path. Repository scripts resolve siblings from `$PSScriptRoot`.
- Never choose an artifact by `LastWriteTime`, newest ZIP, or broad wildcard. If discovery is unavoidable, require exactly one match and fail on zero/multiple matches.
- For ZIP handoffs, show exact extraction root, exact inner package root, and exact entrypoint.
- On success, print every exact output path. If one human-inspected file is the next action, place it in `operator-output` and select that exact file in Explorer.
- Do not open Explorer or select a stale artifact after failure.

Undefined inherited variables such as `$wave`, `$package`, `$zip`, or `$out` are prohibited.

## Operator outbox

The default human-facing destination is:

```text
C:\Users\Fedor\Projects\video-channel-manager\operator-output
```

Prefer flat descriptive filenames. Internal journals/state stay in their contract-defined locations; only the artifact intended for inspection/upload/return belongs in the outbox.

A successful single-file handoff should end with the equivalent of:

```powershell
if (-not (Test-Path -LiteralPath $Result -PathType Leaf)) {
    throw "Expected output was not created: $Result"
}
Write-Host "OPEN/SEND THIS FILE: $Result"
Start-Process explorer.exe -ArgumentList "/select,`"$Result`""
```

## Handoff declaration

Before a provider-capable or multi-step command block, state concisely:

- outcome and evidence level;
- capability/transport for each phase;
- exact `project_key` and target identity when applicable;
- exact repository-owned entrypoint;
- provider-effect state;
- exact result/state/operator-output paths;
- postcondition and stop/reconcile behavior.

Do not repeat the full repository safety model from `AGENTS.md`.

## Failure handling

After a failure:

1. preserve exact machine-readable result/evidence;
2. classify provider effect (`impossible`, `confirmed_absent`, `may_exist`, `verified`);
3. make one falsifiable hypothesis;
4. run the smallest non-mutating probe;
5. patch repository-owned code plus regression coverage;
6. resume only the failed/unverified child operation.

Do not produce another ZIP/version family as the default diagnosis loop.

## Encoding

For Russian Windows artifacts:

- `.ps1` and human-readable `.txt`: UTF-8 with BOM when Windows tooling requires it;
- HTML: explicit UTF-8 charset;
- JSON: valid UTF-8 JSON without comments/wrappers.

Encoding never relaxes exact-file, SHA-256, manifest, or target identity checks.
