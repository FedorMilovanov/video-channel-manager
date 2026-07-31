## Summary

Describe the operational or code change.

## Source of truth

- [ ] I read `AGENTS.md`.
- [ ] I read `docs/operations/current-state.md` for YouTube/VK work.
- [ ] Exact source and target IDs are recorded.

## Safety

- [ ] Read-only by default, or write scope is explicit.
- [ ] Ambiguous items are excluded from automated writes.
- [ ] Unknown outcomes stop automatic retry.
- [ ] Ledger, result, and recovery behavior are documented.
- [ ] Covered and uncovered provider surfaces are stated.

## Operational artifacts

- [ ] Manifest SHA-256 is recorded.
- [ ] Entrypoint and required siblings exist at documented paths.
- [ ] PowerShell launchers use `$PSScriptRoot` and do not depend on the caller's working directory.
- [ ] ZIP handoffs pass `scripts/verify_operational_bundle.py`.
- [ ] No tokens, secrets, media, ledgers, or local logs are committed.

## Verification

- [ ] Tests added or updated.
- [ ] CI passes.
- [ ] `docs/operations/current-state.md` is updated when operational state changes.
