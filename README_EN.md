# Video Channel Manager

**[Русский README](README.md)** · **[Architecture](docs/architecture.md)** · **[Evidence-based case study](CASE_STUDY.md)** · **[Ownership and rights](OWNER.md)** · **[Agent contract](AGENTS.md)** · **[Security](SECURITY.md)**

Video Channel Manager is a **safety-first, locally operated platform for inventorying, auditing, editorially reviewing, and coordinating YouTube, VK, and local video assets**. It is a platform-neutral modular monolith, not a one-off YouTube-to-VK copying script. The project is maintained by Fedor Milovanov, with deterministic execution boundaries and external AI used for editorial review rather than unrestricted provider writes.

> **Operational notice:** This page describes capabilities, **not authorization to mutate a provider**. The canonical current state is [`docs/operations/current-state.md`](docs/operations/current-state.md). Past issues, screenshots, API tokens, successful CI runs, example commands and old plans cannot grant new write permission. Every provider operation needs an explicitly authorized, exact project-bound scope, fresh read-only preflight, reviewed immutable plan and separate execution authority. Default is **read-only**.

## Capabilities

- Multi-account YouTube and VK inventory using exact local aliases and remote target IDs.
- Read-only provider snapshots assembled into immutable `AuditPackage` records.
- Human-reviewed canonical editorial records, with platform-specific rendering and validation.
- Versioned `ChangePlan` schemas, local previews, risk limits and complete before/after comparison.
- Guarded execution **only when separately authorized**: idempotency checks, a single writer per target, locked re-preflight, durable intent, backups, per-operation journals, postcondition verification and guarded rollback.
- Local image/video inspection, media fingerprints and SHA-256-bound artifacts.
- SQLAlchemy/Alembic domain persistence and JSON exchange interfaces for external editorial assistants.

Do not confuse a working executor with permission to use it on a particular channel, community, item or publication. Repository implementation, artifact production, and confirmed remote rollout are **three distinct completion states**.

## Safety invariants

1. **Exact identities:** project, provider account, channel/community and remote object must match the current identity registry. Credentials authenticate; they do not identify the target.
2. **External AI proposes; guarded deterministic code executes.** A generated plan is not an execution instruction.
3. **Immutable evidence:** accepted snapshots, plans and results bind exact paths, IDs and hashes.
4. **Full before-state:** an omitted target record cannot prove absence; unknown state blocks the operation.
5. **Single writer and locked re-preflight:** current provider state is checked again after taking the lock.
6. **No blind retries:** ambiguous outcomes require read-only reconciliation before another write.
7. **Verify the actual postcondition:** HTTP success alone is not evidence of completion.
8. **Human editorial boundary:** facts, interpretations, quotations and ambiguous wording are not silently rewritten.

The full safety model is in [`docs/security.md`](docs/security.md); see the [disclosure policy](SECURITY.md) for reporting vulnerabilities.

## Architecture

The code separates platform-neutral domain models, stable JSON exchange contracts, application services, YouTube/VK adapters, persistence, local media and CLI presentation.

```text
Provider read -> normalized domain inventory -> immutable AuditPackage
    -> human/external-AI review -> versioned ChangePlan
    -> schema and policy validation -> local preview
    -> [separate explicit authorization needed]
    -> exact-target lock -> re-preflight -> backup and durable intent
    -> bounded operation -> remote readback -> verified result
```

Read [architecture](docs/architecture.md), [exchange formats](docs/exchange-format.md) and the [guarded remote-mutation ADR](docs/adr/0003-guarded-remote-mutations.md). The source of truth for live operational decisions is the [current-state document](docs/operations/current-state.md), the [project identity registry](docs/operations/project-identity-registry.md) and the exact owning issue/runbook—not an archived status summary.

## Installation (Windows PowerShell)

With Python 3.11 installed:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

video-manager doctor
video-manager db init
video-manager schema export --output-dir .\schemas
video-manager example export --output-dir .\examples\generated
```

Credentials and OAuth material belong only in ignored local paths, including `secrets/client_secret.json` and `data/secrets/`. **Do not run `git clean -fdx` in a worktree containing ignored credentials, evidence packages or backups.** Generated artifacts in `data/` and `operator-output/` do not belong in public Git history.

## Local validation and read-only examples

These illustrate local commands, not a license to execute on a live provider:

```powershell
video-manager version
video-manager doctor
video-manager schema export
video-manager plan validate plan.json
video-manager plan preview plan.json
video-manager content validate --input content/editorial
video-manager content preview --platform youtube --surface comment --input content/editorial
video-manager content preview --platform vk --surface video_description --input content/editorial
```

Editorial records are validated and rendered before any platform operation. Building or checking a signed plan **does not** grant authority to apply it. A target manifest binds the exact snapshot ID/path and SHA-256, a timezone-aware capture time, exact target IDs and the actual before-state. Missing state coverage must never be interpreted as proof of absence.

See the [unified editorial runbook](docs/operations/unified-editorial-runbook.md), [editorial standard](docs/editorial/unified-editorial-standard.md), [rendering rules](docs/editorial/platform-rendering-rules.md) and [YouTube editorial rules](docs/youtube-editorial-standard.md).

## Resi/DASH and local media

Local file inventory and Resi/DASH operator handoff are separate from provider account writes. Follow the [Resi/DASH operator runbook](docs/operations/resi-dash-local-handoff.md) for supported source acquisition, safety checks and artifact destinations. A completed media artifact needs ffprobe/QC and SHA-256 provenance; a file name or process ID alone is not completion evidence.

## Development and verification

```bash
pip check
python -m compileall -q src scripts tests
ruff check .
ruff format --check .
mypy src --show-error-codes
python -m pytest --cov=video_channel_manager --cov-report=term-missing
pip-audit --skip-editable --desc on
```

CI covers supported Python environments, typing, formatting, vulnerabilities, PowerShell wrappers and contract tests. Use **current** CI results, not historical counts, as acceptance evidence. Read [`AGENTS.md`](AGENTS.md) before modifying code or workflows. A merged PR can prove implementation completion; it cannot authorize remote provider mutations.

## Project boundaries and attribution

The project owns channel inventory, external-AI exchange records, guarded plans, verification and operational history. It does **not** own creative music generation, MP3 conversion, LiveDub or Telegram media delivery; those belong to separate workflows and products.

Maintainer: [Fedor Milovanov](https://github.com/FedorMilovanov). Third-party APIs, media, and content retain their own permissions and licenses; no redistribution right is implied by this repository's code.
