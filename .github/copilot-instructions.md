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

Resi/DASH has one explicit split-destination exception: the completed `<TITLE> - FULL.mp4` master belongs in `C:\Users\Fedor\Downloads`; source receipt/result JSON, generated handoff/watcher control files, logs/state, and exact-trim output remain in repository `operator-output` unless the user chooses another location.

## Self-contained PowerShell

Every copy-paste block must work from an arbitrary current directory.

- Set `$ErrorActionPreference = "Stop"`.
- Define every variable used in the same block; never depend on variables from an earlier message/session.
- Use exact absolute paths or paths derived from `$Repo`, `$Downloads`, and `$OperatorOutput`.
- Use `-LiteralPath` for known paths and validate required inputs with `Test-Path -LiteralPath ... -PathType Leaf`.
- Invoke the exact full entrypoint path. Repository scripts resolve siblings from `$PSScriptRoot`.
- Never choose an artifact by `LastWriteTime`, newest ZIP, or broad wildcard. If discovery is unavoidable, require exactly one match and fail on zero/multiple matches.
- For ZIP handoffs, show exact extraction root, exact inner package root, and exact entrypoint.
- On success, print every exact output path. If one human-inspected file is the next action, place it in the contract-defined destination and select that exact file in Explorer.
- Do not open Explorer or select a stale artifact after failure.

Undefined inherited variables such as `$wave`, `$package`, `$zip`, or `$out` are prohibited.

### Copy/paste serialization contract

Assume the operator uses ordinary **Ctrl+C → Ctrl+V on the entire shown command block**. The handoff must be safe under exactly that behavior.

- Show at most **one executable fenced block** for one requested operator action.
- Do not place a second fenced block containing illustrative console output, labels such as `Channel:` / `Video:` / `Before SHA:`, or pseudo-commands immediately after the executable block. Describe expected success markers in prose instead.
- Do not put long YouTube descriptions, comments, JSON payloads, or other public copy directly into PowerShell for manual pasting. Store the content in an exact repository/operator file and pass only its path/ID to the repository entrypoint.
- Literal chat-escape artifacts such as `\_` or `\:` inside an executable command are a handoff serialization defect. The operator must not be asked to repair them manually.
- If the chat/client cannot preserve the command byte-for-byte, deliver an exact `.ps1` file artifact and give one short invocation line instead of repeatedly emitting increasingly complex inline commands.
- User-visible sample output is never executable material and must not be formatted in a way that invites copying it into PowerShell.

## Provider-capable PowerShell

PowerShell is orchestration, not a second provider implementation.

- A provider-capable block must call a **current-`main` repository-owned entrypoint**.
- Do not embed `googleapis.com`, VK, Telegram, or other provider HTTP requests in generated PowerShell or temporary Python code as a shortcut.
- Do not import provider helpers from a closed, unmerged, superseded, or retired worktree/branch merely because credentials are convenient there.
- Provider pagination, mutation retry policy, effect journaling, convergence/readback, idempotency, and postflight belong in reviewed repository code with regression tests.
- If current `main` has no supported executor for the requested provider operation, stop and implement/review that executor rather than generating an external direct-write script.

## Operator outbox

The default human-facing destination is:

```text
C:\Users\Fedor\Projects\video-channel-manager\operator-output
```

Prefer flat descriptive filenames. Internal journals/state stay in their contract-defined locations; only the artifact intended for inspection/upload/return belongs in the outbox. The Resi `FULL.mp4` exception above is deliberate: the potentially multi-gigabyte retained master stays in Downloads while its compact provenance/control artifacts stay in the outbox.

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

An accepted provider mutation followed by an empty/stale readback is not proof of absence. Preserve the returned remote object ID when available, classify the effect as `may_exist`, and reconcile read-only before any repeat mutation.

## Encoding

For Russian Windows artifacts:

- `.ps1` and human-readable `.txt`: UTF-8 with BOM when Windows tooling requires it;
- HTML: explicit UTF-8 charset;
- JSON: valid UTF-8 JSON without comments/wrappers.

Encoding never relaxes exact-file, SHA-256, manifest, or target identity checks.
