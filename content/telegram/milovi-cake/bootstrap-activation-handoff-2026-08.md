# Milovi Cake Telegram bootstrap activation handoff

Status: provider-inert preparation only. This document does not authorize Telegram writes.

## Exact production identity

- Project: `milovi-cake`
- Public channel: `@MiloviCake`
- Numeric chat id expected from fresh discovery: `-1002215328390`
- Bot id expected from fresh discovery: `8716602202`
- Bot username expected from fresh discovery: `preaching_mp3_bot`
- Public write window: `09:00–21:00 Europe/Moscow`
- Reviewed cadence: at most two verified publications per day, at `10:30` and `20:00` Moscow for the bootstrap schedule
- Durable state branch: `state/milovi-cake-telegram`

## Current fail-closed gates

The bootstrap publisher on `main` remains inert while any of these gates is absent or false:

1. `content/telegram/channels/milovi-cake.json` must explicitly set `provider_writes_authorized=true` in a separately reviewed activation change. It is intentionally false during preparation.
2. `content/telegram/channels/milovi-cake-target-binding.json` must be created from a fresh provider-read-only proof produced by `milovi-telegram-target-discovery.yml`. Do not synthesize this file from remembered ids.
3. `content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json` must exactly match the compiler output, bind the fresh target-binding digest, and contain explicit review metadata.
4. The durable `state/milovi-cake-telegram` branch must contain the exact release ledger expected by the authorized release.
5. The first provider-capable run must be an explicitly confirmed fresh frozen manual release canary. A deleted historical p18 canary is not eligible.
6. Scheduled publication remains blocked until that release canary is terminally provider-verified.
7. Every provider-capable run must still pass the 09:00–21:00 Moscow gate, exact-current-main quality gates, strict-next freshness, fresh target preflight, durable intent-before-send, and no-blind-retry rules.

## Read-only target discovery

Run `.github/workflows/milovi-telegram-target-discovery.yml` on current `main` when a fresh binding is required. It may call Telegram only through `getMe`, `getChat`, and exact `getChatMember` preflight logic. It must not call `sendMessage`, `sendPhoto`, `sendPoll`, or any other provider mutation.

The artifact is a candidate only. Before committing a binding, inspect that it proves:

- exact `@MiloviCake` public/numeric pair;
- exact bot id and username;
- channel type;
- administrator/creator membership;
- `can_post_messages=true` when status is administrator;
- `provider_write_performed=false`;
- fresh discovery timestamp.

## Editorial invariants that activation must not weaken

- Milovi Cake publishes its own cakes and desserts.
- Milovi School is a separate educational/SEO/content project for interesting reading.
- Milovi School must never be used as evidence of Milovi Cake recipe origin, cuisine, production process, or technique.
- The first ten canonical bootstrap posts contain zero Milovi School items.
- The manually deleted erroneous canary is historical transport evidence only and must never be replayed.
- No catch-up publication is allowed for missed slots.

## Next-wave dependency

The twelve-item follow-on wave and its exact nine-photo transport proof are already frozen provider-inert. The follow-on compiler and read-only readiness gate must continue to require terminal verification of `milovi-bootstrap-010` plus fresh Cake/School source revalidation before any follow-on release candidate can be promoted.
