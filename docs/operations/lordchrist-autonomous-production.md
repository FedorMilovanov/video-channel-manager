# Lordchrist autonomous production

## Production state

The main 30-post publisher is enabled for autonomous scheduled publication from **2026-08-08 (Europe/Moscow)**.

Canonical activation is version-controlled in:

`content/telegram/lordchrist/production-schedule.json`

The production config is bound to the approved queue digest and requires a daily verified limit of exactly one publication.

## Schedule

- primary window: **09:17 Europe/Moscow**
- catch-up window: **21:17 Europe/Moscow**
- maximum verified publications: **1 per Moscow calendar date**

GitHub-hosted runners execute the publication workflow. A home computer, PowerShell session, or local Telegram process is not required for text publication.

## Activation semantics

Scheduled publication no longer depends on manually setting `LORDCHRIST_POSTING_ENABLED` or `LORDCHRIST_SCHEDULE_ENABLED` to true.

For a `schedule` event, the workflow must validate the checked-in production config before any live Telegram preflight or provider mutation. Before `not_before_moscow_date`, the scheduled run is a safe no-op/preview. Once active, the scheduled path still requires all existing target proof, strict ledger, daily quota, durable intent, exact rendered payload, exact `sendMessage` result verification, and durable result persistence.

Manual `publish` remains separately guarded by `LORDCHRIST_POSTING_ENABLED=true` and the exact `PUBLISH:<publication_id>` confirmation. This preserves an independent manual emergency gate without making autonomous cron depend on an operator toggle.

## Evidence before activation

- primary queue canary: message `1470`, `published / verified`
- formatted GitHub-hosted one-off presentation test: message `1471`, `published / verified`
- approved queue digest: `sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20`

## Expected first autonomous publication

The first eligible production window is **2026-08-08 09:17 Europe/Moscow**. The expected strict-next queue entry is `lordchrist-bunyan-fire-grace`, unless the durable ledger changes before that window.

The 21:17 window is a catch-up window only: if a publication is already verified on that Moscow date, the global daily guard must produce no provider send.
