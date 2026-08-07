# GitHub-публикатор цитат для @lordchrist

Дата hardening: 2026-08-07  
Проект: `lord-god-strength`  
Канал: `@lordchrist`  
Owning hardening issue: `#155`

## Статус безопасности

Этот publisher должен оставаться **без live-записей в Telegram** до отдельного явно подтверждённого canary после merge hardening-PR.

До canary рекомендуется держать:

```text
LORDCHRIST_POSTING_ENABLED=false
LORDCHRIST_SCHEDULE_ENABLED=false
```

`preview` и live read-only `preflight` не должны требовать включения posting gate. `sendMessage` разрешается только отдельным manual `publish` или последующим scheduled run после подтверждённого manual canary.

## Архитектура

- `content/telegram/lordchrist/verified-30-posts.json` — immutable очередь из 30 публикаций;
- `src/video_channel_manager/telegram_models.py` — queue/state/dispatch schemas;
- `src/video_channel_manager/telegram_state.py` — fail-closed ledger и deterministic state transitions;
- `src/video_channel_manager/telegram_transport.py` — единственный Telegram Bot API transport;
- `src/video_channel_manager/telegram_publisher.py` — узкий публичный facade;
- `src/video_channel_manager/telegram_cli.py` — package-owned CLI;
- `.github/workflows/lordchrist-telegram-poster.yml` — production workflow;
- `state/lordchrist-telegram` — отдельная durable state-ветка;
- `requirements/telegram-publisher.txt` — минимальный exact-version runtime.

Домашний компьютер для текстовых публикаций не требуется.

## Production bot

Для production-публикатора предпочтителен **отдельный cloud-only Telegram bot**, не используемый домашним MP3-процессом или локальным Bot API server.

Причины:

- отдельный blast radius токена;
- отсутствие shared Local/Cloud Bot API lifecycle;
- независимые rate limits и operational ownership;
- publisher получает только минимально необходимое право публикации.

Если существующий bot временно используется для canary, identity всё равно должна быть привязана одновременно к exact numeric `bot_id` и username. До live canary следует отдельно решить, остаётся ли он production publisher или создаётся выделенный bot.

## GitHub configuration

### Secret

```text
LORDCHRIST_TELEGRAM_BOT_TOKEN
```

BotFather token не должен находиться в workflow-level `env`. Workflow передаёт его только двум provider-facing шагам: read-only preflight и exact send.

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

`LORDCHRIST_TELEGRAM_CHAT_ID` — exact numeric ID целевого канала. Код не считает строковый префикс `-100` доказательством типа объекта: фактический `getChat.type` обязан быть `channel`.

`LORDCHRIST_TELEGRAM_BOT_ID` — exact positive numeric ID того же bot, который возвращает `getMe`.

## Три режима workflow

### 1. `preview` — полностью offline

```text
action: preview
publication_id: пусто
confirm: пусто
```

Проверяются immutable queue и exact durable ledger, после чего показывается strict next post.

Telegram calls: `0`.

### 2. `preflight` — live, но строго read-only

```text
action: preflight
publication_id: пусто
confirm: пусто
```

Этот режим должен работать при:

```text
LORDCHRIST_POSTING_ENABLED=false
LORDCHRIST_SCHEDULE_ENABLED=false
```

Последовательность proof:

1. `getMe`;
2. exact `bot_id`;
3. exact bot username;
4. `is_bot=true`;
5. `getChat(exact numeric chat_id)`;
6. exact channel username `lordchrist`;
7. `type=channel`;
8. `getChat(@lordchrist)` обязан разрешиться в тот же numeric ID;
9. `getChatAdministrators(exact_chat_id, return_bots=true)`;
10. exact bot ID обязан присутствовать среди administrators;
11. `status=administrator|creator`;
12. `can_post_messages=true` для administrator.

Production preflight **не использует `getChatMember`**, чтобы не возвращаться к уже наблюдавшемуся инциденту `Bad Request: member list is inaccessible`.

`sendMessage` в этом режиме недостижим.

### 3. `publish` — один exact-bound manual canary/post

