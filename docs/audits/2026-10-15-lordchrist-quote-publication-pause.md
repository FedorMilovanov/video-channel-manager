# Почему не публикуются цитаты @lordchrist — аудит 15 октября 2026

## Вывод

**Причина остановки подтверждена: автопубликацию намеренно выключили 3 октября, а подготовленную повторную активацию не слили в `main`.** Очередь не потеряна. Текущие зелёные запуски Actions не означают, что сообщения отправлялись: при выключенном расписании выполняются только разрешение очереди, валидация и preview.

Дополнительно выявлено: **PR #690 обеспечивает вход в canary №16, но не непрерывную публикацию оставшихся 45 карточек.** Его runtime-проверка требует строго 15 опубликованных / 45 pristine pending. После успешного №16 следующий запуск будет остановлен до отправки. Это соответствует защитной остановке canary, но не является завершённым восстановлением автономной работы.

Публикации, изменение Telegram, слияние PR, изменение расписания и запись в durable state в ходе аудита **не выполнялись**.

## Границы и идентичность

- Репозиторий: `FedorMilovanov/video-channel-manager`.
- Проект: `lord-god-strength`, канал **@lordchrist**, а не Telegram-группа обсуждений.
- Exact target: chat `-1001295216957`, bot `8716602202` / `preaching_mp3_bot`.
- Проверенный current `main`: `6765ed0cc6f9f3e40c2dea2a4905212bbe359c70`.
- Проверенный state-only ref: `state/lordchrist-telegram` @ `65d60e7e11dbe207f745a12f750aab789a430d57`.
- Рабочая ветка этого аудита: `arena/13447cc8-video-channel-manager`; другие ветки не переключались и не изменялись.
- Owning context: issues #667 / #678, pause PR #684, pending activation PR #690.
- Транспорт: GitHub `official_api_read` и локальный `local_only`. Попытка запустить read-only workflow была отклонена до запуска, HTTP 403.
- Гипотеза: отсутствие сообщений вызвано незавершённой повторной активацией, а не исчерпанием очереди. Минимальные проверки: конфигурация current main, remote state, actual Actions steps, exact-state offline preflight.
- Stop condition: никаких Telegram/provider mutations; ограничение доступа не обходить, старые отправки не повторять.

## 1. Хронология

