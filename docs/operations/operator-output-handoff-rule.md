# Operator output handoff rule

This rule exists to keep user-facing files easy to find during interactive Windows work. It supplements `AGENTS.md`, `.github/copilot-instructions.md`, and `operational-artifact-standard.md`; it does not change provider authorization or durable machine-state requirements.

## Canonical operator outbox

For Fedor's interactive Windows handoffs, the canonical user-facing outbox is:

```text
C:\Users\Fedor\Projects\video-channel-manager\operator-output
```

Repository-owned scripts and copy-paste PowerShell must derive it from the fixed repository root rather than from the caller's current directory:

```powershell
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$OperatorOutput = Join-Path $Repo "operator-output"
New-Item -ItemType Directory -Force -Path $OperatorOutput | Out-Null
```

`operator-output/` is local runtime output and must remain untracked.

## What belongs there

Any file that the operator is expected to open, inspect, upload manually, attach to chat, or use as the next handoff input must be written directly into `operator-output` unless the operator explicitly chooses another location.

Examples:

- read-only inventory/AuditPackage JSON intended for review;
- source manifests and timing manifests intended for review;
- chapter text, title/description text, thumbnails, artwork plans, and final preview media intended for operator use;
- diagnostic/result JSON the operator is asked to send back;
- generated handoff TXT/README files;
- final local packages intended for manual upload or inspection.

Internal durable state may remain in `data/`, `logs/`, journals, caches, databases, or build directories when those locations are part of the runtime contract. Do not duplicate an authoritative mutable ledger merely for convenience. Instead, place the operator-facing summary/result or an immutable exported copy in `operator-output`.

## Flat, obvious filenames

Prefer flat, descriptive filenames at the outbox root for the current handoff. Do not make the operator traverse timestamp trees just to find the requested file.

Good:

```text
operator-output\legendary-poet-black-man-source-scan.json
operator-output\black-man-album-status.json
operator-output\black-man-chapters.txt
operator-output\black-man-artwork-plan.json
operator-output\black-man-final.mp4
```

Avoid user-facing instructions such as "look somewhere under data/exports" or "find the newest JSON".

If multiple generations must coexist, include a deterministic run ID or explicit date in the filename and print the exact selected path. Never select by newest timestamp or broad wildcard.

## Mandatory command behavior

For every interactive operator-facing command or wrapper that creates a file:

1. define `$Repo` and `$OperatorOutput` in the same PowerShell block;
2. create the outbox if missing;
3. pass an explicit output path under the outbox whenever the CLI supports `--output`, `--result-output`, `--backup-output`, or equivalent;
4. never depend on the shell's current directory for the output destination;
5. after success, verify the exact file with `Test-Path -LiteralPath`;
6. print an unmistakable final line with the absolute path, for example `OPEN/SEND THIS FILE: C:\...`;
7. when the next operator action is to inspect or send one local file, select that exact file in Explorer after successful creation unless the user asked for non-interactive behavior;
8. if several files are required, open the outbox folder once and print the exact filenames;
9. on failure, do not open stale output from an earlier run;
10. never make the operator search for a file that the script itself can name exactly.

Example final handoff:

```powershell
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$OperatorOutput = Join-Path $Repo "operator-output"
$Result = Join-Path $OperatorOutput "legendary-poet-black-man-source-scan.json"
New-Item -ItemType Directory -Force -Path $OperatorOutput | Out-Null

video-manager youtube scan --account legendary-poet --channel UC-78ys2S3cQ3lpqgXfo-SvQ --output $Result

if (-not (Test-Path -LiteralPath $Result -PathType Leaf)) {
    throw "Expected output was not created: $Result"
}
Write-Host "OPEN/SEND THIS FILE: $Result"
Start-Process explorer.exe -ArgumentList "/select,`"$Result`""
```

The Explorer convenience step is local UI only. It does not authorize or perform any provider mutation.

## Agent handoff requirement

When an agent asks Fedor to run a command and then return a generated file, the agent must provide the output path itself. The agent must not require Fedor to infer repository location, search `data/`, inspect timestamps, or discover filenames manually.

If a tool lacks an explicit output option, the repository-owned wrapper should be improved so that a deterministic user-facing result can be placed in the outbox. Repeated manual searching is treated as a workflow defect, not as an operator task.
