# GitHub-публикатор цитат для @lordchrist

Дата актуализации: 2026-08-07  
Проект: `lord-god-strength`  
Канал: `@lordchrist`  
Hardening: issue `#155`, PR `#160`  
Presentation v1: issue `#163`

## Текущее production-состояние

Первый exact-bound canary уже выполнен и подтверждён:

```text
publication_id: lordchrist-bunyan-cross-burden
workflow run:   31177350161
message_id:     1470
message_url:    https://t.me/lordchrist/1470
state:          published
provider_effect: verified
```

Canary был отправлен прежним plain-text payload, после чего его оформление было вручную отредактировано в Telegram. Durable ledger сохраняет историческую правду именно о первоначальном bot-send; ручная редакционная правка не переписывает provenance уже состоявшейся отправки.

До отдельного решения о запуске расписания держать:

```text
LORDCHRIST_POSTING_ENABLED=false
LORDCHRIST_SCHEDULE_ENABLED=false
```

Merge, green CI или preview сами по себе не включают публикацию.

## Архитектура

- `content/telegram/lordchrist/verified-30-posts.json` — immutable source queue из 30 проверенных публикаций;
- `content/telegram/lordchrist/presentation-policy.json` — canonical presentation policy `lordchrist-editorial-v1`;
- `src/video_channel_manager/telegram_models.py` — source queue/state/dispatch schemas;
- `src/video_channel_manager/telegram_presentation.py` — deterministic Telegram presentation renderer;
- `src/video_channel_manager/telegram_state.py` — fail-closed ledger и state transitions;
- `src/video_channel_manager/telegram_transport.py` — единственный Telegram Bot API transport;
- `src/video_channel_manager/telegram_publisher.py` — публичный facade;
- `src/video_channel_manager/telegram_cli.py` — package-owned CLI;
- `.github/workflows/lordchrist-telegram-poster.yml` — production workflow;
- `state/lordchrist-telegram` — durable state branch;
- `requirements/telegram-publisher.txt` — минимальный exact-version runtime.

Домашний компьютер для текстовых публикаций не требуется.

## Два независимых слоя: источник и оформление

### Source queue

`verified-30-posts.json` остаётся неизменной после первого canary. Её digest:

```text
sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20
```

Source queue содержит проверенный перевод, attribution в историческом source-card формате и доказательство первичного источника. Изменение source text меняет payload SHA и queue digest и поэтому блокируется existing ledger.

### Presentation v1

Публикуемый Telegram payload строится детерминированно поверх source card. Presentation policy не изменяет цитату и не меняет source queue digest.

Canonical правила `lordchrist-editorial-v1`:

1. абзацы самой цитаты сохраняются дословно;
2. первый прямой фрагмент `«…»` в теле — **bold**;
3. все последующие прямые фрагменты `«…»` в теле — *italic*;
4. если прямых фрагментов в теле нет, искусственное выделение в теле не добавляется;
5. attribution: **Автор**, *«Название труда»*;
6. видимый `©` из publication rendering удаляется;
7. hashtags сохраняются без изменения;
8. после attribution перед hashtags используется дополнительный пустой ENTER: `\n\n\n`;
9. Telegram transport использует `parse_mode=HTML`;
10. link preview отключён.

HTML используется только как provider encoding. Renderer экранирует пользовательский/source текст (`&`, `<`, `>`), поэтому исходный текст не может превратиться в произвольную Telegram HTML-разметку.

## Canonical пример

Человек видит:

```text
И увидел я во сне: едва Христианин подошёл ко кресту, как бремя сорвалось с его плеч, упало со спины и покатилось вниз, пока не достигло входа в гробницу; там оно исчезло, и больше я его не видел.

Тогда Христианин возрадовался и почувствовал облегчение. С весёлым сердцем он сказал: «Он дал мне покой Своей скорбью и жизнь Своей смертью». Христианин остановился, чтобы смотреть и дивиться: ему казалось поразительным, что один вид креста освободил его от бремени. Он смотрел снова и снова, пока слёзы не потекли по его щекам. И когда он стоял, глядя и плача, к нему подошли трое Сияющих и приветствовали его словами: «Мир тебе». Первый сказал: «Прощаются тебе грехи твои»; второй снял с него лохмотья и облек в перемену одежд; третий поставил знак на его челе и дал ему запечатанный свиток — читать его в пути и предъявить у Небесных ворот.

Джон Беньян, «Путешествие Пилигрима»


#ДжонБеньян #Крест #Прощение #Спасение
```

