# GitHub-публикатор цитат для @lordchrist

Дата актуализации: 2026-08-06  
Проект: `lord-god-strength`  
Канал: `@lordchrist`  
Owning issue: `#141`

## Состав

- `content/telegram/lordchrist/verified-30-posts.json` — утверждённая очередь из 30 публикаций;
- `content/telegram/lordchrist/verified-30-posts.md` — версия очереди для проверки человеком;
- `src/video_channel_manager/telegram_publisher.py` — логика проверки, подготовки и отправки;
- `src/video_channel_manager/telegram_cli.py` — пакетный CLI;
- `.github/workflows/lordchrist-telegram-poster.yml` — GitHub Actions workflow;
- `state/lordchrist-telegram` — отдельная ветка с журналом публикаций.

Домашний компьютер и локальный `telegram-bot-api.exe` для текстовых публикаций не требуются.

## Настройка GitHub

Во вкладке **Secrets** требуется:

```text
LORDCHRIST_TELEGRAM_BOT_TOKEN
```

Во вкладке **Variables** требуются:

```text
LORDCHRIST_TELEGRAM_CHAT_ID
LORDCHRIST_TELEGRAM_BOT_USERNAME
LORDCHRIST_APPROVED_QUEUE_DIGEST
LORDCHRIST_POSTING_ENABLED
LORDCHRIST_SCHEDULE_ENABLED
```

`LORDCHRIST_TELEGRAM_BOT_USERNAME` указывается без `@`. `LORDCHRIST_TELEGRAM_CHAT_ID` — точный отрицательный ID канала вида `-100...`.

Можно использовать существующего Telegram-бота, включая `@preaching_mp3_bot`, если он добавлен администратором канала и имеет право публиковать сообщения. Локальная MP3-программа при этом не запускается: GitHub Actions использует только облачный Telegram Bot API.

## Безопасное включение

Начальное состояние:

```text
LORDCHRIST_POSTING_ENABLED=false
LORDCHRIST_SCHEDULE_ENABLED=false
```

### 1. Проверка без отправки

Открыть:

**Actions → Lordchrist Telegram quote publisher → Run workflow**

Выбрать:

```text
action: preview
confirm: оставить пустым
```

`preview` проверяет очередь и state-ветку, показывает следующий пост и не обращается к Telegram.

### 2. Один ручной тестовый пост

Установить:

```text
LORDCHRIST_POSTING_ENABLED=true
LORDCHRIST_SCHEDULE_ENABLED=false
```

Затем запустить workflow с параметрами:

```text
action: publish
confirm: PUBLISH_NEXT_LORDCHRIST_POST
```

Перед отправкой workflow проверяет:

1. digest очереди;
2. username бота;
3. точный числовой ID канала;
4. статус администратора;
5. право `can_post_messages`;
6. отсутствие уже опубликованного поста в эту московскую дату.

Отправляется не более одного следующего поста. Успех фиксируется только после проверки возвращённых Telegram `chat.id`, полного текста и положительного `message_id`.

### 3. Включение расписания

Только после успешного ручного теста установить:

```text
LORDCHRIST_SCHEDULE_ENABLED=true
```

Запланированы две возможности запуска:

```text
09:17 Europe/Moscow
21:17 Europe/Moscow
```

Вечерний запуск является страховочным. После подтверждённой публикации в этот день второй пост не отправляется.

## Защита от повторов

До вызова `sendMessage` workflow сохраняет намерение в ветке `state/lordchrist-telegram`. После ответа Telegram туда же записывается точный результат.

При сетевом обрыве после начала отправки состояние становится `unknown / may_exist`. Слепой повтор блокируется до ручной сверки канала.

Для ручного разрешения используется пакетный CLI:

```text
python -m video_channel_manager.telegram_cli ... resolve
```

Допустимые решения:

- `confirmed_published` — сообщение найдено;
- `confirmed_absent` — подтверждено, что сообщения нет;
- `skip` — публикация сознательно пропущена.

## Критерий подтверждённой публикации

Публикация завершена только когда state-ветка содержит:

```text
state = published
provider_effect = verified
message_id > 0
actual_chat_id = ожидаемый LORDCHRIST_TELEGRAM_CHAT_ID
payload_sha256 = digest утверждённого поста
```

Зелёный workflow или HTTP 200 сами по себе не считаются достаточным доказательством публикации.
