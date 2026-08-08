# Svodka Telegram production readiness

Last reviewed: 2026-08-08

## Current state

`@deep_info_life` is **not live-enabled** yet.

- channel profile: `content/telegram/channels/svodka.json`
- exact target binding: `content/telegram/channels/svodka-target-binding.json`
- canonical pilot queue: `content/telegram/svodka/draft-14-posts-2026-08.json`
- state branch: `state/svodka-telegram`
- approved release path (must not exist before review): `content/telegram/svodka/approved-release-2026-08.json`
- current profile gate: `provider_writes_authorized=false`
- scheduled publisher: intentionally absent until a verified manual canary exists

## Stable workflow split

1. `Svodka quality` — read-only CI. No Telegram secret, no repo mutation, no provider mutation. It validates the canonical queue, renders all 14 provider payloads and uploads a target-bound write-disabled review candidate.
2. `Svodka Telegram preview and preflight` — manual preview / fresh read-only Telegram identity proof.
3. `Svodka initialize publication ledger` — manual state-only operation. It requires an exact committed authorized release digest and creates the ledger once on `state/svodka-telegram`. It has no Telegram secret and cannot send.
4. `Svodka exact manual canary` — manual one-publication provider mutation. It is fail-closed unless the profile is write-enabled, the committed release is authorized, the exact release digest/publication/confirmation match, the ledger already exists, and a fresh Telegram preflight passes. It persists intent before `send-once` and persists the exact outcome afterward.
5. Scheduled publication — added only after the ledger contains a verified manual canary for the same bot/channel. The generic state layer also enforces this invariant.

## Activation checklist

The next production activation must happen in this order:

1. `Svodka quality` green on the exact main SHA.
2. Manual read-only preflight green against chat `-1003527567039`, bot `8716602202`, `@preaching_mp3_bot`.
3. Review the generated 14-item candidate and record its exact digest.
4. Commit an authorized immutable release generated from that exact candidate; do not rebuild it from changed draft data during deployment.
5. Change only the profile write gate to `true`. The profile stable digest intentionally ignores the write-enable bit, so binding identity remains unchanged.
6. Initialize the state ledger once with `INITIALIZE:<release_digest>`.
7. Run one exact manual canary with `CANARY:<publication_id>:<release_digest>`.
8. Verify durable ledger state `published`, `provider_effect=verified`, exact message id/url, chat id, bot id and manual dispatch provenance.
9. Only then add/enable the 10:30 and 19:30 Europe/Moscow scheduled publisher for the approved release.

## Blocking conditions

Do not schedule or retry automatically if any of these are true:

- quality or preflight is not green;
- approved release is absent or digest differs;
- profile remains write-disabled;
- ledger is absent or belongs to another release digest;
- first unresolved entry is `dispatching`, `unknown` or `failed`;
- provider outcome is `may_exist`;
- manual canary is not verified;
- a scheduled workflow is a rerun rather than attempt 1;
- the requested item is not the strict next item;
- daily verified limit is already consumed.

## Editorial boundary

The pilot facts were hardened directly in the canonical queue. The previous self-mutating repair workflow was removed. Source and wording changes must be committed as ordinary reviewed content changes before candidate generation. Dynamic web results are never auto-published.

Technical and factual source audit: `docs/research/2026-08-08-svodka-technical-verification-ledger.md`.