Сначала выполнить `preview` и взять показанный exact `publication_id`.

Пример:

```text
action: publish
publication_id: lordchrist-bunyan-cross-burden
confirm: PUBLISH:lordchrist-bunyan-cross-burden
```

Workflow дополнительно требует:

```text
LORDCHRIST_POSTING_ENABLED=true
```

Manual confirmation привязано к immutable `publication_id`. Если strict next item изменился, stale/re-run workflow не может молча перейти к следующей публикации: выполнение останавливается на `manual publication_id mismatch`.

## Глобальное ограничение на сутки

Независимо от режима:

```text
manual OR scheduled
+
already verified publication on current Europe/Moscow date
=
NO DISPATCH
```

Таким образом повторный manual click после успешного поста не может отправить №2 в тот же московский календарный день.

## Scheduled mode

После отдельного успешного manual canary можно установить:

```text
LORDCHRIST_SCHEDULE_ENABLED=true
```

Окна:

```text
09:17 Europe/Moscow
21:17 Europe/Moscow
```

Второе окно — catch-up. Daily guard не позволяет ему создать второй verified post за тот же день.

Scheduled execution дополнительно требует хотя бы один verified manual publication с **тем же exact bot ID и exact chat ID**.

Concurrency настроена как:

```text
queue: single
cancel-in-progress: false
```

Текущая потенциально выполняющаяся отправка никогда не отменяется ради более нового run, но после outage не накапливается длинная FIFO-очередь старых publisher runs.

## Fail-closed ledger

Production больше никогда не создаёт отсутствующий state автоматически.

`load_ledger()` останавливает workflow, если:

- ledger file отсутствует;
- JSON/schema невалидны;
- queue digest отличается;
- отсутствует хотя бы один из 30 `publication_id`;
- присутствует extra ID;
- payload SHA записи не совпадает с immutable queue.

Это устраняет опасный сценарий, когда потерянный/частичный state мог бы восстановить уже опубликованную запись как `pending`.

### Explicit initialization

Только для **новой кампании**, до её первого provider call, существует отдельная административная команда:

```text
python -m video_channel_manager.telegram_cli \
  --queue PATH_TO_NEW_QUEUE \
  --ledger PATH_TO_NEW_LEDGER \
  initialize-ledger \
  --confirm INITIALIZE_NEW_LORDCHRIST_LEDGER
```

Она отказывается перезаписывать существующий ledger.

**Текущий `state/lordchrist-telegram` уже существует и не должен переинициализироваться.**

## Durable intent before provider mutation

Для `publish` порядок фиксирован:

```text
strict queue validation
→ live target preflight
→ global Moscow daily guard
→ exact manual publication_id guard / scheduled canary guard
→ create dispatch envelope
→ save dispatching/may_exist intent locally
→ commit intent to state branch
→ verify exact intent commit on remote
→ verify exact persisted intent payload
→ only then sendMessage
```

Dispatch intent сохраняет:

- `intent_id`;
- `publication_id`;
- payload SHA;
- `GITHUB_RUN_ID`;
- `GITHUB_RUN_ATTEMPT`;
- code `GITHUB_SHA`;
- workflow SHA;
- exact bot ID/username;
- exact chat ID/username;
- dispatch mode.

## State push reconciliation

GitHub API/transport ошибки state push и Telegram ambiguity — разные классы событий.

State commit можно безопасно повторно push'ить, поэтому workflow:

1. делает bounded push retry;
2. после ошибочного push response проверяет `ls-remote`;
3. если exact local SHA уже оказался remote — продолжает;
4. если remote branch неожиданно ушла от ожидаемого parent — fail closed и не force-push'ит.

Это применяется и к intent commit, и к result commit.

Ни один такой retry не является повтором `sendMessage`.

## Telegram outcome classification

### `published / verified`

Только когда Telegram вернул одновременно:

- exact `chat.id`;
- exact channel username;
- `chat.type=channel`;
- exact immutable text;
- positive `message_id`.

Ledger сохраняет также:

```text
https://t.me/lordchrist/<message_id>
```

