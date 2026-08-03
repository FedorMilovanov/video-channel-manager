# Reliability audit verification — 2026-08-04

Scope: verify the external audit against repository commit `cb13e0d578626ed39f41336914aa698b5a824f06` before changing production behavior.

## Decision rules

- A finding is **confirmed** only when current code demonstrates the behavior.
- Provider limits or capabilities are not accepted from secondary articles when current primary documentation is unavailable.
- Project-specific safety guards are not classified as generic defects merely because they are hard-coded.
- Fixes must preserve the existing mutation invariants: no blind retry after an ambiguous write, exact identity guards, journal-before/after, and live postflight verification.

## Verification matrix

| Audit item | Status | Verified interpretation | Planned action |
|---|---|---|---|
| B1: Legendary Poet branding in generic VK publication path | **Confirmed, critical** | `platforms/vk/text.py` has Legendary Poet defaults; `platforms/vk/publishing.py` applies the lightning suffix and calls the default renderer; `catalog.py` invokes this generic path without a project profile. This conflicts with the two-project boundary in `AGENTS.md`. | Make publication rendering project-profile aware and fail closed when project identity is absent. Add cross-project contamination tests. |
| B2: no connection pooling | **Confirmed, high** | Core VK and YouTube clients create and close a new `httpx.Client` when no test client is injected. HTTPX documents that persistent `Client` instances reuse pooled TCP connections. | Introduce lifecycle-owned provider clients, explicit `close()`/context-manager support, and tests proving multiple calls reuse one client. |
| B3: duplicated VK API transport | **Confirmed, medium** | Retry codes, HTTP status handling, request encoding, response parsing, and exception translation are duplicated across VK reader/writer/thumbnail surfaces. | Consolidate only after pooling/rate controls are covered by tests; keep mutation retry policy distinct from read retry policy. |
| B4: no chunked/resumable VK video upload | **Partly confirmed; recommendation not accepted** | The implementation sends one multipart POST and a network failure can require another upload. However, no current provider-supported resumable/chunk API has been verified. Generic large-file advice is not enough to invent an unsupported protocol. | Preserve durable upload tickets and reconciliation. Add bounded retry only where the outcome is proven pre-mutation or provider-safe; do not claim chunk resume support. |
| B5: no proactive VK rate control / no `execute` batching | **Code deficiency confirmed; numeric assumptions pending** | Current calls use reactive backoff only. The exact current VK limits and suitable `execute` coverage must be verified from current primary provider documentation before hard-coding numbers. | Add a configurable shared limiter with conservative defaults only after transport consolidation; batch read-only calls where response semantics are testable. Never batch ambiguous writes. |
| B6: SQLite lacks WAL and busy timeout | **Confirmed, medium** | SQLite engine setup only disables `check_same_thread`; it does not configure WAL or a per-connection busy timeout. SQLite documents both mechanisms. | Configure SQLite connections through SQLAlchemy events, verify `journal_mode`, `busy_timeout`, and foreign keys in tests. |
| B7: external VK env path and project IDs | **Mixed; mostly intentional** | The external `mp3telegrambot/.env` source is explicitly documented in `AGENTS.md` as the current credential source. Exact community/owner IDs in focused operational scripts are safety guards. They are not identity bugs. Portability is still weak when paths are embedded in reusable library code or user-visible launchers. | Keep the documented credential fallback for compatibility, but add an explicit setting and warnings; add CI checks against new absolute paths in reusable `src/` code. Do not remove numeric mutation guards. |
| B8: exactly 42 targets | **Not a generic bug** | The invariant appears in a dated, Legendary-Poet-specific final megawave and validates an immutable reviewed policy snapshot. It should fail if that snapshot changes unexpectedly. | Keep the guard in the closed historical executor. Prevent new generic modules from copying snapshot-specific counts. |
| B9: membership `position` churn | **Historical defect, partly remediated** | Position is provider-observed and can change independently of semantic membership. Some code already compares collection/video pairs. | Add a shared semantic membership comparator and regression tests before touching remaining postflights. |
| B10: `authority_repository=TheLegendaryPoet` | **Audit finding rejected** | The constant is inside `editorial_stance.py`, whose API and profile ID are explicitly Legendary-Poet-specific. Its mere presence is not contamination of the theological project. | No change unless a lord-god call site is found. Add an import/call-site boundary test instead of deleting valid project-specific policy. |
| B11: Unicode Windows console failures | **Partly confirmed** | Recent PowerShell runners explicitly set UTF-8, but this is not centralized for every CLI entrypoint. | Add a small runtime output configurator and tests; keep mandatory machine-readable status lines ASCII-safe where possible. |
| B12: bool accepted by int/string digit checks | **Confirmed, low** | `bool` is a subclass of `int`, so `True` can pass current `isinstance(value, int | str)` gates. | Add strict positive-integer parsing helper and migrate identity fields incrementally. |

## Corrected priority order

1. Project identity and branding fail-closed.
2. Persistent HTTP clients and explicit lifecycle.
3. SQLite connection pragmas.
4. Shared VK transport plus configurable proactive rate control.
5. Semantic membership comparison and Windows output normalization.
6. Remove portability hazards from reusable code without weakening exact target guards.
7. Long-term: move repeated mutation state machines into library primitives.

## Non-goals

- No unsupported VK chunk/resume protocol.
- No automatic retry of `photos.saveWallPhoto`, `video.save`, `wall.post`, or another mutation with an ambiguous outcome.
- No removal of exact community/owner/source identity guards.
- No replacement of project-specific reviewed policy snapshots with loose dynamic discovery.

## Primary references checked

- HTTPX Clients: https://www.python-httpx.org/advanced/clients/
- SQLite PRAGMA documentation: https://www.sqlite.org/pragma.html
- SQLite WAL documentation: https://www.sqlite.org/wal.html
- YouTube Data API quota documentation: https://developers.google.com/youtube/v3/determine_quota_cost

Current public VK documentation was not reliably retrievable during this verification, so exact request-rate and `execute` assumptions remain configuration candidates rather than verified constants.
