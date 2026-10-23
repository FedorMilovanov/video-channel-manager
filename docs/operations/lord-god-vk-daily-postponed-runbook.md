# Господь Бог — Сила Моя: ежедневные отложенные посты ВКонтакте

Статус: **provider-inert до шага 1**. Этот ранбук — самый быстрый поддерживаемый путь
заполнить стену сообщества отложенными постами примерно на два месяца. Он не создаёт
второй VK-клиент и не воскрешает исторические исполнители: единственный писатель —
`video-manager wave` с адаптером `vk.lord_god.postponed_wall` (policy
`vk-lord-god-postponed-wall-v3`).

## Точная цель

| Поле | Значение |
| --- | --- |
| `project_key` | `lord-god-strength` |
| Сообщество | `60805374` (`† Господь Бог - Сила Моя! †`) |
| `owner_id` | `-60805374` |
| Публичная ссылка | https://vk.ru/the_lord_god_is_my_strength |
| VK Видео | https://vkvideo.ru/@the_lord_god_is_my_strength |
| Credential alias | `vk-own-app-54555649` (только он; см. шаг 1) |
| Владеющий issue восстановления | #662 |

## Каденция на ~60 дней

Сборщик `scripts/build_lord_god_content_backlog_v2.py` раскладывает слоты по
московскому времени без коллизий:

| Тип поста | Когда | Источник |
| --- | --- | --- |
| Видео из VK Видео (реклама видео вложением) | каждый день, 19:00 | свежий read-only аудит стены: только `unposted`, длительность ≥ 120 с, просмотры ≤ 1500, ротация по спикерам (МакАртур, Спраул, Лоусон, Вошер, Бики, Сперджен, Коломийцев) |
| Цитаты богословов | пн/ср/пт, 12:00 | только Telegram-посты со статусом `published` + `provider_effect=verified` в durable ledger (очередь depth-v3 либо legacy verified-30) |
| Историческая статья | вт, 13:00 | только опубликованный+верифицированный исторический пост; `--historical-text-mode full` даёт полный текст (3–5 тыс. знаков, лимит стены 15 000), `excerpt` — заголовок+лид+первый абзац |

