# LordChrist historical rich production

This runbook is the operational contract for Issue #561. The active candidate is the human-editorial v2 cycle created after the owner rejected and deleted the technically successful v1 canary message 1514.

## Production authority

The exact candidate release is:

`content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-02.json`

It binds project `lord-god-strength`, channel `@lordchrist`, the exact Telegram target, nine new `-v2` publication identities, the sealed v2 manifest, the 50-URL second verification pass, the existing rich profile and target binding, one provider mutation request maximum, zero blind retries, and `backfill_policy=none`.

The old `production-release-2026-09-cycle-01.json` and the deleted Telegram message 1514 remain audit evidence only. They are not authority for another provider mutation or recurring schedule.

## Canary is out of band

The only replacement canary is:

`lordchrist-history-spurgeon-down-grade-1887-v2`

It is intentionally outside the recurring date map. Its durable ledger entry uses `scheduled_date_moscow=2026-09-07`, the exact Moscow date on which the sealed manual-canary authorization window begins. That audit date does not make the canary schedulable: the release restricts it to the exact manually confirmed canary path.

The canary authorization window is sealed in the release. Manual dispatch requires the exact publication identity, first workflow attempt, current-main CI proof, fresh target proof, clear shared LordChrist state, and exact confirmation `PUBLISH:lordchrist-history-spurgeon-down-grade-1887-v2`.

The canary uses the existing `lordchrist-telegram-poster.yml` historical job. There is no second Telegram transport workflow.

## Two-phase activation

A successful Telegram response is only transport verification. It does not arm recurring publication.

For v2 the durable state fields are:

- `canary_transport_verified_at_utc` — set only after exact provider verification;
- `canary_editorial_approved_at_utc` — remains null until explicit owner approval;
- `canary_editorial_approved_by` — records the approving actor;
- `canary_verified_at_utc` — remains null after transport success and is populated only by the provider-free editorial approval transition.

The owner must review the actual reader-facing canary message before approval. Approval is bound to the exact durable Telegram `message_id`; a different ID fails closed.

The provider-free workflow is `.github/workflows/lordchrist-historical-editorial-approval.yml`. It shares concurrency group `lordchrist-telegram-publisher`, contains no Telegram bot token and has no preflight/send path. It requires exact confirmation `APPROVE-HISTORY:<message_id>`, current-main CI, exact release validation and durable message-ID readback before persisting approval.

## Recurring schedule after approval

The canary does not consume the first recurring Monday slot. After editorial approval, the remaining eight publication identities are mapped exactly to 19:17 `Europe/Moscow`:

- 2026-09-14 — Bunyan v2;
- 2026-09-16 — Judson v2;
- 2026-09-19 — Spurgeon cholera v2;
- 2026-09-21 — Carey v2;
- 2026-09-23 — Fuller v2;
- 2026-09-26 — Tyndale v2;
- 2026-09-28 — Stam v2;
- 2026-09-30 — Sattler v2.

The release seals these mappings as `recurring_publication_ids` and `recurring_scheduled_dates_moscow`. The facade materializes the durable ledger as one manual-only canary audit date followed by the eight exact recurring dates. It never dynamically chooses an older pending post.

A recurring event before editorial approval returns `canary_not_verified`. A late event outside the 120-minute freshness window returns `slot_expired_no_backfill`. A verified exact slot is not replayed.

The existing quote slots remain unchanged: 09:17 daily and 21:17 Tuesday/Friday/Sunday. Both tracks continue to share the single `lordchrist-telegram-publisher` concurrency namespace.

## Durable state

Historical state remains on `state/lordchrist-telegram` at:

`content/telegram/lordchrist/historical-editorial/publication-ledger.json`

After the v2 code is merged, archive the existing v1 historical ledger as audit evidence and initialize a pristine ledger from the exact merged v2 release provider-free. Do not edit an old release-bound ledger into a v2 ledger by hand.

The v2 ledger must bind the exact release SHA-256 and contain all nine publication identities. The canary entry starts pending/impossible with the exact 2026-09-07 audit date; the remaining entries start pending/impossible with their exact recurring dates.

## Provider-effect rules

Before any provider call, durable intent must already be present on the shared state branch. The rich transport performs one mutation request with transport retries fixed at zero.

The exact provider outcome is archived before durable result mutation.

`may_exist` and unresolved `intent` block the writer globally. `failed_no_effect` is terminal for that publication identity and is never retried, but it does not permanently block later identities.

Never infer provider absence from a failed runner. Ambiguous state requires explicit read-only recovery evidence under a separately reviewed recovery scope.

## Replenishment

The release retains `replenishment_guard_remaining=1`. When only the final recurring publication remains pending, scheduling fails closed until a separately reviewed successor historical cycle is durably bound.

Successor binding is provider-free state. It must bind the exact successor manifest Git blob plus queue/source-registry/theology digests while leaving the current release immutable.

## Media

The v2 production release remains text-only until exact historical image bytes, MIME, SHA-256, rights and provenance are separately sealed. Existing image plans are editorial provenance only and are not transport authority.

Do not fetch arbitrary current page imagery at send time and do not substitute generated pseudo-historical images.

## Closure criteria for Issue #561

Do not close Issue #561 on merge alone. Closure requires all of the following:

1. final exact-head CI is terminal green and the PR is merged from the expected head;
2. the pristine v2 ledger is durably initialized and read back from `state/lordchrist-telegram`;
3. the exact v2 canary is shown to the owner before dispatch;
4. at most one canary provider mutation occurs and the durable result is `published / verified` with exact message ID and URL;
5. the owner explicitly approves that exact canary through the provider-free approval transition;
6. durable readback proves `canary_verified_at_utc == canary_editorial_approved_at_utc`;
7. scheduler readback proves the first recurring slot is Bunyan v2 on 2026-09-14, not the already-published canary;
8. no unresolved LordChrist provider effects remain.
