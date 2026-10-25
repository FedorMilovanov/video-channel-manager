# Господь Бог — Сила Моя: ежедневные отложенные посты ВКонтакте

Статус: **GitHub Actions, ручной двухэтапный запуск**. Поддерживаемый путь —
workflow [`.github/workflows/lord-god-vk-postponed-wave.yml`](../../.github/workflows/lord-god-vk-postponed-wave.yml):
сначала `action=prepare`, затем отдельным запуском `action=apply`. Единственный
писатель в VK — `video-manager wave` с адаптером `vk.lord_god.postponed_wall`
(policy `vk-lord-god-postponed-wall-v4`). Расписания (`schedule`) у workflow нет:
один успешный apply передаёт VK всю отложенную волну, дальше посты публикует сам VK.

## Точная цель

| Поле | Значение |
| --- | --- |
| `project_key` | `lord-god-strength` |
| Сообщество | `60805374` (`† Господь Бог - Сила Моя! †`) |
| `owner_id` | `-60805374` |
| Публичная ссылка | https://vk.ru/the_lord_god_is_my_strength |
| VK Видео | https://vkvideo.ru/@the_lord_god_is_my_strength |
| Credential alias | `vk-lord-god-community-key` (только он) |
| GitHub Environment | `The_Lord_God_VK` |
| Environment secret | `LORD_SECRET` (ключ доступа сообщества с правом `wall`) |
| Владеющий issue восстановления | #662 |

## Каденция на ~60 дней

Сборщик `scripts/build_lord_god_content_backlog_v2.py` раскладывает слоты по
московскому времени без коллизий:

| Тип поста | Когда | Источник |
| --- | --- | --- |
| Видео из VK Видео (реклама видео вложением) | каждый день, 19:00 | свежий read-only аудит стены: только `unposted`, длительность ≥ 120 с, просмотры ≤ 1500, ротация по спикерам (МакАртур, Спраул, Лоусон, Вошер, Бики, Сперджен, Коломийцев) |
| Цитаты богословов | пн/ср/пт, 12:00 | только Telegram-посты со статусом `published` + `provider_effect=verified` в durable ledger очереди depth-v3 |
| Историческая статья | вт, 13:00 | только опубликованный+верифицированный исторический пост; `--historical-text-mode full` даёт полный текст (лимит стены 15 000) |

