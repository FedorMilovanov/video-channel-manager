# Video Channel Manager

**Video Channel Manager** is a safety-first toolkit for auditing, organizing, and synchronizing video channels across YouTube, VK, local storage, and future platforms.

It is not a one-off YouTube → VK script. The core is platform-neutral and supports independent work with each channel:

- authorize multiple YouTube accounts with read-only or explicitly requested guarded-write OAuth;
- export channels, videos, playlists, and memberships as a versioned `AuditPackage`;
- organize titles, descriptions, thumbnails, tags, and playlists through reviewed plans;
- audit a VK community and its video albums in future phases;
- compare platforms and detect missing or duplicate publications;
- import a structured `ChangePlan` prepared by an external AI assistant;
- preview, validate, approve, execute, verify, and roll back changes;
- index local media without moving or deleting files.

> Status: YouTube read-only OAuth, complete channel inventory, deterministic description validation, conservative description plans, guarded writes, verification, backups, and recovery are operational. Playlist and destructive remote mutations remain disabled until their own policy gates and rollback paths are implemented.

## Core principles

1. **Read-only by default.** Scans and audits never mutate remote platforms.
2. **External AI, deterministic executor.** AI analyzes exported data and returns a versioned plan; the application validates and executes only supported deterministic operations.
3. **Dry-run before write.** Every mutation command performs a complete live preflight before writing.
4. **No guessed IDs.** All remote objects are referenced by exact platform IDs.
5. **Description-state concurrency.** A write proceeds only when live text matches the planned before-state; the planned after-state is idempotently accepted, and every third state is rejected.
6. **Idempotency.** Re-running a plan must not duplicate or overwrite work already applied.
7. **Auditability.** Snapshots, plans, backups, attempts, outcomes, postflight checks, and rollback results are persisted.
8. **Human editorial boundary.** The bot automates only mechanically provable formatting changes; semantic punctuation and factual edits stay review-only.
9. **Modular monolith.** One deployable application with strict domain and adapter boundaries.

## Architecture

```text
External AI / Human editor
          │
          │ AuditPackage ↔ ChangePlan (JSON)
          ▼
┌───────────────────────────────────────────────┐
│              Video Channel Manager            │
│                                               │
│  CLI / future Web UI / future Telegram client │
│                    │                          │
│  Audit ─ Plan Guard ─ Preview ─ Executor      │
│                    │                          │
│  Domain + SQLAlchemy persistence + history    │
│                    │                          │
│  YouTube adapter | VK adapter | Local index   │
└───────────────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) and [`docs/exchange-format.md`](docs/exchange-format.md).

## Editorial policy

Channel-specific editorial and playlist decisions are documented in:

- [`docs/youtube-editorial-standard.md`](docs/youtube-editorial-standard.md) — titles, descriptions, Shorts classification, playlist routing, fact-checking, tags, hashtags, and approval rules;
- [`docs/youtube-description-rendering-standard.md`](docs/youtube-description-rendering-standard.md) — exact `*bold*` / `_italic_` punctuation, first-paragraph behavior, selective emoji policy, line breaks, final-link rendering, and the screenshot-verified «На поле Куликовом» example;
- [`docs/youtube-copy-automation-safety.md`](docs/youtube-copy-automation-safety.md) — the narrower deterministic boundary for automatic fixes, live-state guards, retries, locking, postflight, and rollback;
- [`docs/audits/2026-07-24-the-legendary-poet.md`](docs/audits/2026-07-24-the-legendary-poet.md) — the first real audit of **The Legendary Poet**.

These files are the source of truth for future AI-assisted recommendations. Do not rely on chat memory alone. Human editorial guidance may be broader than the automatic rules: the automation safety document controls what the bot may change without review.

## Quick start — Windows PowerShell

```powershell
./scripts/setup.ps1
.\.venv\Scripts\Activate.ps1
video-manager doctor
video-manager db init
video-manager schema export --output-dir .\schemas
video-manager example export --output-dir .\examples\generated
```

Manual installation:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## YouTube OAuth and inventory

Place the downloaded Google OAuth **Desktop app** client in a local ignored path such as:

```text
secrets/client_secret.json
```

Authorize one account alias for read-only work:

```powershell
video-manager youtube login --account legendary-poet
```

Guarded description writes require an explicit replacement token:

```powershell
video-manager youtube login --account legendary-poet --write --force
```

Inspect local accounts and live channels:

```powershell
video-manager youtube accounts
video-manager youtube channels --account legendary-poet
```

Export a complete read-only snapshot:

```powershell
video-manager youtube scan --account legendary-poet
```

The export contains exact channel/video/playlist IDs, metadata, revisions, playlist memberships, and a read-only marker. OAuth tokens and client secrets stay local and must never be committed.

See [`docs/youtube-oauth.md`](docs/youtube-oauth.md).

## Editorial validation and conservative plans

Validate a single prepared description stored as UTF-8 text:

```powershell
python .\scripts\validate_youtube_copy.py .\description.txt --strict
```

Validate every description in an `AuditPackage` and write a Markdown report:

```powershell
python .\scripts\validate_youtube_copy.py `
  .\data\exports\youtube-audit-package.json `
  --output .\data\reports\youtube-copy-validation.md
