# Video Channel Manager

**Video Channel Manager** is a safety-first toolkit for auditing, organizing, and synchronizing video channels across YouTube, VK, local storage, and future platforms.

It is not a one-off YouTube → VK script. The core is platform-neutral and supports independent work with each channel:

- authorize multiple YouTube accounts with read-only OAuth;
- import and validate multiple VK user tokens locally;
- export YouTube channels or VK communities as a versioned `AuditPackage`;
- organize titles, descriptions, thumbnails, tags, playlists, and video albums through reviewed plans;
- compare platforms and detect missing or duplicate publications;
- import a structured `ChangePlan` prepared by an external AI assistant;
- preview, validate, approve, execute, verify, and roll back changes;
- index local media without moving or deleting files.

> Status: YouTube read-only OAuth and complete channel inventory are operational. VK read-only user-token inventory is implemented in `feature/vk-readonly-v1`. Remote mutations remain intentionally disabled until write scopes, policy gates, live fixtures, dry-run previews, verification, and rollback paths are implemented and approved.

## Core principles

1. **Read-only by default.** Scans and audits never mutate remote platforms.
2. **External AI, deterministic executor.** AI analyzes exported data and returns a versioned `ChangePlan`; this application validates and executes it.
3. **Dry-run before write.** Every plan has a preview and policy validation stage.
4. **No guessed IDs.** All remote objects are referenced by exact platform IDs.
5. **Optimistic concurrency.** Mutations carry an expected revision to avoid overwriting newer manual edits.
6. **Idempotency.** Re-running a plan must not create duplicates.
7. **Auditability.** Snapshots, plans, operations, attempts, and outcomes are persisted.
8. **Human approval.** Editorial and collection changes are reviewed before any remote write.
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

## Editorial and platform policy

Permanent instructions and audit decisions are documented in:

- [`docs/youtube-editorial-standard.md`](docs/youtube-editorial-standard.md) — titles, descriptions, Shorts classification, playlist routing, fact-checking, tags, hashtags, and approval rules;
- [`docs/youtube-description-rendering-standard.md`](docs/youtube-description-rendering-standard.md) — exact `*bold*` / `_italic_` punctuation, first-paragraph behavior, selective emoji policy, line breaks, final-link rendering, and the screenshot-verified «На поле Куликовом» example;
- [`docs/vk-readonly.md`](docs/vk-readonly.md) — VK token safety, communities, videos, albums, Shorts/Clips metadata, pagination, system albums, and first-run commands;
- [`docs/audits/2026-07-24-the-legendary-poet.md`](docs/audits/2026-07-24-the-legendary-poet.md) — the first real YouTube audit of **The Legendary Poet**;
- [`docs/research/2026-07-25-vk-api-source-ledger.md`](docs/research/2026-07-25-vk-api-source-ledger.md) — 52-source VK API research ledger.

These files are the source of truth for future AI-assisted recommendations. Do not rely on chat memory alone. The YouTube rendering standard takes precedence when it clarifies punctuation or emoji behavior.

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

## Editorial validation

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

The validator treats punctuation outside a completed emphasis span as an error candidate, allows an external dash in `*The Legendary Poet* — ...`, permits one intentional emoji in the first paragraph, and only warns when emoji prefixes appear mechanically on all or almost all body paragraphs.

## VK token and inventory

The VK video methods used here require a **user access token**, not a community token. Obtain one through an official VK OAuth flow with the expected `video` and `groups` permissions, then import it through hidden input:

```powershell
video-manager vk login --account legendary-poet
```

The command validates the token with read-only calls before it is permanently saved. It accepts a raw token, a full OAuth redirect URL, or a local ignored token file:

```powershell
video-manager vk login --account legendary-poet --token-file .\secrets\vk-token.txt
```

Inspect local aliases and managed communities:

```powershell
video-manager vk accounts
video-manager vk communities --account legendary-poet
```

Export a complete community snapshot:

```powershell
video-manager vk scan --account legendary-poet --community <numeric-id-or-screen-name>
```

The export includes exact community/video/album IDs, system-album markers, video dimensions and VK type, revisions, and album memberships. It does not call any write method.

See [`docs/vk-readonly.md`](docs/vk-readonly.md).

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
video-manager vk login --account legendary-poet
video-manager vk accounts
video-manager vk communities --account legendary-poet
video-manager vk scan --account legendary-poet --community <id-or-screen-name>
```

The operational workflow is:

```text
YouTube scan ─┐
              ├→ AuditPackage(s) → verified editorial/cross-platform analysis
VK scan ──────┘  → ChangePlan → strict validation → human approval
                 → preview → future safe operations
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
└── platforms/       # YouTube, VK, and future adapter implementations
```

## Safety posture

Destructive operations are disabled by default. A plan can be syntactically valid and still be rejected by policy. See [`docs/security.md`](docs/security.md).

Never run `git clean -fdx` in a working tree that contains ignored OAuth secrets or tokens.

VK tokens are stored below `data/secrets/vk/`, outside version control. The CLI validates a replacement token in a temporary directory first, sends tokens in POST bodies rather than URLs, and does not copy VK `request_params` into exception messages.

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

1. obtain the first real VK `AuditPackage` and verify response variations against the official schema;
2. compare real YouTube and VK snapshots without mutating either platform;
3. generate verified editorial and cross-platform findings plus reviewed `ChangePlan` documents;
4. enrich matching with local media fingerprints and owner-only geometry where available;
5. add explicit write scopes and safe playlist/video-album operations behind dry-run, revision, approval, verification, and rollback gates.

See [`docs/roadmap.md`](docs/roadmap.md).
