# Video Channel Manager

**Video Channel Manager** is a safety-first toolkit for auditing, organizing, and synchronizing video channels across YouTube, VK, local storage, and future platforms.

It is not a one-off YouTube → VK script. The core is platform-neutral and supports independent work with each channel:

- authorize multiple YouTube accounts with read-only OAuth;
- export channels, videos, playlists, and memberships as a versioned `AuditPackage`;
- organize titles, descriptions, thumbnails, tags, and playlists through reviewed plans;
- audit a VK community and its video albums in future phases;
- compare platforms and detect missing or duplicate publications;
- import a structured `ChangePlan` prepared by an external AI assistant;
- preview, validate, approve, execute, verify, and roll back changes;
- index local media without moving or deleting files.

> Status: YouTube read-only OAuth and complete channel inventory are operational. Remote mutations remain intentionally disabled until write scopes, policy gates, live fixtures, dry-run previews, and rollback paths are implemented and approved.

## Core principles

1. **Read-only by default.** Scans and audits never mutate remote platforms.
2. **External AI, deterministic executor.** AI analyzes exported data and returns a versioned `ChangePlan`; this application validates and executes it.
3. **Dry-run before write.** Every plan has a preview and policy validation stage.
4. **No guessed IDs.** All remote objects are referenced by exact platform IDs.
5. **Optimistic concurrency.** Mutations carry an expected revision to avoid overwriting newer manual edits.
6. **Idempotency.** Re-running a plan must not create duplicates.
7. **Auditability.** Snapshots, plans, operations, attempts, and outcomes are persisted.
8. **Human approval.** Editorial and playlist changes are reviewed before any remote write.
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

- [`docs/youtube-editorial-standard.md`](docs/youtube-editorial-standard.md) — titles, descriptions, YouTube formatting, Shorts classification, playlist routing, fact-checking, tags, hashtags, and approval rules;
- [`docs/audits/2026-07-24-the-legendary-poet.md`](docs/audits/2026-07-24-the-legendary-poet.md) — the first real audit of **The Legendary Poet**.

These files are the source of truth for future AI-assisted recommendations. Do not rely on chat memory alone.

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

Authorize one account alias:

```powershell
video-manager youtube login --account legendary-poet
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
```

The current operational workflow is:

```text
YouTube scan → AuditPackage → verified editorial analysis → ChangePlan
→ strict validation → human approval → preview → future safe operations
```

## Project layout

```text
src/video_channel_manager/
├── application/     # use cases, validation, preview
├── cli/             # PowerShell-friendly command line
├── config/          # typed environment settings
├── domain/          # platform-neutral models and enums
├── exchange/        # versioned AuditPackage / ChangePlan formats
├── local_media/     # read-only local file indexer
├── persistence/     # SQLAlchemy entities and database lifecycle
└── platforms/       # adapter contracts and platform implementations
```

## Safety posture

Destructive operations are disabled by default. A plan can be syntactically valid and still be rejected by policy. See [`docs/security.md`](docs/security.md).

Never run `git clean -fdx` in a working tree that contains ignored OAuth secrets or tokens.

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
2. generate verified editorial findings and reviewed `ChangePlan` documents;
3. add explicit write scopes and safe playlist operations behind dry-run, revision, approval, and rollback gates;
4. implement VK read-only inventory and cross-platform comparison.

See [`docs/roadmap.md`](docs/roadmap.md).
