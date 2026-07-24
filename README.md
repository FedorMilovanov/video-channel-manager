# Video Channel Manager

**Video Channel Manager** is a safety-first toolkit for auditing, organizing, and synchronizing video channels across YouTube, VK, local storage, and future platforms.

It is not a one-off YouTube → VK script. The core is platform-neutral and supports independent work with each channel:

- inspect a YouTube channel without changing anything;
- organize titles, descriptions, thumbnails, and playlists;
- audit a VK community and its video albums;
- compare platforms and detect missing or duplicate publications;
- import a structured change plan prepared by an external AI assistant;
- preview, validate, approve, execute, verify, and roll back changes;
- index local media without moving or deleting files.

> Status: foundation release. Network adapters are intentionally read-only stubs until OAuth, live API fixtures, and safety gates are implemented and tested.

## Core principles

1. **Read-only by default.** Scans and audits never mutate remote platforms.
2. **External AI, deterministic executor.** AI analyzes exported data and returns a versioned `ChangePlan`; this application validates and executes it.
3. **Dry-run before write.** Every plan has a preview and policy validation stage.
4. **No guessed IDs.** All remote objects are referenced by exact platform IDs.
5. **Optimistic concurrency.** Mutations carry an expected revision to avoid overwriting newer manual edits.
6. **Idempotency.** Re-running a plan must not create duplicates.
7. **Auditability.** Snapshots, plans, operations, attempts, and outcomes are persisted.
8. **Modular monolith.** One deployable application with strict domain and adapter boundaries.

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

## Quick start (Windows PowerShell)

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
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## CLI foundation

```text
video-manager version
video-manager doctor
video-manager db init
video-manager schema export
video-manager example export
video-manager plan validate plan.json
video-manager plan preview plan.json
video-manager local scan H:\ --output local-inventory.json
```

The first operational milestone is:

```text
YouTube scan → AuditPackage → external AI analysis → ChangePlan
→ strict validation → preview → safe playlist operations
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

## Development

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

CI runs on Python 3.11, 3.12, and 3.13.

## Roadmap

See [`docs/roadmap.md`](docs/roadmap.md). The next implementation phase adds YouTube OAuth and a read-only channel scanner, followed by VK read-only inventory and safe playlist/album mutations.