### `pending / not_dispatched`

Connect failure до установления provider connection может быть доказан как отсутствие dispatch effect. Следующий guarded run может повторить эту же публикацию.

### `pending / confirmed_absent`

Явный Telegram `429` означает, что запрос отвергнут и post не создан. Это безопасно для будущего bounded retry той же публикации.

### `failed / confirmed_absent`

Явный terminal 4xx, например invalid request/permissions, блокирует strict queue до исправления причины и reconciliation.

### `unknown / may_exist`

Любой исход, при котором `sendMessage` мог быть принят, но exact response потерян или не доказан:

- read/write timeout после начала mutation;
- remote protocol ambiguity;
- HTTP/Telegram 5xx после mutation request;
- malformed/non-JSON response после mutation;
- returned message identity mismatch.

В этом состоянии **blind retry запрещён**.

## Manual reconciliation

CLI допускает:

```text
confirmed_published
confirmed_absent
skip
```

`confirmed_published` требует concrete evidence note, exact negative chat ID и positive `message_id`; durable dispatch bot identity должна уже присутствовать в ledger.

`confirmed_absent` — единственный reconciliation, который возвращает unresolved publication в `pending`.

## State branch protection

Для `state/lordchrist-telegram` рекомендуется включить GitHub ruleset:

- block branch deletion;
- block force pushes;
- разрешить workflow fast-forward writes;
- не требовать обычный PR для каждого machine-state commit, иначе publisher не сможет durable-persist intent/result.

Это defense-in-depth поверх exact parent/SHA проверки workflow.

## Minimal runtime

Production workflow не устанавливает весь `video-channel-manager` со всеми VK/YouTube/SQL dependencies.

Он использует:

```text
PYTHONPATH=src
requirements/telegram-publisher.txt
```

с exact package versions и `--only-binary=:all:`.

Full repository CI по-прежнему устанавливает весь проект и выполняет dependency audit, Ruff, formatting, mypy, pytest и PowerShell matrices.

## CI pressure hardening

Полный CI должен запускаться:

- на `pull_request` для рабочих веток;
- на `push` только для `main`.

Это устраняет двойные полные matrices `branch push + pull_request synchronize`, которые раньше могли создавать десятки лишних hosted-runner jobs.

Рабочая hardening-ветка может делать несколько repository commits без CI; один полный CI начинается после открытия PR. Последующий push в открытый PR отменяет superseded CI через существующий `cancel-in-progress: true`.

## Campaign rollover после 30/30

Нельзя просто заменить JSON новой месячной очередью при старом ledger.

Правильный rollover:

1. доказать текущие `30/30` или явно reconciled final state;
2. сохранить старую queue + ledger как immutable campaign evidence;
3. создать новую reviewed 30-post queue;
4. получить новый queue digest;
5. создать **новый** ledger explicit initialization;
6. отдельно утвердить новый digest в repository variables;
7. выполнить read-only preflight;
8. новый campaign снова проходит manual canary перед scheduled execution.

Отсутствие automatic rollover — сознательная safety boundary.

## Перед первым live canary после hardening

Обязательная последовательность:

1. hardening PR merged после полного green CI;
2. подтвердить, что state ledger всё ещё `30 pending`, provider effect не возникал во время hardening;
3. решить production bot ownership; предпочтительно dedicated cloud-only bot;
4. добавить/проверить exact `LORDCHRIST_TELEGRAM_BOT_ID`;
5. `LORDCHRIST_POSTING_ENABLED=false`;
6. `LORDCHRIST_SCHEDULE_ENABLED=false`;
7. выполнить `preview`;
8. выполнить live read-only `preflight`;
9. сверить exact bot/channel proof;
10. только после отдельного человеческого решения временно включить posting gate;
11. запустить один exact-bound manual canary;
12. проверить Telegram визуально и сверить state branch `published/verified/message_id/message_url`;
13. только затем принимать отдельное решение о scheduled mode.

Зелёный workflow сам по себе не является доказательством публикации. Источник истины — exact Telegram response + durable verified ledger + при canary визуальная сверка публичного сообщения.