При текущих durable данных (state-ref на 2026-10-23) это даёт: 60 видео +
24 опубликованные карточки depth-v3 (Telegram-сообщения `1534`–`1581`) +
1 полная историческая статья (Сперджен, Down-Grade, Telegram `1516`). Тексты, ещё не опубликованные в Telegram,
в отбор **не попадают** (#654): они становятся eligible только после
`published+verified` записи в соответствующем ledger, и волна пересобирается.

## Шаг 1 — единственное ручное действие: своя авторизация VK (один раз)

Старый общий токен (алиасы `legendary-poet` / `default`, сторонний
`client_id=2685278`) находится в карантине (#662,
[`vk-credential-quarantine.md`](vk-credential-quarantine.md)): его нельзя
«проверить ещё раз», ротировать алиасом или обходить ожиданием. Policy v3 в коде
прямо отклоняет этот алиас до любого provider-вызова.

1. Откройте согласие собственного приложения `54555649` со scopes
   `video,wall,groups,offline` (implicit flow, redirect на `blank.html`) и
   скопируйте итоговый redirect URL целиком.
2. Импортируйте его **отдельным** алиасом, не затирая старый:

```powershell
video-manager vk login --account vk-own-app-54555649
video-manager vk token-capabilities --account vk-own-app-54555649 --sync-local
```

`token-capabilities` должен показать `video,wall,groups`. Дальше — по одному
зонду на метод, ровно как в карантинном ранбуке; упавший зонд останавливает
восстановление, второй попытки в тот же заход нет:

```powershell
video-manager vk flood-reset --account vk-own-app-54555649 --method groups.getById --confirm-code 9
video-manager vk community-probe --account vk-own-app-54555649 --community 60805374
video-manager vk flood-reset --account vk-own-app-54555649 --method wall.get --confirm-code 9
video-manager vk wall-probe --account vk-own-app-54555649 --community 60805374
```

## Шаг 2 — свежий read-only аудит стены (один проход)

```powershell
python scripts/build_vk_wall_content_audit.py `
  --account vk-own-app-54555649 `
  --community 60805374 `
  --output-dir data\handoffs
```

Нужны из пакета: `00-videos.json` и `03-wall-content-audit.json`. Исторический
аудит и старый кандидат на 83 операции (`2327edc3…`) — не авторитет свежести и
не применяются.

## Шаг 3 — выгрузить durable Telegram-свидетельства (только чтение state-ref)

`state/lordchrist-telegram` — durable state, не источник кода; файлы читаются
через `git show`, рабочее дерево не переключается:

```powershell
git fetch origin state/lordchrist-telegram
New-Item -ItemType Directory -Force operator-output\lord-god-vk\state, operator-output\lord-god-vk\runtime | Out-Null
git show origin/state/lordchrist-telegram:content/telegram/lordchrist/publication-ledger.json > operator-output\lord-god-vk\state\predecessor-ledger.json
git show origin/state/lordchrist-telegram:content/telegram/lordchrist/successor-publication-ledger.json > operator-output\lord-god-vk\state\source-v1-ledger.json
git show origin/state/lordchrist-telegram:content/telegram/lordchrist/successor-depth-v2-publication-ledger.json > operator-output\lord-god-vk\state\depth-v2-ledger.json
git show origin/state/lordchrist-telegram:content/telegram/lordchrist/successor-depth-v3-publication-ledger.json > operator-output\lord-god-vk\state\depth-v3-ledger.json
git show origin/state/lordchrist-telegram:content/telegram/lordchrist/historical-editorial/publication-ledger-spurgeon-v3-media.json > operator-output\lord-god-vk\state\historical-ledger.json
```

Материализовать очередь depth-v3 тем же кодом, что и Telegram-воркфлоу:

```powershell
python -m video_channel_manager.telegram_quote_depth resolve `
  --predecessor-queue content\telegram\lordchrist\verified-30-posts.json `
  --predecessor-ledger operator-output\lord-god-vk\state\predecessor-ledger.json `
  --candidate content\telegram\lordchrist\successor-quotes-v1.json `
  --translation-ledger content\telegram\lordchrist\successor-translation-ledger-v1.json `
  --integrity-amendments content\telegram\lordchrist\successor-integrity-amendments-v1.json `
  --source-v1-runtime-queue operator-output\lord-god-vk\runtime\source-v1-queue.json `
  --source-v1-ledger operator-output\lord-god-vk\state\source-v1-ledger.json `
  --depth-v2-runtime-queue operator-output\lord-god-vk\runtime\depth-v2-queue.json `
  --depth-v2-ledger operator-output\lord-god-vk\state\depth-v2-ledger.json `
  --runtime-queue operator-output\lord-god-vk\runtime\depth-v3-queue.json `
  --depth-ledger operator-output\lord-god-vk\state\depth-v3-ledger.json `
  --output operator-output\lord-god-vk\runtime\selection.json
```

## Шаг 4 — собрать очередь на 60 дней и provider-inert handoff

`--start-date` — ближайший понедельник после аудита; все даты обязаны оставаться
в будущем на момент apply.

```powershell
python scripts/build_lord_god_content_backlog_v2.py data\handoffs\<audit-dir>\03-wall-content-audit.json `
  --repository-root . `
  --historical-release content\telegram\lordchrist\historical-editorial\v1\production-release-spurgeon-v3-media-canary.json `
  --historical-ledger operator-output\lord-god-vk\state\historical-ledger.json `
  --quote-queue operator-output\lord-god-vk\runtime\depth-v3-queue.json `
  --quote-ledger operator-output\lord-god-vk\state\depth-v3-ledger.json `
  --start-date <YYYY-MM-DD> --days 60 --video-count 60 --quote-count 24 --telegram-count 1 `
  --historical-text-mode full `
  --output operator-output\lord-god-vk\backlog.json

python scripts/prepare_lord_god_content_wave.py `
  --repository-root . `
  --backlog operator-output\lord-god-vk\backlog.json `
  --videos data\handoffs\<audit-dir>\00-videos.json `
  --quote-queue operator-output\lord-god-vk\runtime\depth-v3-queue.json `
  --quote-ledger operator-output\lord-god-vk\state\depth-v3-ledger.json `
  --historical-release content\telegram\lordchrist\historical-editorial\v1\production-release-spurgeon-v3-media-canary.json `
  --historical-ledger operator-output\lord-god-vk\state\historical-ledger.json `
  --output-dir operator-output\lord-god-vk\handoff-review

video-manager wave preview operator-output\lord-god-vk\handoff-review\07-plan.json
```

Проверить в preview: проект `lord-god-strength`, сообщество `60805374`,
число операций и digest плана. Затем пересобрать тот же handoff в новый каталог
с `--enable-provider-writes` (только флаг intent; provider-вызовов prepare не
делает) и убедиться, что digest плана не изменился.

## Шаг 5 — один apply, без повторов

```powershell
video-manager wave apply `
  --source operator-output\lord-god-vk\handoff-apply\06-source.json `
  --plan operator-output\lord-god-vk\handoff-apply\07-plan.json `
  --intent operator-output\lord-god-vk\handoff-apply\08-apply-intent.json `
  --repository-root . `
  --journal-directory operator-output\lord-god-vk\journal-001 `
  --vk-account vk-own-app-54555649 `
  --enable-provider-writes
```

Правила остановки: один писатель на сообщество; `unknown` исход не повторяется —
только `video-manager wave reconcile` по точному плану/результату; код 9 по
любому методу останавливает волну, TTL не предполагается.

## Приём новых постов от оператора

Посты, присланные текстом в чат, не вставляются в уже собранный план. Порядок:
текст сверяется с первоисточником и дубликатами, публикуется/фиксируется в
Telegram либо оформляется отдельным reviewed text-слотом в backlog JSON
(`kind: telegram_quote|telegram_editorial` с точным `publication_id`, текстом и
`source_url`), после чего шаги 4–5 повторяются с новой датой старта для ещё не
запланированного хвоста. Уже запланированные слоты не переиспользуются.
