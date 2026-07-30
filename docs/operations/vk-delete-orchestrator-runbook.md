# VK delete orchestrator runbook

## Purpose

Resume the signed 403-operation VK duplicate cleanup without the V1–V10 restart loop. The command imports the legacy journal once and then owns its lifecycle in SQLite.

## Do not run

Do not run any `Invoke-VkDeleteMegawave.ps1` V1–V10 package again. Operations 30 and 31 already have accepted VK responses and must never be sent a second time.

## Install

```powershell
cd C:\Users\Fedor\Projects\video-channel-manager

git fetch origin
git switch agent/vk-delete-orchestrator

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Files

Use the immutable artifacts already produced:

```text
policy:
  vk-delete-megawave-policy-20260730.json

wall audit:
  source-wall-audit.zip

legacy journal:
  vk-lord-strength-delete-megawave-apply-20260730-173341.zip
```

The legacy argument can point directly to the diagnostic ZIP; the orchestrator extracts `10-journal.json` itself.

## First read-only import and reconciliation

```powershell
vk-delete-orchestrator run `
  --account default `
  --policy .\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\vk-delete-megawave-policy-20260730.json `
  --wall-audit .\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\source-wall-audit.zip `
  --legacy-journal .\data\handoffs\vk-lord-strength-delete-megawave-apply-20260730-173341.zip
```

Expected imported state before live reconciliation:

```text
confirmed_deleted: 29
accepted: 2
planned: 372
```

No `video.delete` call is possible without `--execute`.

## Live run

Set the destructive gate only in the current PowerShell session:

```powershell
$env:VCM_ALLOW_DESTRUCTIVE_OPERATIONS = "true"
```

Then start one durable process:

```powershell
vk-delete-orchestrator run `
  --account default `
  --policy .\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\vk-delete-megawave-policy-20260730.json `
  --wall-audit .\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\source-wall-audit.zip `
  --legacy-journal .\data\handoffs\vk-lord-strength-delete-megawave-apply-20260730-173341.zip `
  --execute `
  --confirm-policy-sha256 "sha256:6c5f6f856c72c685d7e6bf33a163b9e9c3513464e76ec3d45edaa57c73539ded" `
  --confirm-community 60805374 `
  --confirm-operations 403
```

The process waits and reconciles automatically. Do not interrupt it merely because no writes are printed during cooldown.

## Status in another terminal

```powershell
vk-delete-orchestrator status `
  --policy .\data\handoffs\vk-lord-strength-delete-megawave-v10-20260730\vk-delete-megawave-policy-20260730.json
```

`status` reads SQLite only. It does not load the evidence bundle and does not call VK.

## Crash or reboot

Run the same live command again. The SQLite ledger and legacy import are idempotent. An operation with `dispatch_count=1` is never sent again.

The filesystem lock detects a live writer. A stale lock is removed only when the recorded local process is no longer running.

## Fatal versus non-fatal

Fatal:

- protected video absent from both inventory and exact guarded lookup;
- signed wall attachment missing;
- primary immutable guard changed or primary disappeared;
- authorization failure;
- evidence/policy digest mismatch.

Not fatal by itself:

- owner `count` differs from visible items;
- two accepted deletes become visible together;
- exact candidate lookup returns a shell;
- mutable album title/privacy changes;
- rate limit or server timeout on reads.

## Database

Default:

```text
data/vk/delete-orchestrator.db
```

Do not delete this file while the signed run is active. Back up the `.db`, `-wal`, and `-shm` files together when the process is stopped.
