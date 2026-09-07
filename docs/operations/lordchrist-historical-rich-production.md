# LordChrist historical rich production

This runbook is the production contract for Issue #561. It activates the already-merged provider-inert historical editorial lane without creating a second Telegram client or weakening the existing LordChrist quote feed.

## Exact live release

The only v1 live release is:

`content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-01.json`

It binds:

- project `lord-god-strength` / channel `@lordchrist`;
- exact Telegram chat `-1001295216957` and bot `8716602202` (`preaching_mp3_bot`);
- exact sealed historical cycle and all nine publication IDs;
- the independent 50-URL second verification pass;
- the existing LordChrist rich profile and target binding;
- Monday / Wednesday / Saturday at 19:17 `Europe/Moscow`;
- one provider mutation request maximum and zero blind retries;
- `backfill_policy=none`;
- canary-first activation;
- text-only v1 until exact historical image bytes/MIME/SHA-256 are separately bound in a successor release.

The merged #552 editorial manifest remains provider-inert. Live authority exists only in the separate exact #561 production release.

## Durable state

Historical live state is stored on the existing durable ref `state/lordchrist-telegram`, under:

`content/telegram/lordchrist/historical-editorial/publication-ledger.json`

It does not replace or rewrite the verified-quote ledger. Both tracks share the same channel-wide unresolved-effect guard and the same writer concurrency namespace.

Before the first canary, initialize this ledger provider-free from the exact merged release:

```bash
python -m video_channel_manager.telegram_historical_production ensure-ledger \
  --release content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-01.json \
  --ledger .state/lordchrist/content/telegram/lordchrist/historical-editorial/publication-ledger.json
```

Commit and fast-forward that exact ledger only to `state/lordchrist-telegram`. Initialization is not publication authority and performs no Telegram access.

## Release validation

Provider-free validation:

```bash
python -m video_channel_manager.telegram_historical_production preview \
  --release content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-01.json
```

The command fails closed if the manifest, second-pass verification, source/theology bindings, profile, target binding, post identities or schedule differ from the reviewed release.

The second verification pass must remain exactly 50 unique reviewed HTTPS records, only A/B+ grades, with exact nine-post coverage. It is release input, not an unbound research note.

## Canary

The only v1 manual historical mutation is the exact canary:

`lordchrist-history-spurgeon-down-grade`

The unified LordChrist publisher requires exact confirmation:

`PUBLISH:lordchrist-history-spurgeon-down-grade`

Before intent it must prove:

1. current `main` exact-SHA repository CI;
2. exact release and all immutable inputs;
3. the historical ledger is exact pending/impossible;
4. no unresolved legacy/research/historical LordChrist provider effect exists;
5. the previous rich canary is terminal `published / verified` evidence, not live authority;
6. the combined Moscow-date verified-publication limit is not exceeded;
7. fresh Telegram bot/channel preflight matches the exact chat and bot.

The workflow then persists durable intent to `state/lordchrist-telegram` before `sendRichMessage`. The provider path uses the repository `HttpxTelegramRichMutationProvider`, which performs one mutation request with transport retries fixed at zero. There is no `sendMessage` fallback.

The exact rich provider outcome must be archived before the durable ledger is changed from intent. `provider_effect=may_exist` is terminal blocking evidence and never authorizes a replay of the same publication identity.

A provider-proven no-effect outcome is stored as `failed_no_effect`. That publication identity remains terminal and is not retried, but it does not globally block later publication identities. Only unresolved `intent` or `may_exist` states stop the historical writer globally.

Only a verified outcome with exact returned chat, exact rich structure and a Telegram `message_id` sets `canary_verified_at_utc`.

## Automatic schedule

The recurring historical slot remains inert until the canary is durably verified.

After canary verification the exact cycle dates are:

- 2026-09-07
- 2026-09-09
- 2026-09-12
- 2026-09-14
- 2026-09-16
- 2026-09-19
- 2026-09-21
- 2026-09-23
- 2026-09-26

The recurring event is 19:17 `Europe/Moscow` on Monday, Wednesday and Saturday, with a 120-minute freshness window.

A delayed event outside that window returns `slot_expired_no_backfill`; it never selects the next old publication. A scheduled workflow rerun is forbidden by the first-attempt contract. An already verified slot cannot publish again.

The existing quote slots remain:

- 09:17 every day;
- 21:17 Tuesday / Friday / Sunday.

The tracks share one LordChrist writer namespace so their state operations cannot race.

## Replenishment / exhaustion

The production release has `replenishment_guard_remaining=1`.

When only the final current-cycle publication remains pending, scheduling fails closed with `successor_cycle_required_before_exhaustion` until a separately reviewed successor cycle is durably bound. The current production release itself is immutable: do not modify its digest or add a mutable `successor_cycle_verified` flag to it.

After the successor editorial bundle is separately reviewed and sealed in the repository, bind it provider-free into the current historical ledger:

```bash
python -m video_channel_manager.telegram_historical_production bind-successor \
  --release content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-01.json \
  --ledger .state/lordchrist/content/telegram/lordchrist/historical-editorial/publication-ledger.json \
  --successor-manifest content/telegram/lordchrist/historical-editorial/v1/cycles/<NEXT-CYCLE>/manifest.json \
  --verified-by "github-actions:<run-id>/<attempt>"
```

`bind-successor` performs no Telegram access. It materializes and validates the successor bundle, requires the same project/channel and reviewed 19:17 Monday/Wednesday/Saturday no-backfill cadence, rejects the current cycle as its own successor, and records the exact successor manifest Git blob plus queue/source-registry/theology digests in durable state. Commit and fast-forward the resulting ledger only to `state/lordchrist-telegram`, then read it back and confirm that the current release SHA-256 is unchanged.

Coverage can be inspected provider-free:

```bash
python -m video_channel_manager.telegram_historical_production coverage \
  --release content/telegram/lordchrist/historical-editorial/v1/production-release-2026-09-cycle-01.json \
  --ledger .state/lordchrist/content/telegram/lordchrist/historical-editorial/publication-ledger.json
```

A replenishment warning is operational debt; it is never authority to weaken evidence standards or invent a post.

## Historical images

The v1 live release is deliberately text-only. Existing historical image plans are editorial provenance, not transport proof.

A future image-bearing release must bind the exact reviewed media bytes, MIME and SHA-256 and re-prove rights/provenance. Do not fetch an arbitrary current page image at send time and do not substitute generated pseudo-historical imagery.

## No-replay rules

Never replay the same historical publication identity when:

- durable state is `intent`;
- provider effect is `may_exist`;
- the identity is terminal `failed_no_effect`;
- the workflow result is ambiguous;
- a slot expired;
- the exact release/source/theology/verification/profile/target binding drifted;
- current-main CI or fresh target proof cannot be established.

Resolve ambiguity through exact read-only evidence under a new reviewed recovery scope; do not infer provider absence from a failed runner.
