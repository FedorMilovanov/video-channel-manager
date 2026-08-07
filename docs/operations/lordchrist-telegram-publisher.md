# GitHub-публикатор цитат для @lordchrist

Дата актуализации: 2026-08-07  
Проект: `lord-god-strength`  
Канал: `@lordchrist`

## Текущее production-состояние

Проверенный manual canary:

```text
publication_id: lordchrist-bunyan-cross-burden
workflow run:   31177350161
message_id:     1470
message_url:    https://t.me/lordchrist/1470
state:          published
provider_effect: verified
```

Отдельный GitHub-hosted formatting/autonomy test John Owen также успешно опубликован как `message_id=1471`; он не входит в основную 30-постовую очередь и хранится отдельным one-off state evidence.

Основная очередь остаётся immutable:

```text
queue digest:
sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20
```

Strict-next item основной очереди после canary:

```text
lordchrist-bunyan-fire-grace
```

## Автономный production schedule

Canonical config:

`content/telegram/lordchrist/production-schedule.json`

Production schedule включён в version control и не требует открытого домашнего ПК, PowerShell-сессии или ручного переключения repository variables.

```text
enabled: true
not_before_moscow_date: 2026-08-08
timezone: Europe/Moscow
primary: 09:17
catch-up: 21:17
daily_verified_limit: 1
```

Scheduled-run разрешён только если checked-in production config совпадает с:

- exact project/channel identity;
- exact numeric channel ID `-1001295216957`;
- exact bot ID `8716602202`;
- exact bot username `preaching_mp3_bot`;
- approved queue digest;
- current reviewed presentation policy ID + SHA;
- one-publication-per-Moscow-day contract.

Manual `publish` остаётся отдельно закрыт repository variable `LORDCHRIST_POSTING_ENABLED=true` и exact confirmation `PUBLISH:<publication_id>`. Scheduled production не зависит от этого manual toggle.

## Presentation v2

Canonical policy:

`content/telegram/lordchrist/presentation-policy.json`

Current policy ID:

```text
lordchrist-editorial-v2
```

Правила:

1. source quote paragraphs сохраняются дословно;
2. самый длинный прямой фрагмент `«…»` в body становится **bold**; при равной длине выбирается первый;
3. остальные прямые фрагменты становятся *italic*;
4. если direct quotes нет, body emphasis не выдумывается;
5. **Автор**, *«Название труда»*;
6. visible `©` не публикуется;
7. между attribution и hashtags дополнительный пустой ENTER (`\n\n\n`);
8. hashtags сохраняются;
9. provider encoding — Telegram HTML с escaping source symbols;
10. postflight проверяет exact bold/italic entities в Telegram UTF-16 offsets.

Актуальные human-readable образцы:

`docs/operations/lordchrist-telegram-presentation-v2.md`

`presentation-v1` — историческая политика первого canary и больше не является production-инструкцией.

## Source queue и presentation — разные слои

`verified-30-posts.json` не переписывается из-за оформления. Source payload SHA и queue digest остаются исторически стабильными.

Перед `sendMessage` renderer создаёт exact `rendered.json` с:

- source payload SHA;
- presentation policy ID/SHA;
- provider payload SHA;
- plain text;
- HTML text;
- expected bold/italic entities;
- link-preview policy.

`dispatch.json` и `rendered.json` сначала сохраняются в `state/lordchrist-telegram`, читаются обратно с remote и проверяются. Только после этого provider mutation становится достижимой.

## Telegram identity preflight

Каждый real scheduled/manual publish выполняет live read-only proof:

```text
getMe
getChat(exact numeric channel ID)
getChat(@lordchrist)
getChatAdministrators(return_bots=true)
```

Требуется одновременно:

```text
bot id: 8716602202
bot username: preaching_mp3_bot
channel id: -1001295216957
channel username: lordchrist
chat type: channel
status: administrator/creator
can_post_messages: true
```

Если proof не совпадает, `sendMessage` недостижим.