| Дата | Подтверждённое событие |
| --- | --- |
| 2 октября | [#668](https://github.com/FedorMilovanov/video-channel-manager/pull/668): принят корпус depth-v2; [#683](https://github.com/FedorMilovanov/video-channel-manager/pull/683): активирован переход после 14 опубликованных старых карточек. |
| 3 октября, 11:37:11 UTC / 14:37:11 МСК | Опубликован №15 `lordchrist-successor-depth-v2-15-owen-mortify-by-spirit`, [сообщение 1558](https://t.me/lordchrist/1558), [run 37120208117](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/37120208117). Журнал: `published` / `verified`. |
| 3 октября, 19:52 UTC | Слит [#684](https://github.com/FedorMilovanov/video-channel-manager/pull/684): `production-schedule.json.enabled=false`, пауза для оформления, самостоятельности цитат и обновления проверки источников. |
| 3–4 октября | Слиты hardening/preflight PR #685, #687, #688, #689. Формат quote-v4 и доказательства подготовлены, но публикация этим не включена. |
| 4 октября | Успешные read-only preflight на current main и на PR #690. Последний подготовлен, CI зелёный, но PR остаётся **OPEN / merged=false**. |
| 4–15 октября | В полученной истории publisher — **22 запуска, все success**. State ref остаётся на результате от 3 октября. |

Это не «несколько недель без попыток cron»: задания продолжают запускаться, но публикационная ветвь выключена.

## 2. Точные действующие блокировки

### Основная: выключено расписание

`content/telegram/lordchrist/production-schedule.json`:

- `enabled=false`;
- `presentation_policy_id=lordchrist-quote-v3`;
- activation note прямо описывает временную паузу после №15.

`decide_scheduled_slot()` на текущей конфигурации возвращает `active=false`, `reason="production schedule disabled"` для обоих quote cron. В `.github/workflows/lordchrist-telegram-poster.yml` это превращается в `do_publish=false`, `do_preflight=false`: затем выполняется preview, а публикационные шаги пропускаются.

В [run 38727145942 от 15 октября](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/38727145942) через jobs API подтверждено:

- resolve active quote release, validate immutable queue, preview — `success`;
- current-main CI proof, live bot/channel preflight, prepare dispatch, persist intent, send, capture outcome, persist result — `skipped`.

Поэтому зелёный Actions здесь доказывает успешный preview, **не отправку**. Полные run logs в окружении недоступны из-за сетевого ограничения хоста хранения логов; вывод основан на jobs/steps API и исходном workflow, а не на предположении о содержимом логов.

### Дополнительная: v4 не активирован и не выбран publisher-ом

`successor-depth-runtime-activation-v4.json` содержит `provider_writes_authorized=false`. Current publisher использует `presentation-policy-v3.json`; наличие v4-файлов само по себе ничего не переключает.

[#690](https://github.com/FedorMilovanov/video-channel-manager/pull/690), head `e0bca5121b49cdb9da1b14c98a92c3cd138b7a05`, подготавливает связанное включение:

1. `enabled=true`;
2. `provider_writes_authorized=true` в rolling v4 activation;
3. выбор v4 в publisher;
4. обязательный runtime checkpoint и согласованность policy/arming до провайдерных шагов;
5. read-only preflight, совместимый с активированным checkpoint.

На момент проверки PR mergeable / CLEAN, 10 checks success на head. Это исторические CI/проверки от 4 октября, а не свежая проверка текущих Telegram-прав и не разрешение на новую запись.

**Просто поменять `enabled` на true в main нельзя:** будет возобновлён старый путь v3 без полного перехода к reviewed v4. Использовать ручной publish для обхода паузы также не следует.

## 3. Очередь, история и защита от повторов

Данные прочитаны из точного state commit; экспортированные ledger bytes сверены с `git show` и после проверок остались неизменными.

| Журнал | Подтверждённое состояние |
| --- | --- |
| Исходные verified-30 | 30 `published/verified` — завершены. |
| Старый successor-v1 | 14 `published/verified`, 46 `pending/impossible`. Это сохранённый источник перехода, не вторая активная очередь для параллельной отправки. |
| Активный successor-depth-v2 | **15 `published/verified`, 45 `pending/impossible`**, всего 60. Первые 14 — перенесённая история, новая depth-v2 публикация — №15. |
| Historical v2 ledger | 1 published / 8 pending. Отдельная линия, не остаток quote-корпуса. |
| Historical v3 media canary | 1 published / verified. |
| Rich live canary | 1 published / verified. |

Quote queue digest: `sha256:c2ad28bb96e88a9e0633c4b7a55d6033bbf29c5a557e1aa4478cc2e0359e3441`.

Все 45 будущих depth-v2 карточек проходят exact pending-suffix checkpoint: совпадают payload hashes, нет intent, attempt, message identity или незавершённой отправки. Не требуется переинициализация ledger.

Channel-wide effect guard для predecessor/research/successor/depth-v2 возвращает `clear=true`. В августовской research-v2 **действительно сохранён** старый `unknown/may_exist`, но его точная identity закрыта отдельным проверенным disposition `retired_no_replay` по #286. Это не текущая блокировка и **не разрешение повторить старую отправку**. Historical/rich ledgers также просмотрены отдельно; дополнительных dispatching/may_exist там не обнаружено.

## 4. Следующий пост и редакционная готовность

- №16: `lordchrist-successor-depth-v2-16-spurgeon-sovereignty-comfort`.
- Заголовок: «Суверенитет как утешение».
- Автор: Чарльз Сперджен, проповедь «Божественный суверенитет», 1856.
- Политика: `lordchrist-quote-v4`, digest `sha256:a87dd04d605a749c84ecd47d18c127dd921dddea500781c0fd75a0db20a7be9f`.
- Локальный render proof: **437 символов**, entities `bold / blockquote / italic`, attribution отдельной строкой непосредственно под цитатой.
- Exact provider payload: `sha256:40db4515dcb26173fcd83650a0baeb291d71adc49f802c789f98d2dddc8c6977`.

Пройдены отдельно: queue/ledger validation, runtime activation checkpoint, standalone review всех 45 pending-карточек, quality-v4, content-findings validation, v4 render proof. Перезапущены **113 тестов — 113 passed**, с точным hash-pinned runtime из `requirements/telegram-publisher.txt`. Это целевой набор, не заявление о полном прогоне всего репозитория.

Доказательства источников: reviewed web audit содержит 99 страниц; статический сохранённый live-probe — 92 retrieved, 5 relocated, 2 bot-protection. Эти цифры дополнительно подтверждены annotations успешных preflight от **4 октября**. Это не 99 вновь открытых страниц 15 октября: новый независимый live source audit в этой среде не выполнялся.

Есть **один открытый редакционный дефект №44** (`translation_grammar`): перевод «Покаяние не более заслуживающее спасение дело…». Исправление уже предложено в `quote-pending-content-findings-v1.json`, но намеренно не применено из-за sealed payload/ledger bindings. Это не причина остановки №16. До разрешения всей оставшейся очереди нужно согласовать исправление/новую release identity и rebind только ещё не опубликованного suffix; незаметно редактировать запечатанную карточку нельзя.

## 5. Почему #690 не решает постоянную работу полностью

PR добавляет вызов `validate_runtime_checkpoint()` при **каждом** запуске publisher. В текущем коде:

- `required_published_prefix=15`, `required_pending_suffix=45`;
- карточки 16–60 должны быть pristine pending;
- `validate_migration()` тоже требует pending 16–60, migration boundary фиксирован на 15.

Локально проверены два случая без вызовов Telegram:

1. Точные байты activation из PR #690 + текущий state: offline `--require-provider-writes` проходит.
2. **Синтетическая временная копия**, моделирующая опубликованный №16: следующий runtime checkpoint отклоняется с `runtime checkpoint requires pristine pending suffix: lordchrist-successor-depth-v2-16-spurgeon-sovereignty-comfort`.

Синтетическая копия не является доказательством реальной отправки; была удалена после проверки, authoritative state не менялся. Эта проверка подтверждает границу canary. Для дальнейшего постоянного выполнения нужно отделить immutable migration boundary от проверки допустимого монотонно растущего verified prefix, сохранив exact payloads, порядок, pristine remaining suffix, target/CI/slot gates и no-blind-retry. Простого продвижения числа prefix в JSON недостаточно: migration пока жёстко привязан к 15.

## 6. Что остаётся неизвестным

- На 4 октября live preflight подтвердил exact channel, bot, `administrator`, `can_post_messages=True`: [main run 37235958110](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/37235958110), [PR run 37237072978](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/37237072978). Annotations доступны через GitHub API.
- **Свежие Telegram-права/валидность токена на 15 октября не подтверждены.** Dispatch исключительно read-only preflight на current main отклонён GitHub API: HTTP 403 `Resource not accessible by integration`. Workflow не был создан этим запросом.
- Чтение repository Actions variables также отклонено HTTP 403; их текущие значения не выдумывались. Secrets не извлекались.
- Прямой Telegram API и внешние source hosts в sandbox недоступны. Независимое чтение реальной истории канала не выполнено; последнее сообщение указано по provider-verified durable receipt, не по свежему просмотру Telegram.

Отказ доступа не объясняет историческую паузу: она уже закодирована в main и видна в выполняющихся schedule jobs. Это ограничение **свежей проверки/восстановления из данной сессии**, не доказательство поломки бота.

## 7. Безопасный порядок восстановления

1. Отдельно подтвердить возобновление публикаций именно в **@lordchrist**. Audit request не использован как разрешение отправить сообщения или слить активацию.
2. Получить рабочий доступ к запуску read-only preflight; проверить fresh current main/state, exact bot/channel и posting permissions. Не менять токен без подтверждённой причины.
3. Перепроверить точный head #690 и current state, CI/reviews перед возможным слиянием. Не применять исторические зелёные checks как свежую provider-authority.
4. После отдельной авторизации выполнить ограниченный canary №16; подтвердить message URL, точный текст/entities, durable результат **16/44**, отсутствие дубля. При неоднозначном результате — reconciliation, не повторная отправка.
5. До №17 завершить отдельное reviewed решение для постоянного выполнения после canary. Не отключать checkpoint wholesale; не менять историю №1–15; учесть открытый дефект №44 перед разрешением всего suffix.
6. Утренний слот: ежедневно 09:17 МСК, lease до 21:17. Вечерний: вт/пт/вс 21:17 МСК, максимум 160 минут, без перехода на следующий московский день. Это отдельный слот, не обещание догнать любой пропуск. **Не публиковать накопившееся за пропущенные дни**, `backfill_policy=none`, не rerun-ить старые scheduled sends.
7. После rollout контролировать не только общий зелёный run, но и фактические send/result steps, state progress и message URL. Для операционной видимости полезен отдельный summary «PAUSED / PREVIEW ONLY», чтобы зелёный preview больше не воспринимался как публикация.

## Локальные артефакты

Основной пользовательский отчёт: `operator-output/lordchrist-publication-audit-2026-10-15.md` — копия этого документа.

- Machine evidence: `operator-output/lordchrist-publication-audit-2026-10-15.json`.
  SHA-256: `e98698a6c7192a5dcc4f1880e1af8929fa391296bb6cc3376d1c74e82ab254e2`.
- Render proof: `operator-output/lordchrist-quote-v4-render-proof-audit.json`.
  SHA-256: `7bf33501d43ffe74f794b7769737318bb74c0b3fb3798fbfbc1b58daff830972`.
- Exact next preview: `operator-output/lordchrist-next-quote-preview.json`.
- Timeline runs: `operator-output/lordchrist-publisher-runs-after-pause.json`.

`operator-output` остаётся ignored; в Git добавлен только этот документ аудита. Исполняемый production-код, расписание, content payloads, remote refs и provider state не изменялись. Этот отчёт фиксирует состояние на дату проверки, **не является разрешением на публикацию**.