Formatting entities поверх этого plain text:

- **«Он дал мне покой Своей скорбью и жизнь Своей смертью»**;
- *«Мир тебе»*;
- *«Прощаются тебе грехи твои»*;
- **Джон Беньян**;
- *«Путешествие Пилигрима»*.

Полный human-readable образец находится в `docs/operations/lordchrist-telegram-presentation-v1.md`.

## Presentation evidence до sendMessage

Новый production dispatch создаёт два независимых immutable proofs:

1. source `dispatch.json`;
2. exact `rendered.json`.

Они сохраняются до Telegram mutation по пути:

```text
state/lordchrist-telegram:
content/telegram/lordchrist/dispatches/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>/
  dispatch.json
  rendered.json
```

`rendered.json` содержит:

- exact `publication_id`;
- source payload SHA;
- presentation policy ID;
- presentation policy SHA;
- exact provider payload SHA;
- plain text;
- exact HTML text;
- ожидаемые `bold` / `italic` Telegram entities;
- link-preview policy.

Workflow сначала push'ит ledger intent + оба evidence files в state branch, затем читает их обратно с remote, byte-сравнивает и выполняет `verify-intent` + `verify-rendered`. Только после этого `sendMessage` становится достижим.

## Telegram postflight presentation proof

HTTP 200 недостаточен.

`published / verified` допускается только когда Telegram вернул одновременно:

- exact `chat.id`;
- exact channel username;
- `chat.type=channel`;
- exact rendered **plain text**;
- exact ожидаемые `bold`/`italic` entities с Telegram UTF-16 offsets;
- positive `message_id`.

Telegram может дополнительно вернуть свои entities, например `hashtag`; они разрешены. Но набор `bold`/`italic` обязан точно совпасть с reviewed renderer.

Если Telegram вернул сообщение, но plain text или formatting entities отличаются, outcome считается:

```text
state=unknown
provider_effect=may_exist
```

Blind retry в таком состоянии запрещён.

## Production bot identity

Текущий проверенный bot:

```text
bot username: preaching_mp3_bot
bot id:       8716602202
```

Target:

```text
channel: @lordchrist
chat id: -1001295216957
type: channel
```

Read-only preflight требует exact ID + username для bot и channel, `getChatAdministrators(..., return_bots=true)`, administrator/creator status и `can_post_messages=true`.

Для долгосрочной production-изоляции отдельный cloud-only publisher bot остаётся предпочтительной архитектурой, но смена bot identity требует отдельной reviewed configuration transition и нового preflight; существующий verified canary нельзя автоматически переносить на другой bot ID.

## GitHub configuration

### Secret

```text
LORDCHRIST_TELEGRAM_BOT_TOKEN
```

Secret не находится в workflow-level env. Он передаётся только provider-facing read-only preflight и send step.

### Repository variables

```text
LORDCHRIST_TELEGRAM_CHAT_ID
LORDCHRIST_TELEGRAM_BOT_ID
LORDCHRIST_TELEGRAM_BOT_USERNAME
LORDCHRIST_APPROVED_QUEUE_DIGEST
LORDCHRIST_POSTING_ENABLED
LORDCHRIST_SCHEDULE_ENABLED
```

`LORDCHRIST_TELEGRAM_BOT_USERNAME` указывается без `@`.

## Три режима workflow

### `preview`

Полностью offline:

```text
action: preview
publication_id: пусто
confirm: пусто
```

Показывает strict-next source item и одновременно его exact presentation-v1 view:

- source payload SHA;
- presentation policy SHA;
- provider payload SHA;
- rendered plain text;
- HTML provider text;
- expected formatting entities.

Telegram calls: `0`.

### `preflight`

Live, но read-only:

```text
action: preflight
publication_id: пусто
confirm: пусто
```

Работает при обоих write-gate `false`. Последовательно доказывает bot/channel/admin identity. `sendMessage` недостижим.

### `publish`

Один exact-bound manual post:

```text
action: publish
publication_id: <strict-next exact ID>
confirm: PUBLISH:<strict-next exact ID>
```

Требует:

```text
LORDCHRIST_POSTING_ENABLED=true
```

Stale manual run не может перейти к следующему post: exact requested publication ID обязан совпадать со strict-next item.

