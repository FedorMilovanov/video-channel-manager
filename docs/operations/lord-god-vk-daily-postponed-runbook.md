# Господь Бог — Сила Моя: ежедневные отложенные посты ВКонтакте

Статус: **GitHub Actions, ручной двухэтапный запуск**. Поддерживаемый путь —
workflow [`.github/workflows/lord-god-vk-postponed-wave.yml`](../../.github/workflows/lord-god-vk-postponed-wave.yml):
сначала `action=prepare`, затем отдельным запуском `action=apply`. Единственный
писатель в VK — `video-manager wave` с адаптером `vk.lord_god.postponed_wall`
(policy `vk-lord-god-postponed-wall-v3`). Расписания (`schedule`) у workflow нет:
один успешный apply передаёт VK всю отложенную волну, дальше посты публикует сам VK.

## Точная цель

| Поле | Значение |
| --- | --- |
| `project_key` | `lord-god-strength` |
| Сообщество | `60805374` (`† Господь Бог - Сила Моя! †`) |
| `owner_id` | `-60805374` |
| Публичная ссылка | https://vk.ru/the_lord_god_is_my_strength |
| VK Видео | https://vkvideo.ru/@the_lord_god_is_my_strength |
| Credential alias | `vk-own-app-54555649` (только он) |
| GitHub Environment | `lord-god-vk-production` |
| Environment secret | `VK_OWN_APP_54555649_TOKEN` |
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

## Одноразовая настройка

### 1. Собственная авторизация VK приложения 54555649

Старый общий токен (алиасы `legendary-poet` / `default`, сторонний
`client_id=2685278`) находится в карантине (#662,
[`vk-credential-quarantine.md`](vk-credential-quarantine.md)): его нельзя
переносить в GitHub, «проверять ещё раз», ротировать алиасом или обходить
ожиданием. Policy v3 отклоняет этот алиас до любого provider-вызова.

Под аккаунтом — администратором сообщества откройте согласие собственного
приложения `54555649` со scopes `video,wall,groups,offline` (implicit flow,
redirect на `blank.html`), например:

```text
https://oauth.vk.com/authorize?client_id=54555649&scope=video,wall,groups,offline&redirect_uri=https://oauth.vk.com/blank.html&response_type=token&display=page
```

После согласия адресная строка будет содержать фрагмент
`#access_token=...&expires_in=0&user_id=...`. Значение `access_token` — секрет:
не присылайте его в чат, не кладите в Git, issue, workflow inputs или артефакты.

### 2. GitHub Environment и секрет

Один раз в репозитории:

1. `Settings → Environments → New environment`, имя ровно
   `lord-god-vk-production`.
2. В `Deployment branches and tags` выберите `Selected branches` и разрешите
   только `main`.
3. Включите `Required reviewers` и укажите оператора, который утверждает
   production-запуски.
4. В `Environment secrets` добавьте `VK_OWN_APP_54555649_TOKEN` и вставьте
   только новый токен приложения `54555649` из шага 1.

Workflow доступен для ручного запуска только после merge в `main`. Оба job —
и `prepare`, и `apply` — ссылаются на этот Environment, поэтому GitHub запросит
approval перед каждым из них; секрет при этом остаётся внутри runner и не
попадает в логи, Git или артефакты.

## Этап 1 — prepare (без provider-записи)

В GitHub: `Actions → Lord God VK postponed wave → Run workflow`, ветка `main`:

- `action=prepare`;
- `start_date` можно оставить пустым — workflow возьмёт ближайший будущий
  понедельник по Europe/Moscow; либо укажите будущий понедельник `YYYY-MM-DD`.

Утвердите Environment deployment. Workflow выполнит строго по порядку:

1. импортирует секрет в ephemeral `VCM_DATA_DIR` алиасом `vk-own-app-54555649`;
2. проверит `token-capabilities`: известные scopes обязаны быть ровно
   `video,wall,groups`;
3. сделает по одному read-probe `community-probe` (`groups.getById`) и
   `wall-probe` (`wall.get`) для сообщества `60805374`;
4. read-only checkout `state/lordchrist-telegram`, локально материализует
   очереди successor/depth-v2/depth-v3 и эффективный depth-v3 ledger
   (в state-ref ничего не пишет);
5. построит свежий аудит стены и найдёт созданный bundle
   `vk-wall-content-audit-*` (timestamp не угадывается);
6. соберёт backlog `--days 60 --video-count 60 --telegram-count 1
   --quote-count 24 --historical-text-mode full --max-views 1500`;
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

Prepare не вызывает `wall.post` и не запускает `wave apply`. Если probes падают
(в том числе code 9), волна останавливается: workflow не делает `flood-reset`,
вторых проб и автоматических повторов; issue #662 остаётся открытым до успешных
проб новым токеном.

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
`enable_provider_writes` и будущие даты; затем повторит token gates
(capabilities и по одному probe) и ровно один раз выполнит:

```text
video-manager wave apply --source .../06-source.json --plan .../07-plan.json \
  --intent .../08-apply-intent.json --repository-root . \
  --journal-directory operator-output/lord-god-vk/apply-journal \
  --vk-account vk-own-app-54555649 --enable-provider-writes
```

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
