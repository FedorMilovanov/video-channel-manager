# VK delete orchestrator runbook

## Purpose

Resume the signed 403-operation VK duplicate cleanup without the V1–V10 restart loop. The command imports the legacy journal once and then owns its lifecycle in SQLite.

## Do not run

Do not run any `Invoke-VkDeleteMegawave.ps1` V1–V10 package again. Operations 30 and 31 already have accepted VK responses and must never be sent a second time.

## Install in a separate worktree

Do not switch the user's working repository away from its current branch. Prepare an isolated worktree for the draft orchestrator:

```powershell
$repo = "C:\Users\Fedor\Projects\video-channel-manager"
$worktree = "C:\Users\Fedor\Projects\video-channel-manager-orchestrator"

git -C $repo fetch origin agent/vk-delete-orchestrator

if (Test-Path -LiteralPath $worktree) {
    throw "Dedicated orchestrator worktree already exists: $worktree"
}

git -C $repo worktree add --detach $worktree origin/agent/vk-delete-orchestrator

cd $worktree
py -3.11 -m venv .venv
& "$worktree\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$worktree\.venv\Scripts\python.exe" -m pip install -e ".[dev]"
```

## Files

Use the immutable artifacts already produced in the original repository:

```text
policy:
  data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\vk-delete-megawave-policy-20260730.json

wall audit:
  data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\source-wall-audit.zip

legacy journal:
  data\handoffs\vk-lord-strength-delete-megawave-apply-20260730-173341.zip
```

The legacy argument can point directly to the diagnostic ZIP; the orchestrator extracts `10-journal.json` itself.

## One-command continuous read-only reconciliation

This is the required first live step. It contains no `--execute`, does not set the destructive environment gate, and cannot open a new deletion epoch. It waits through transient VK reads and performs both absence confirmations for operations 30 and 31 automatically.

```powershell
$env:VCM_DATA_DIR = "$repo\data"

& "$worktree\.venv\Scripts\python.exe" -m video_channel_manager.cli.vk_delete run `
  --account default `
  --policy "$repo\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\vk-delete-megawave-policy-20260730.json" `
  --wall-audit "$repo\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\source-wall-audit.zip" `
  --legacy-journal "$repo\data\handoffs\vk-lord-strength-delete-megawave-apply-20260730-173341.zip" `
  --ledger "$repo\data\vk\delete-orchestrator.db" `
  --watch-read-only
```

Expected imported state before live reconciliation:

```text
confirmed_deleted: 29
accepted: 2
planned: 372
```

The process exits by itself when the two legacy accepted operations have terminal read-only outcomes. New planned operations remain untouched.

No `video.delete` call is possible without `--execute`.

## Review before any live run

After read-only reconciliation, inspect durable status:

```powershell
& "$worktree\.venv\Scripts\python.exe" -m video_channel_manager.cli.vk_delete status `
  --policy "$repo\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\vk-delete-megawave-policy-20260730.json" `
  --ledger "$repo\data\vk\delete-orchestrator.db"
```

`status` reads SQLite only. It does not load the evidence bundle and does not call VK.

Do not enable the live dispatcher until the read-only result and draft PR are reviewed.

## Live run after explicit review

Set the destructive gate only in the current PowerShell session:

```powershell
$env:VCM_ALLOW_DESTRUCTIVE_OPERATIONS = "true"
```

Then start one durable process:

```powershell
& "$worktree\.venv\Scripts\python.exe" -m video_channel_manager.cli.vk_delete run `
  --account default `
  --policy "$repo\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\vk-delete-megawave-policy-20260730.json" `
  --wall-audit "$repo\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\source-wall-audit.zip" `
  --legacy-journal "$repo\data\handoffs\vk-lord-strength-delete-megawave-apply-20260730-173341.zip" `
  --ledger "$repo\data\vk\delete-orchestrator.db" `
  --execute `
  --confirm-policy-sha256 "sha256:6c5f6f856c72c685d7e6bf33a163b9e9c3513464e76ec3d45edaa57c73539ded" `
  --confirm-community 60805374 `
  --confirm-operations 403
```

The process waits and reconciles automatically. Do not interrupt it merely because no writes are printed during cooldown.

## Crash or reboot

Run the same command again. The SQLite ledger and legacy import are idempotent. An operation with `dispatch_count=1` is never sent again.

The filesystem lock detects a live writer. A stale lock is removed only when the recorded local process is no longer running.

## Fatal versus non-fatal

Fatal:

- protected video absent from both inventory and exact guarded lookup;
- signed wall attachment missing;
- primary immutable guard changed or primary disappeared;
- authorization failure;
- evidence/policy digest mismatch.

Not fatal by itself:

- owner `count` differs from visible items while the gap is fully explained by exact guarded protected shadow IDs;
- two accepted deletes become visible together;
- exact candidate lookup returns a shell;
- mutable album title/privacy changes;
- rate limit or server timeout on reads.

An unexplained `count/items` gap is transient and blocks confirmation of candidate absence until the complete set is accounted for.

## Database

Default:

```text
data\vk\delete-orchestrator.db
```

Do not delete this file while the signed run is active. Back up the `.db`, `-wal`, and `-shm` files together when the process is stopped.
