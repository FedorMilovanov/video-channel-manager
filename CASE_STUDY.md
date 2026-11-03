# Case study: verification before multichannel media changes

## Engineering problem

Media channels are not a shared list of editable rows. YouTube, VK, Instagram, Telegram and local assets have different identity, revision, format, rights and failure semantics. A timeout after a provider write may mean the change succeeded even if a local process never recorded a result. Blind retries can then duplicate uploads, posts or scheduled content.

**Video Channel Manager** implements a common evidence and planning boundary while keeping platform-specific adapters and owner approvals separate. The application is not the source of copyrighted media, and a green CI check is never permission to publish.

## Source-verifiable implementation

| Invariant | Implementation and decision record |
|---|---|
| Project and target identity | [docs/operations/project-identity-registry.md](docs/operations/project-identity-registry.md) binds project keys to exact channel/community IDs; credentials alone are not selectors |
| Immutable evidence before mutation | [docs/architecture.md](docs/architecture.md) and [docs/adr/0003-guarded-remote-mutations.md](docs/adr/0003-guarded-remote-mutations.md) describe `AuditPackage` → canonical content → reviewed `ChangePlan` → plan guard, dry-run, locking and postflight |
| Deterministic editorial rendering | [docs/editorial/unified-editorial-standard.md](docs/editorial/unified-editorial-standard.md) separates source-backed facts and interpretation from YouTube/VK renderers |
| Safe release acceptance | [docs/operations/operational-package-acceptance.md](docs/operations/operational-package-acceptance.md) defines `editorial_prepared`, `preview_validated`, `self_tested`, `canary_verified` and `batch_verified` as distinct proof levels |
| Durable outcome and no replay | [AGENTS.md](AGENTS.md) and [docs/operations/current-state.md](docs/operations/current-state.md) require exact-target bindings, single-writer ownership and read-only reconciliation when a remote effect may have occurred |
| Protected forensic references | [docs/operations/protected-evidence-refs.json](docs/operations/protected-evidence-refs.json) distinguishes durable state and content-addressed evidence refs from disposable work branches |

## Architecture in practice

The source tree contains a platform-neutral domain and exchange layer, application/CLI orchestration, platform adapters, local-media handling and persistence. [pyproject.toml](pyproject.toml) defines a Python 3.11+ package with SQLAlchemy, Pydantic and Typer, together with pytest, Ruff and mypy development gates.

A representative **local, read-only** validation path from the root of an authorized checkout:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m mypy src/video_channel_manager
```

These commands check code-level properties only. They do **not** call the YouTube/VK/Instagram/Telegram publishing executors. For the correct authoritative release/checklist for a specific project and platform, follow its existing [current-state registry](docs/operations/current-state.md), owning issue and runbook rather than using this case study as a substitute.

## Results that can and cannot be claimed

**Supported by the code and contracts:** a reusable audit/snapshot format, deterministic plan and preview boundaries, explicit provider identity, safeguards against conflicting writes and blind retries, and separate verification levels for code, final artifacts and provider effects.

**Not established by source alone:** how many posts actually reached a platform, whether a remote account currently has valid OAuth permissions, provider-side delivery success, paid traffic, views, engagement, business revenue, or clearance to reuse third-party media.

For maintainer and third-party attribution, see [OWNER.md](OWNER.md); for safe vulnerability reporting, see [SECURITY.md](SECURITY.md). Media operations always require project-scoped authority and exact readback under [AGENTS.md](AGENTS.md).
