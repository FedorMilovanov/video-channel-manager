# Architecture

## Product boundary

Video Channel Manager owns channel inventory, audit snapshots, external-AI exchange documents, change plans, safe execution, verification, and history. It does not own creative generation, MP3 conversion, LiveDub, or Telegram media delivery.

## Modular monolith

The application is one deployable unit with strict internal boundaries:

- `domain`: platform-neutral vocabulary and invariants;
- `exchange`: stable JSON contracts shared with external AI systems;
- `application`: orchestration, validation, previews, and later execution;
- `platforms`: YouTube/VK adapters behind protocols;
- `persistence`: storage concerns only;
- `local_media`: read-only file inventory and future matching;
- `cli`: presentation layer, never business logic.

No application service imports Telegram, Gemini, or provider SDKs directly.

## Data flow

1. Platform adapter reads current remote state.
2. Scanner normalizes data into domain records.
3. Audit creates an immutable `AuditPackage` and findings.
4. The package is exported to a human or external AI.
5. A versioned `ChangePlan` is imported.
6. Pydantic validates structure and invariants.
7. `PlanGuard` applies local policy and risk limits.
8. Preview shows the exact intended mutation set.
9. Future executor re-reads current state and checks revisions.
10. Operations execute idempotently and results are verified.
11. Every attempt is persisted.

## Why RemoteVideo exists before ContentIdentity

A platform publication always exists independently. Cross-platform identity is optional and will be introduced only when matching confidence or human confirmation is sufficient. This prevents false coupling between unrelated videos with similar titles.

## Database strategy

SQLAlchemy 2 models support SQLite for local development and PostgreSQL for deployed workers. Alembic owns schema evolution. JSON payloads preserve raw provider data without leaking provider-specific fields into domain contracts.

## Queue strategy

The foundation stores operations and attempts without choosing a queue implementation. A worker boundary will be added when upload and long-running API operations are implemented. This avoids prematurely coupling the domain to Celery, Dramatiq, or Redis.
