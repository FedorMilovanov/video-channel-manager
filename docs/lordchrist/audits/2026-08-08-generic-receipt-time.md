# 2026-08-08 generic receipt timestamp provenance audit

## Finding

The generic Telegram transport checked target-proof freshness and populated `GenericSendReceipt.verified_at_utc` from the same timestamp captured before `sendMessage` / `sendPoll`.

That was safe for dispatch ordering, but semantically weak provenance: the recorded `verified_at_utc` (and later ledger `published_at_utc`) could precede the actual successful provider response by network latency.

## Fix

- target-proof freshness is still checked with a timestamp captured before the provider mutation;
- when production callers omit the optional deterministic `now` override, the verified receipt timestamp is captured only after the provider response, exact target identity, payload semantics, and positive message id have all been verified;
- an explicit `now=` remains supported for deterministic tests and historical fixtures;
- mutation retries remain zero and provider call count is unchanged.

## Regression invariant

For normal production calls, `verified_at_utc` must not precede the provider response that established the verified receipt.