## Глобальное ограничение на сутки

Для manual и scheduled одинаково:

```text
verified publication on current Europe/Moscow date
=> no second dispatch that date
```

Первый canary уже опубликован 2026-08-07, поэтому следующий item не должен публиковаться в тот же московский день.

## Scheduled mode

Окна:

```text
09:17 Europe/Moscow
21:17 Europe/Moscow
```

Второе окно — catch-up; daily guard не позволяет получить второй verified post за день.

Schedule разрешается только при:

```text
LORDCHRIST_SCHEDULE_ENABLED=true
LORDCHRIST_POSTING_ENABLED=true
```

и наличии verified manual canary с тем же exact bot ID и chat ID.

Scheduled workflow re-run (`GITHUB_RUN_ATTEMPT > 1`) запрещён. После инфраструктурной ошибки ждать следующего normal cron-run либо использовать отдельный exact-bound manual operation после проверки state.

Concurrency:

```text
queue: single
cancel-in-progress: false
```

## Fail-closed ledger

Production не создаёт потерянный state автоматически.

`load_ledger()` останавливает workflow, если:

- ledger отсутствует;
- JSON/schema невалидны;
- queue digest отличается;
- coverage publication IDs отличается от source queue;
- payload SHA entry отличается от immutable source card.

Published entries требуют complete durable provenance, exact target identity, positive message ID, canonical public URL и timezone-aware timestamps.

## Durable intent before provider mutation

Порядок future publish:

```text
source queue + ledger validation
→ presentation policy validation
→ target preflight
→ daily guard
→ exact publication-id guard
→ create source dispatch
→ render exact provider payload
→ save ledger dispatching/may_exist
→ persist ledger + dispatch.json + rendered.json to remote state
→ read remote evidence back
→ byte-compare exact evidence
→ verify-intent
→ verify-rendered
→ sendMessage exactly once
→ verify Telegram chat + plain text + formatting entities + message_id
→ persist exact result
```

Ни один state-push retry не повторяет `sendMessage`.

## Telegram outcome classification

Transport policies:

```text
preflight connect retries: 2
sendMessage transport retries: 0
```

- `published / verified` — exact provider result доказан;
- `pending / not_dispatched` — connect failure до provider connection;
- `pending / confirmed_absent` — явный retryable provider reject, например 429;
- `failed / confirmed_absent` — terminal 4xx;
- `unknown / may_exist` — timeout/5xx/malformed response или любое несовпадение postflight после возможной отправки.

`unknown / may_exist` никогда не retried вслепую.

## Minimal runtime и CI

Production использует:

```text
PYTHONPATH=src
requirements/telegram-publisher.txt
```

CI Python 3.11 создаёт отдельный чистый venv без Telegram token и проверяет:

- dependency graph;
- temporary ledger initialization;
- queue validation;
- presentation policy validation;
- offline rendered preview;
- отсутствие `©` в rendered text;
- дополнительный ENTER перед hashtags;
- canonical bold/italic HTML example.

Отдельные tests проверяют все 30 source cards, HTML escaping, Telegram UTF-16 entity offsets, exact postflight entities и fail-closed mismatch behavior.

Полный CI запускается на PR и на push только в `main`, чтобы не создавать двойные branch-push + PR matrices.

## Campaign rollover после 30/30

Нельзя заменить source JSON при старом ledger.

Для следующей кампании:

1. закрыть текущие 30 items verified/skipped/reconciled;
2. сохранить queue + ledger + dispatch evidence как immutable history;
3. подготовить новую reviewed queue;
4. получить новый source digest;
5. создать новый ledger explicit initialization;
6. утвердить новый digest в repository variables;
7. выполнить offline presentation preview;
8. выполнить read-only target preflight;
9. выполнить новый exact-bound canary перед schedule.

Presentation policy может переиспользоваться только если её exact digest остаётся тем же. Любая смена оформления — новая reviewed policy version.

## Источник истины

Зелёный workflow сам по себе не доказывает remote publication.

Для будущего formatted post завершение означает одновременно:

```text
exact Telegram response
+ exact formatting entities
+ durable published/verified ledger
+ durable source dispatch evidence
+ durable rendered provider evidence
```

Для первого visual rollout после presentation-v1 дополнительно требуется визуально проверить сообщение в `@lordchrist` перед включением scheduled mode.
