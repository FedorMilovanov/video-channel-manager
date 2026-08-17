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

### Explicit Resi retained-master exception

For the supported Resi/DASH handoff, the operator has chosen a durable split destination:

```text
Retained FULL master: C:\Users\Fedor\Downloads\<TITLE> - FULL.mp4
Control/evidence:     C:\Users\Fedor\Projects\video-channel-manager\operator-output\...
```

The potentially multi-gigabyte retained `FULL.mp4` is therefore **not** an `operator-output` file. Resi source receipt/result JSON, generated handoff/watcher files, logs/state, and exact-trim output stay in `operator-output` unless the operator explicitly chooses another location. Receipt/result evidence must record the exact Downloads master path and SHA-256, and reuse must remain source-fingerprint + hash bound after the split.

This is a narrow Resi exception, not permission for unrelated workflows to scatter user-facing artifacts outside the outbox.

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
3. pass an explicit contract-defined output path whenever the CLI supports `--output`, `--result-output`, `--backup-output`, or equivalent; the Resi retained master uses the explicit Downloads exception above;
4. never depend on the shell's current directory for the output destination;
5. after success, verify the exact file with `Test-Path -LiteralPath`;
6. print an unmistakable final line with the absolute path, for example `OPEN/SEND THIS FILE: C:\...`;
7. when the next operator action is to inspect or send one local file, select that exact file in Explorer after successful creation unless the user asked for non-interactive behavior;
8. if several files are required, open the contract-defined folder once and print the exact filenames;
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

## Copy/paste serialization contract

Interactive shell handoffs are designed for ordinary **Ctrl+C → Ctrl+V of the entire executable block**. The operator is not expected to distinguish executable lines from illustrative material inside the same visual handoff.

Therefore:

1. one operator action gets at most one executable fenced block;
2. illustrative terminal output, labels such as `Channel:` / `Video:` / `Before SHA:`, or success examples must not appear in a second adjacent fenced block that can be mistaken for commands;
3. long descriptions, comments, JSON bodies and other content are passed by exact file path rather than pasted inline into PowerShell;
4. chat-rendering artifacts such as literal `\_` or `\:` inside an executable block are a handoff defect; never ask the operator to repair them character-by-character;
5. if the client cannot preserve an inline command byte-for-byte, provide one exact `.ps1` artifact and one short invocation line;
6. expected success/failure markers are described in prose outside executable material;
7. a failed copy/paste handoff is fixed at the producer/repository layer rather than normalized as operator cleanup work.

## Provider-capable handoff boundary

Provider-capable PowerShell may choose exact paths, verify local preconditions and invoke a current-`main` repository entrypoint. It must not become a second provider client.

Do not embed provider URLs, OAuth handling, HTTP mutation calls, pagination, retry loops, convergence policy or provider postflight inside generated PowerShell/temporary Python merely to complete an operational session. If current `main` lacks the required provider executor, stop and implement/review that executor under its own scope.

After an accepted provider mutation, an empty or stale immediate readback is not proof of absence. Preserve returned remote IDs/evidence, classify the effect as `may_exist`, and use read-only reconciliation before any repeat mutation.

## Agent handoff requirement

When an agent asks Fedor to run a command and then return a generated file, the agent must provide the output path itself. The agent must not require Fedor to infer repository location, search `data/`, inspect timestamps, or discover filenames manually.

If a tool lacks an explicit output option, the repository-owned wrapper should be improved so that a deterministic user-facing result can be placed in the contract-defined destination. Repeated manual searching is treated as a workflow defect, not as an operator task.