```

Build a conservative description plan:

```powershell
python .\scripts\autofix_youtube_copy.py .\data\exports\youtube-audit-package.json
```

General commas, full stops, semicolons, and explanatory colons outside an emphasis span are review-only. The bot automatically changes punctuation only when the scope is mechanically unambiguous, such as `*VK:*` or an extra period after `?`, `!`, or `…`. A video with any remaining error-level finding is excluded from automatic operations.

Preflight and apply a generated plan:

```powershell
video-manager youtube apply-copy-fixes `
  .\data\reports\youtube-copy-fix-plan.json `
  --account legendary-poet `
  --confirm-channel UC_EXACT_CHANNEL_ID

video-manager youtube apply-copy-fixes `
  .\data\reports\youtube-copy-fix-plan.json `
  --account legendary-poet `
  --confirm-channel UC_EXACT_CHANNEL_ID `
  --execute
```

Execution holds a local process lock, writes a backup before mutation, records progress incrementally, retries bounded verification reads, performs a final whole-batch postflight, and rolls back every attempted operation when the batch fails.

After an automation ruleset changes, recompute only affected outputs from a completed apply result:

```powershell
python .\scripts\rebuild_youtube_copy_plan.py `
  .\data\reports\youtube-copy-apply-YYYYMMDD-HHMMSS.json
```

## CLI

```text
video-manager version
video-manager doctor
video-manager db init
video-manager schema export
video-manager example export
video-manager plan validate plan.json
video-manager plan preview plan.json
video-manager local scan H:\ --output local-inventory.json
video-manager youtube login --account legendary-poet
video-manager youtube accounts
video-manager youtube channels --account legendary-poet
video-manager youtube scan --account legendary-poet
video-manager youtube apply-copy-fixes plan.json --account legendary-poet --confirm-channel UC_EXACT_CHANNEL_ID
```

The current operational description workflow is:

```text
YouTube scan → AuditPackage → conservative deterministic plan → live dry-run
→ explicit guarded write → per-item verification → whole-batch postflight
→ completed result or description-state guarded rollback
```

## Project layout

```text
src/video_channel_manager/
├── application/     # use cases, validation, preview
├── cli/             # PowerShell-friendly command line
├── config/          # typed environment settings
├── domain/          # platform-neutral models and enums
├── editorial/       # deterministic YouTube copy validation
├── exchange/        # versioned AuditPackage / ChangePlan formats
├── local_media/     # read-only local file indexer
├── persistence/     # SQLAlchemy entities and database lifecycle
└── platforms/       # adapter contracts and platform implementations
```

## Safety posture

Destructive operations are disabled by default. Supported description replacement is narrow, non-destructive, explicitly authorized, backed up, live-state guarded, verified, and recoverable. A plan can be syntactically valid and still be rejected by policy. See [`docs/security.md`](docs/security.md).

Never run `git clean -fdx` in a working tree that contains ignored OAuth secrets, tokens, exports, backups, or result logs.

## Development

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

CI runs on Python 3.11, 3.12, and 3.13.

## Roadmap

The next milestones are:

1. enrich read-only YouTube inventory with owner-only file geometry for reliable Shorts classification;
2. generate broader verified editorial findings and reviewed `ChangePlan` documents;
3. add safe playlist operations behind dry-run, approval, live-state, verification, and rollback gates;
4. implement VK read-only inventory and cross-platform comparison.

See [`docs/roadmap.md`](docs/roadmap.md).