При durable данных state-ref на 2026-10-23 расчётная волна: до 60 видео,
24 опубликованные карточки depth-v3 (Telegram-сообщения `1534`–`1581`) и
1 полная историческая статья (Сперджен, Down-Grade, Telegram `1516`). Фактическое
число операций всегда берётся из свежего аудита и summary конкретного prepare:
если подходящих видео меньше, план будет меньше. Тексты, ещё не опубликованные
в Telegram, в отбор **не попадают** (#654): они становятся eligible только после
`published+verified` записи в ledger, и волна пересобирается.

**Полоса `text-only` (текущий режим ключа сообщества).** Ключ сообщества не
может читать `wall.get`/`video.get` (VK error 27 для group auth), поэтому
prepare с `lane=text-only` не строит аудит и не включает видео-слоты: волна
состоит из цитат (пн/ср/пт 12:00) и исторической статьи (вт 13:00) — до
25 операций. Дедупликация вместо снапшотов стены опирается на журнал волны и
Telegram-ledger'ы; поэтому перед apply оператор обязан открыть в VK вкладку
«Отложенные» сообщества и убедиться, что там нет уже запланированных копий
этих текстов (кроме ожидаемых). Видео-слоты вернутся только с пользовательским
read-путём (`lane=full`).

**Полоса `charnock` (текстовая серия).** Prepare с `lane=charnock` берёт
13 готовых статей цикла Стивена Чарнока «О бытии Бога»
(`content/telegram/lordchrist/telegraph-v1/charnock/`), режет каждую по
разделам на посты ≤ 15 000 знаков (`build_lord_god_charnock_vk_posts.py`) и
раскладывает части по будням в 13:00 МСК (`prepare_lord_god_article_wave.py`).
Обложки статей привязаны только как evidence: загрузить фото на стену
ключом сообщества нельзя — живой apply `40197033579` доказал, что
`photos.getWallUploadServer` недоступен с group auth (VK error 27), поэтому
серия идёт текстом, как и полоса `text-only`. Apply — тот же, с точным
digest-подтверждением и журналом волны.

**Частичный apply и resume.** Если apply встал на ошибке VK 214 («на это
время уже запланирован пост»), часть операций уже в отложке. Повторять тот
же план нельзя: готовьте resume-prepare с `skip_posts` = числу `succeeded`
в журнале apply и `occupied_dates` — датами (через запятую), чьи слоты
13:00 уже заняты на стене (ключ сообщества стену не читает, занятость
объявляет оператор). Пример из жизни: слот вт 27.10.2026 13:00 занимает
статья Сперджена из первой волны.

## Одноразовая настройка

### 1. Ключ доступа сообщества «Господь Бог»

Старый общий токен (алиасы `legendary-poet` / `default`, сторонний
`client_id=2685278`) находится в карантине (#662,
[`vk-credential-quarantine.md`](vk-credential-quarantine.md)): его нельзя
переносить в GitHub, «проверять ещё раз», ротировать алиасом или обходить
ожиданием. Policy v4 отклоняет этот алиас до любого provider-вызова.

Поддерживаемый credential — **ключ доступа самого сообщества** 60805374:
в интерфейсе VK откройте сообщество → `Управление → Дополнительно →
Работа с API → Ключи доступа → Создать ключ` и включите право **«Стена»**
(фактически выданный ключ также несёт `photos, docs, messages, manage,
stories, market`). Значение ключа — секрет: не присылайте его в чат, не
кладите в Git, issue, workflow inputs или артефакты.

24.10.2026 ключ проверен read-only пробником (workflow
`legendary-poet-vk-group-key-probe.yml`, target `lord-god`):
`groups.getTokenPermissions` вернул `wall` в списке прав, а
`groups.getById` подтвердил сообщество `60805374`
(`the_lord_god_is_my_strength`). Provider writes при проверке: 0.

### 2. GitHub Environment и секрет

Один раз в репозитории:

1. `Settings → Environments`, имя ровно `The_Lord_God_VK`.
2. В `Deployment branches and tags` выберите `Selected branches` и разрешите
   только `main`.
3. Включите `Required reviewers` и укажите оператора, который утверждает
   production-запуски.
4. В `Environment secrets` добавьте `LORD_SECRET` и вставьте только ключ
   сообщества из шага 1.

Workflow доступен для ручного запуска только после merge в `main`. Оба job —
и `prepare`, и `apply` — ссылаются на этот Environment, поэтому GitHub запросит
approval перед каждым из них; секрет при этом остаётся внутри runner и не
попадает в логи, Git или артефакты.

## Этап 1 — prepare (без provider-записи)

В GitHub: `Actions → Lord God VK postponed wave → Run workflow`, ветка `main`:

- `action=prepare`;
- `lane=text-only` (по умолчанию) — текстовые посты ключом сообщества;
  `lane=charnock` — серия Чарнока частями, текстом (будни 13:00);
  `lane=full` требует пользовательского аудита и сейчас не используется;
- `start_date` можно оставить пустым — workflow возьмёт ближайший будущий
  понедельник по Europe/Moscow; либо укажите будущий понедельник `YYYY-MM-DD`.

Утвердите Environment deployment. Workflow выполнит строго по порядку:

1. импортирует секрет в ephemeral `VCM_DATA_DIR` алиасом
   `vk-lord-god-community-key` (`community-key-login` сам валидирует ключ);
2. проверит `community-key-capabilities`: ровно два read-вызова
   (`groups.getTokenPermissions` и `groups.getById`), право `wall` обязательно,
   сообщество обязано быть `60805374`;
4. read-only checkout `state/lordchrist-telegram`, локально материализует
   очереди successor/depth-v2/depth-v3 и эффективный depth-v3 ledger
   (в state-ref ничего не пишет);
5. при `lane=full` построит свежий аудит стены и найдёт созданный bundle
   `vk-wall-content-audit-*` (timestamp не угадывается); при `lane=text-only`
   (по умолчанию) этот шаг пропускается — аудит ключом сообщества недоступен;
6. соберёт backlog: `lane=text-only` — `--text-only --video-count 0`,
   `lane=full` — `--video-count 60 --max-views 1500`; в обоих случаях
   `--days 60 --telegram-count 1 --quote-count 24 --historical-text-mode full`;
7. соберёт неизменяемый provider-inert handoff
   (`00-backlog.json` … `08-apply-intent.json`, `manifest.json`) и проверит
   manifest, SHA файлов, source/plan/intent и будущие `publish_date`.

Артефакты prepare: `lord-god-vk-audit-<run_id>-1` (90 дней) и
`lord-god-vk-handoff` (30 дней). В summary prepare возьмите значения для apply:

- ID этого prepare-run;
- `operation_count`;
- `plan_self_digest`;
- `operation_set_digest`;
- готовую строку подтверждения формата
  `APPLY-LORD-GOD-VK:<prepare_run_id>:<plan_self_digest>:<operation_set_digest>`.

Prepare не вызывает `wall.post` и не запускает `wave apply`. Если проверка
ключа падает, волна останавливается: workflow не делает автоматических
повторов; сначала чинится сам ключ (права/значение в настройках сообщества)
или секрет в Environment.

## Этап 2 — apply (одна provider-запись)

Запускайте apply отдельным dispatch и как можно скорее после prepare: если
первый `publish_date` окажется не позже `now + 5 минут`, workflow откажется
применять план и потребуется новый prepare.

`Actions → Lord God VK postponed wave → Run workflow`, ветка `main`:

- `action=apply`;
- `prepare_run_id` — ID успешного prepare-run;
- `plan_self_digest` — точное значение из prepare summary;
- `operation_set_digest` — точное значение из prepare summary;
- `confirm` — точная строка
  `APPLY-LORD-GOD-VK:<prepare_run_id>:<plan_self_digest>:<operation_set_digest>`.

Утвердите Environment deployment. Workflow скачает `lord-god-vk-handoff`
именно из указанного prepare-run в тот же repository-relative каталог
`operator-output/lord-god-vk/handoff`, сверит manifest и SHA всех файлов,
`source.verify_artifacts`, `intent.assert_matches`, оба digest, включённый
`enable_provider_writes` и будущие даты; затем повторит проверку ключа
сообщества (`community-key-login` + `community-key-capabilities`) и ровно
один раз выполнит:

```text
video-manager wave apply --source .../06-source.json --plan .../07-plan.json \
  --intent .../08-apply-intent.json --repository-root . \
  --journal-directory operator-output/lord-god-vk/apply-journal \
  --vk-account vk-lord-god-community-key \
  --ci-operator-confirmation WAVE-CI-APPLY:<plan_self_digest>:<operation_set_digest> \
  --enable-provider-writes
```

Движок волны запрещает ambiguous-мутации в CI по умолчанию; исключение —
только точный токен `WAVE-CI-APPLY:<plan_self_digest>:<operation_set_digest>`,
который workflow выводит из подтверждённых оператором digest'ов. Без него
(или с чужим digest) apply отклоняется до создания журнала и до provider-вызовов.

## После apply: стоп-правила

- **Не запускайте apply второй раз** для того же handoff, если шаг apply уже
  стартовал или исход неизвестен. Re-run того же workflow запрещён условием
  `github.run_attempt == 1`, но и новый dispatch с тем же подтверждением при
  неизвестном исходе запрещён процедурой.
- Итоговый артефакт: `lord-god-vk-apply-<apply_run_id>-1` — `result.json`,
  `preflight-summary.json`, журналы операций и, если есть,
  `token_capabilities_flood_state.json`. Токен и token store в артефакты не
  загружаются.
- Исход `unknown` не повторяется вслепую: только `video-manager wave reconcile`
  по точному плану и загруженному результату/журналу из apply-артефакта.
- Code 9 на любом методе останавливает волну; TTL и «подождать и повторить»
  политикой не предполагаются.
- Если apply упал **до** шага `Apply the reviewed postponed-post wave exactly
  once` (проверки digest, токена или probes), provider-запись ещё не начиналась:
  исправьте причину и используйте новый dispatch с тем же точным подтверждением
  либо, при истёкших датах, новый prepare.

## Приём новых постов от оператора

Посты, присланные текстом в чат, не вставляются в уже собранный план. Порядок:
текст сверяется с первоисточником и дубликатами, публикуется/фиксируется в
Telegram либо оформляется отдельным reviewed text-слотом в backlog, после чего
prepare повторяется с новой датой старта для ещё не запланированного хвоста.
Уже запланированные слоты не переиспользуются; в VK по-прежнему идут только
посты со статусом `published` + `provider_effect=verified`.
