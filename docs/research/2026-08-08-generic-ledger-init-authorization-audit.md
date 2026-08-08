# 2026-08-08 generic ledger initialization authorization audit

## Finding

The production Svodka ledger-init CLI already required an authorized immutable release before it called `initialize_ledger()`. The lower-level Python helper itself did not repeat that requirement, so future direct library callers could construct publication state from an unreviewed release candidate even though the live workflow could not.

This was defense-in-depth debt rather than an active provider path: the current workflow enters through the guarded CLI, the Svodka profile remains write-disabled, no approved release exists, and no Svodka publication ledger exists.

## Fix

`initialize_ledger()` now fails closed unless `release.release_authorized` is true. The existing CLI guard and explicit digest confirmation remain in place; the library layer is no longer weaker than its production caller.

A focused regression calls `initialize_ledger()` directly with the canonical unreviewed Svodka candidate and requires `ValueError` before any ledger is created.

## Safety boundary

The change does not create or modify durable state, authorize a release, alter Telegram target identity, expose a credential, change scheduling, or perform provider access. It only removes a future direct-library bypass around release authorization.

## Verification discipline

This record was added after skipped-send recovery was hardened to exact GitHub run-attempt provenance. Final merge requires a new synthetic-merge full CI on the then-current `main`; any older queued CI from before that main advancement is diagnostic only.