## Durable state и exactly-once guards

State branch:

```text
state/lordchrist-telegram
```

Production ledger:

```text
content/telegram/lordchrist/publication-ledger.json
```

Production loader fail-closed:

- missing ledger → STOP;
- invalid schema → STOP;
- queue digest mismatch → STOP;
- missing/extra publication IDs → STOP;
- payload SHA drift → STOP;
- unresolved `dispatching/unknown + may_exist` → strict queue STOP.

Никакой production auto-initialization потерянного ledger не существует.

## Порядок одного scheduled publish

```text
GitHub schedule on default main
→ install minimal pinned runtime
→ validate production schedule release binding
→ checkout state read-only
→ validate immutable queue + strict ledger
→ live read-only Telegram target proof
→ validate production gates
→ enable state writer
→ daily Moscow quota guard
→ require verified manual canary
→ select strict-next pending item
→ render exact presentation-v2 payload
→ write dispatching/may_exist intent + rendered evidence
→ push exact intent to remote state branch
→ read remote intent/rendered evidence back
→ verify exact bytes and provenance
→ sendMessage exactly once
→ verify exact channel + plain text + formatting entities + positive message_id
→ persist exact result to state branch
```

## Daily guard и два окна

Manual и scheduled используют один и тот же global guard:

```text
already published/verified on current Europe/Moscow date
=> no second dispatch that date
```

Поэтому 21:17 — только catch-up. Если 09:17 успешно опубликовал пост, вечерний run не может отправить следующий.

Scheduled workflow re-run (`GITHUB_RUN_ATTEMPT > 1`) запрещён. После infrastructure failure не использовать blind rerun; дождаться следующего normal schedule либо провести отдельную exact-bound manual operation только после проверки durable state.

## Provider outcome policy

```text
preflight transport retries: 2
sendMessage transport retries: 0
```

- `published / verified` — exact Telegram result доказан;
- `pending / not_dispatched` — доказано, что provider mutation не произошла;
- `pending / confirmed_absent` — явный retryable reject, например 429;
- `failed / confirmed_absent` — terminal provider reject;
- `unknown / may_exist` — timeout/5xx/malformed response/postflight mismatch после возможной отправки.

`unknown / may_exist` никогда не retried автоматически.

## Runtime

Production работает на GitHub-hosted `ubuntu-latest` с:

```text
PYTHONPATH=src
requirements/telegram-publisher.txt
```

Текущий minimal runtime exact-pinned. BotFather secret передаётся только provider-facing preflight/send steps, а не всему job.

## GitHub schedule caveat

GitHub `schedule` работает только на default branch и использует latest default-branch commit. GitHub может задерживать scheduled events при высокой Actions-нагрузке и в редких случаях drop queued jobs; поэтому используются два разнесённых окна `09:17` и `21:17`, а не одна попытка в начале часа.

В публичном репозитории schedule может быть автоматически отключён после 60 дней repository inactivity. Для текущей 30-дневной кампании это не ожидаемый фактор, но правило нужно учитывать при будущих длительных паузах.

## Операционные запреты

Не делать blind `Re-run` после `sendMessage` failure/timeout.

Не редактировать вручную production ledger так, чтобы `unknown/may_exist` становился `pending` без evidence reconciliation.

Не заменять `verified-30-posts.json` поверх существующего ledger.

Не менять bot/channel identity только через repository variables: scheduled production config также release-bound к exact audited identity.

Не считать зелёный preview доказательством Telegram readiness; реальный proof даёт live read-only preflight.

## Следующая кампания после 30/30

Нельзя просто заменить JSON очереди. Нужен отдельный reviewed campaign rollover:

1. закрыть текущие entries verified/skipped/reconciled;
2. сохранить queue/ledger/dispatch evidence как immutable history;
3. подготовить новую verified source queue;
4. получить новый queue digest;
5. explicit initialize новый ledger;
6. обновить production schedule release binding;
7. выполнить read-only preflight;
8. только затем разрешать следующий campaign.
