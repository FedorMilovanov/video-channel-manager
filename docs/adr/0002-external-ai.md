# ADR 0002: Keep AI outside the executor

## Status

Accepted.

## Context

The owner wants to discuss channel organization with an AI assistant separately, then pass recommendations back to the tool. Embedding one AI provider would add cost, secrets, lock-in, and a larger attack surface.

## Decision

Export a strict `AuditPackage` and import a strict `ChangePlan`. The application never trusts prose and never lets an AI call provider APIs directly.

## Consequences

Any AI or human editor can participate. The executor remains deterministic, testable, and independent from model availability.
