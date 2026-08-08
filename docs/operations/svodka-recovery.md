# Svodka Telegram recovery

Last reviewed: 2026-08-08

This runbook covers recovery only. It never authorizes a Telegram provider mutation.

## Shared-bot reminder

`@preaching_mp3_bot` (bot id `8716602202`) intentionally serves multiple Telegram channels. A shared bot token is expected. Never infer a destination from the secret name. The Svodka destination is selected by the Svodka profile, exact numeric chat id, pinned binding, immutable release and `state/svodka-telegram` ledger.

## Recovery classes

### 1. Proven local/pre-provider failure

Examples: missing bot token in the job environment or another local validation failure before any HTTP provider call.

Expected outcome:

- provider effect: `not_dispatched`;
- retryable: `true` only when absence is proven;
- applying the exact outcome clears the intent and returns the entry to `pending`;
- a new manual run may retry only while the same immutable publication window is still open.

### 2. Publication window expired before dispatch

Never send the stale item late.

Use `Svodka skip expired publication windows` with exact release digest and confirmation. It has no Telegram secret and may only move consecutive already-expired `pending` entries to:

- state: `skipped`;
- provider effect: `impossible`.

The scheduled publisher performs the same state-only stale check before any Telegram operation.

### 3. Durable intent persisted, provider send step proven skipped

Use `Svodka reconcile skipped provider send` only for this exact case.

The workflow does not trust operator recollection. It uses GitHub Actions REST metadata and requires:

- exact source run id and run attempt;
- exact release digest and publication id;
- original run from `main`;
- recognized Svodka provider workflow path;
- source run head SHA equals the persisted dispatch provenance;
- durable intent step conclusion is exactly `success`;
- provider send step conclusion is exactly `skipped`;
- no prior `outcome.json` exists for the dispatch.

Only then it writes an evidence file, constructs a `confirmed_absent` retryable outcome, applies it to the ledger, and durably commits the result. It has GitHub Actions read access but no Telegram secret and performs no Telegram API call.

### 4. Provider send started, timed out, was cancelled, returned a mismatching message, or otherwise may have produced a remote effect

Do not use skipped-send reconciliation.

Expected state is `dispatching/unknown` with `provider_effect=may_exist`. Blind retry is forbidden. A send step conclusion of `cancelled`, `failure`, `success`, missing/ambiguous step evidence, or an already-recorded outcome is not proof of absence.

Telegram Bot API does not provide a general `getMessage(message_id)` method for this recovery problem. Reconcile the actual channel state manually/read-only and preserve the original durable intent. Do not reset the ledger merely to make the queue move.

## Single-writer rule

Ledger initialization, stale-window recovery, skipped-send reconciliation, manual canary and scheduled publication all use the same concurrency group: `svodka-telegram-publisher`, `cancel-in-progress: false`.

No recovery workflow may create an independent Telegram client or a second state branch.
