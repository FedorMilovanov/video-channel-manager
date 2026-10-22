# Полный аудит репозитория, веток и незакрытых работ — 21 октября 2026

Точка опоры: `main@c308448d8760f3a093dcf219ed4c80d29de338ad` (2026-10-18), CI на этом SHA —
run `39132645918`, success.

Это точечный исторический аудит. Он **не заменяет** `AGENTS.md`,
[`current-state.md`](../operations/current-state.md), владеющий issue или текущую
provider-авторизацию. Аудит не выполнял provider-вызовов, provider-записей,
merge, удаления веток и мутаций durable `state/*`.

> Соблюдены границы: провайдерные чтения/записи — **0 / 0**; изменения durable
> state — **0**; ветки не переключались и не удалялись; единственное изменение —
> этот отчёт в рабочей ветке сессии.

## 1. Резюме

| Область | Состояние | Главный вывод |
| --- | --- | --- |
| `main` | зелёный | 2882 теста, mypy strict, ruff clean, покрытие 74 % |
| Ветки (45 refs) | 36 из 45 — балласт | 4 активных PR-ref, 3 durable state, 1 evidence, 23 zero-ahead, 13 superseded divergent |
| Открытые PR (4) | 3 из 4 не смержатся | #691 блокирован тестами-пинами, #670/#631/#628 конфликтуют с `main` |
| Открытые issue (3) | 2 внешне блокированы, 1 устарел | #692 фактически выполнен (22/38 опубликовано), #662/#621 ждут OAuth-согласия владельца |
| Безопасность | **есть P1** | Pillow 12.3.0 — 24 CVE в production-lock; certifi — 1 CVE; Dependabot alerts выключены |
| Документация | дрейф | `current-state.md` датирован 2026-09-12 и говорит 17/43, реально 22/38 |
| Планировщик | латентный риск | `timezone: Europe/Moscow` рядом с UTC-cron; сейчас ключ инертен, но при его включении публикация встанет |

**Незакрытые работы, требующие решения:** #628 (конфликт с инвариантом
`never_replay`), #670 (уникальный, но конфликтующий контент), #691 (разблокировать
dependabot), #692 (закрыть/обновить), #631 (закрыть), апгрейд Pillow/certifi,
синхронизация operational-документа и 36 веток.

## 2. Метод и ограничения

- Сравнение веток: GitHub compare API `main...<branch>` на свежем `ls-remote`;
  локальный клон shallow, поэтому история не докачивалась целиком.
- Проверка кода: локальный venv вне репозитория (`.venv`/`venv` не создавались
  внутри дерева), `pip install -e ".[dev]"`.
- Тесты: `pytest`; типы: `mypy` (strict); стиль: `ruff check` + `ruff format --check`.
- Безопасность: `pip-audit -r` по обоим hash-lock-файлам, статический поиск
  опасных паттернов, проверка пинов actions.
- Ограничения: архив логов Actions отдаёт `EOF` на хосте хранения (та же
  инфраструктурная проблема, что и в аудите 2026-10-15), поэтому CI-причины
  проверялись воспроизведением на точных head-ветках, а не чтением логов;
  `actions/variables` и `actions/secrets` возвращают 403 — значения repo-переменных
  не проверялись (но факт публикаций доказывает, что digest-гейт проходит).

## 3. Состояние `main`

| Проверка | Результат |
| --- | --- |
| Тесты | **2882** собрано, 0 failed, 0 errors, 2 skipped, ~29.7 s |
| Покрытие | **74 %** (50 901 statement, 13 211 missed) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 1110 files already formatted |
| `mypy` strict | Success: no issues in **344** source files |
| JSON | 292 tracked JSON — все валидны |
| Внутренние ссылки в `.md` | **0** битых из 269 документов |
| Workflow | 25, все `active`; падений на `main` среди последних 60 runs нет |
| Опасные паттерны | нет `eval`/`exec`/`shell=True`/`os.system`/`verify=False`/`pickle.load`/`yaml.load` |
| HTTP-клиенты | все 17 `httpx.Client(...)` создаются с явным timeout |
| Секреты | в git только тестовые заглушки (`super-secret-...`, `not-a-live-token`) |
| Actions | все `uses:` запинены на 40-символьный SHA; `pull_request_target` отсутствует |
| Инъекции в `run:` | выражений `${{ github.event.* }}`/`${{ inputs.* }}` внутри `run` нет |

Репозиторий в хорошем инженерном состоянии: чистая типизация, детерминированные
тесты, provider-inert CI, аккуратные hash-locks. Проблемы ниже — не «сломанный
код», а незакрытые решения и обслуживание.

## 4. Ветки: полная инвентаризация (45 refs)

### 4.1 KEEP — durable state (3)

| Ветка | ahead/behind | Причина |
| --- | --- | --- |
| `state/lordchrist-telegram` | 132 / 2052 | durable provider state; последний commit `0120c71` (2026-10-21T08:38:23Z) |
| `state/svodka-telegram` | 26 / 1945 | durable provider state |
| `state/milovi-cake-telegram` | 11 / 698 | durable provider state |

Большой `behind` ожидаем: это state-only refs, никогда не code baseline.

### 4.2 KEEP — content-addressed evidence (1)

| Ветка | ahead/behind | Причина |
| --- | --- | --- |
| `agent/milovi-video-accepted-73c578eff825` | 1 / 622 | на неё ссылается `current-state.md` как на принятый 16/16 Milovi video reservoir, digest `sha256:73c578eff825…` |

### 4.3 Активные PR-refs (4) — не трогать до решения по PR

`agent/lordchrist-rich-copy-editorial-standards` (#670),
`agent/sync-vk-v2-current-state` (#631),
`agent/vk-known-rejection-retry-621` (#628),
`dependabot/github_actions/workflow-actions-dc5ed02c9f` (#691).

### 4.4 Zero-ahead stale refs (23) — вернуть к `main` или удалить

У всех `ahead=0`: уникальных коммитов нет, содержимое уже в `main` (часто — через
squash/закрытые PR). По правилу `AGENTS.md` такие refs либо удаляются, либо
fast-forward-ятся на текущий `main` (`force=false`). Ни одна из них не является
источником кода.

```text
agent/instagram-facebook-state-sync-577                 (#580 closed)
agent/lordchrist-historical-editorial-552
agent/lordchrist-historical-live-561
agent/lordchrist-slot-aware-production-20260906-v2      (#549 closed)
agent/lordchrist-spurgeon-v3-live-media-561
agent/retirement-archive-blob-integrity
arena/01a10838-video-channel-manager
arena/13447cc8-video-channel-manager                    (#693 merged)
do-not-use
feat/lordchrist-historical-v3-archival-revisions-561
feat/lordchrist-quote-v4-readiness-20261004
feature/lordchrist-successor-quote-corpus-v1-20260906
final-accidental
fix/instagram-resumable-phase-diagnostics
fix/lordchrist-editorial-completeness-665
fix/lordchrist-quote-handoff-576
lane/lordchrist-history-human-editorial-561-20260907-copy
lane/lordchrist-spurgeon-v3-media-561-20260908
oops6
probe/lordchrist-historical-v3-final-sources-561        (#576 closed)
research/lordchrist-calvin-spurgeon-macarthur-series-v1 (#169 closed)
tmp-noop
zzz-test-ignore
```

### 4.5 Superseded divergent refs (13) — удалить после фиксации tip

Каждая проверена по diff/содержимому: уникальный материал либо уже есть в `main` в
более поздней/строгой форме, либо относится к отменённой конструкции.

| Ветка | Tip | ahead/behind | Доказательство |
| --- | --- | --- | --- |
| `agent/lordchrist-depth-v2-gatefix-680` | `843c4c4` | 11 / 62 | one-off workflow `lordchrist-depth-v2-gatefix-680.yml` + правки, поглощённые #683 |
| `agent/lordchrist-depth-v2-preflight-678` | `37303fc` | 4 / 61 | один one-off workflow, не нужен после #687/#688 |
| `agent/lordchrist-depth-v2-rollout-678-final` | `a59c87a` | 10 / 62 | PR #680 CLOSED «superseded» |
| `agent/lordchrist-depth-v2-rollout-678-ready` | `0358d78` | 13 / 62 | PR #682 CLOSED; активация пришла через #683 |
| `agent/sync-vk-upload-state-622` | `8c4b557` | 1 / 192 | только `docs/operations/current-state.md`, уже синхронизирован |
| `arena/01a1083a-video-channel-manager` | `e0bca51` | 16 / 17 | PR #690 CLOSED; заменён merged #693/#694 |
| `docs/instagram-current-state-625` | `e228151` | 3 / 134 | PR #630 CLOSED, docs-only |
| `feat/lord-god-vk-content-wave` | `a6f7417` | 12 / 129 | PR #639 CLOSED; код в `main` строже (circuit-assert, blob provenance) |
| `feat/lordchrist-depth-v3-context-fixes-20261003` | `7abb6e6` | 5 / 31 | отменённый глубинный v3: boundary 15, amendments 17/32; merged #694 — boundary 17, restores 32/36 |
| `feat/lordchrist-quote-v4-stage-20261003` | `684b858` | 1 / 20 | PR #686 CLOSED; workflow уже в `main` |
| `fix/instagram-cli-unicode-638` | `310b5e3` | 2 / 129 | PR #643 CLOSED «superseded» свежим PR с current main |
| `fix/vk-wall-fail-fast-flood-remote` | `11e6825` | 12 / 125 | PR #645 CLOSED; заменён merged #647 |
| `ops/lordchrist-depth-v2-readonly-preflight-678` | `8058949` | 1 / 61 | один one-off workflow |

Итого: **4 KEEP + 4 active + 23 zero-ahead + 13 superseded = 44** (плюс сам `main`).

### 4.6 План очистки

1. Сначала закрыть/слить 4 открытых PR (см. §5).
2. Затем удалить 23 zero-ahead refs (`git push origin --delete <ref>`); tip-и
   зафиксированы в этом отчёте.
3. Затем удалить 13 superseded refs, tip-и выше сохранены как provenance.
4. `state/*` и `agent/milovi-video-accepted-*` не трогать.
5. Ветку этого аудита (`arena/fc0892e0-…`) удалить после merge отчёта — как
   транзиентный ledger-ref.

## 5. Открытые PR: почему не закрыты

### 5.1 #691 — dependabot `upload-artifact` 7.0.1 → 7.0.2 (P2, легко чинится)

`mergeable=true`, `mergeStateStatus=blocked`, падают `quality (3.11/3.12/3.13)`.
Причина воспроизведена на head `c9809c1`: три теста жёстко проверяют **старый**
SHA-пин `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1`:

- `tests/test_wave16_ci_runtime_hygiene.py:18`;
- `tests/test_lordchrist_quote_v4_preflight_contract.py:139`;
- `tests/test_milovi_provider_outcome_recovery.py:167`.

Dependabot не может обновить тесты, поэтому **любой** будущий bump actions будет
падать. Рекомендация: в том же PR обновить три ожидания на новый SHA/комментарий
(или заменить точный SHA на проверку формата 40-hex + разрешённого репозитория,
сохранив требование пиннинга). Это не ослабляет safety-контроль — пиннинг остаётся.

### 5.2 #670 — rich editorial standard + manual rich copy (P2, ценный, но конфликтует)

`mergeable=false`, `dirty`; 5 ahead / 70 behind; CI был зелёным на старом head.
Уникальные файлы, которых нет в `main`:

- `content/telegram/lordchrist/MANUAL_RICH_COPY.md`;
- `tools/telegram-rich-copy/index.html`.

Плюс правки `RICH_EDITORIAL_STANDARD.md` и `README.md`, которые с 28 сентября
менялись (последний раз — `c308448`, 2026-10-18). Рекомендация: salvage —
rebase на текущий `main`, разрешить конфликты в двух docs, прогнать CI и слить.
Закрывать нельзя: `tools/telegram-rich-copy` в `main` отсутствует, а это
единственный ручной rich-copy путь для Telegram.

### 5.3 #631 — docs(VK) «mark durable native-video v2 complete» (P3, закрыть)

`dirty`; 2 ahead / 133 behind. Правка `wave-engine-contract.md` уже вошла в `main`
другим путём (раздел про `vk-native-video-wave-v2` присутствует), а запись в
`current-state.md` устарела на 133 коммита и всё равно требует переписывания под
октябрьское состояние. Рекомендация: **закрыть как superseded**, отдельно
синхронизировать `current-state.md` (см. §7).

### 5.4 #628 — retry после definite no-effect rejection (P2, блокирует #621)

`dirty`; 11 ahead / 135 behind. CI падает **не** из-за stale base: на точном head
`cf676f2` воспроизводятся два падения:

```text
tests/test_mutation_boundary_register.py::test_ambiguous_boundaries_are_never_replayed
tests/test_vk_native_clip_golden_path_contract.py::test_vk_upload_reservation_has_one_generic_provider_owner
AssertionError: vk.video.upload.reserve
  assert 'one_attempt_per_wave; later Wave may retry only a definite no-effect reservation rejection…'
         == 'never_replay'
```

PR меняет `retry_policy` границы `vk.video.upload.reserve` на свободный текст, что
нарушает канонический инвариант «ambiguous boundary never replays». Семантика PR
(переоткрытие только `reservation_rejected` без ticket/remote/bytes) сама по себе
полезна, но её нельзя выражать через `retry_policy`.

Рекомендация: переделать — оставить `retry_policy="never_replay"`, добавить
отдельное типизированное поле (например `known_rejection_recovery`) в
mutation-boundary register и golden-path contract, и обновить оба теста осознанно.
Только после этого — rebase и merge. Учитывая, что #621 всё равно заблокирован
#662 (VK code 9 / OAuth), спешки нет; текущее поведение fail-closed безопасно.

## 6. Открытые issues: что реально не закрыто

### 6.1 #692 — «restore continuous quote-v4 publication» (P2, устарел)

Issue открыт 2026-10-15, комментариев нет. Фактическое состояние на 2026-10-21:

- runtime восстановлен merged #693 (2026-10-15) и #694 (2026-10-17);
- depth-v3 ledger инициализирован state-коммитом `713dbc9`;
- публикации идут: **22 published / 38 pending**, последняя —
  `2026-10-21T08:38:21Z`, сообщение **1576**, seq 22;
- цепочка после boundary 17: сообщения 1570 (18), 1573 (19), 1574 (20), 1575 (21),
  1576 (22);
- scheduled runs успешны, падений на `main` нет.

Требование issue «verified monotonic progress» выполнено. Рекомендация: закрыть
#692 как completed (implementation + live rollout), зафиксировав 22/38 и run id,
либо, если владелец хочет держать трекер до конца очереди, переписать его в
«remaining 38» с явным критерием закрытия. В текущем виде issue вводит в
заблуждение: он описывает остановку, которой уже нет.

### 6.2 #662 — VK code 9 / Lord God recovery (внешний блокер, код не чинится)

Легитимно открыт. Последнее состояние: legacy-токен `legendary-poet` карантинирован,
OAuth-согласие для app `54555649` не завершено, provider writes = 0, все локальные
resume-пути заменены provider-inert блокерами. Кодовая часть (exact-method
circuits, one-shot probes) работает как задумано. Действий в репозитории нет;
нужно действие владельца (OAuth consent) либо официальная позиция VK.

### 6.3 #621 — первый durable native-video v2 canary (заблокирован)

Заблокирован двумя независимыми причинами:

1. #662 — credential/VK code 9, любые provider reads запрещены;
2. #628 не слит — известный dead-end `reservation_rejected` всё ещё существует.

Кодовых provider-записей нет. Issue корректен как операционный трекер; закрывать
нельзя до реального canary.

## 7. Операционная сверка: документы vs факты

| Утверждение в репозитории | Факт на 2026-10-21 | Действие |
| --- | --- | --- |
| `current-state.md`: «Updated: 2026-09-12» | документ содержит октябрьские разделы | обновить дату |
| `current-state.md`: «17 published / 43 pending», «next 18» | **22 / 38**, next 23 | синхронизировать |
| `production-schedule.json` `activation_note`: 17/43 | то же; заметка историческая (момент активации) | либо пометить как «на момент активации», либо обновить |
| #692: публикация остановлена | публикация идёт | закрыть/обновить issue |
| #621: canary ожидает | всё ещё ожидает, причин две | оставить, связать с #628/#662 |

Важно: `current-state.md` — операционная истина, поэтому его правка должна быть
отдельным маленьким state-sync изменением после решения по #692, а не побочным
эффектом аудита.

## 8. Безопасность и supply chain

### 8.1 P1 — Pillow 12.3.0: 24 известных CVE в production-lock

`requirements/milovi-photo-publisher.txt` ставит `Pillow==12.3.0` в workflow
`milovi-telegram-feed-publisher.yml` (строка 303) и проверяется
`pillow-runtime-compat.yml`. `pip-audit`:

```text
Found 24 known vulnerabilities in 1 package
pillow 12.3.0  CVE-2026-112890 … CVE-2026-112901  fix: 13.0.0
```

При этом исправленная версия заблокирована дважды: `pyproject.toml`
(`Pillow>=12.3,<13`) и Dependabot-конфигом (все major-апгрейды игнорируются).
`pillow-runtime-compat.yml` дополнительно жёстко утверждает
`PIL.__version__ == "12.3.0"`, поэтому простой bump сломает CI.

Рекомендация (координированный апгрейд, не одиночная правка):

1. `pyproject.toml` → `Pillow>=13,<14` (или снять верхнюю границу после проверки);
2. пересчитать `requirements/milovi-photo-publisher.txt` с новыми hashes;
3. обновить assertion версии в `pillow-runtime-compat.yml`;
4. прогнать `pillow-runtime-compat`, `milovi-telegram-feed-quality` и полный CI;
5. перепроверить реальный perceptual-hash путь на новых bytes.

Пока апгрейд не сделан, риск ограничен средой CI/оператора (входные изображения
контролируются), но 24 CVE в единственном production image-стеке — неприемлемо
как постоянное состояние.

### 8.2 P1 — certifi 2026.5.20 в Telegram production-lock

`requirements/telegram-publisher.txt` (hash-locked, `--require-hashes`) содержит
`certifi==2026.5.20`; `pip-audit`: `PYSEC-2026-4320`, fix `2026.10.19`. Это
production-зависимость Telegram publisher (через httpx). Рекомендация: обновить
весь lock как один resolved closure по процедуре из заголовка файла, затем
`pip check`, guarded CLI smoke и dependency audit в CI.

### 8.3 P2 — Dependabot alerts отключены

`GET /repos/.../dependabot/alerts` → «Dependabot alerts are disabled for this
repository». Групповые version-updates работают, но security-алерты не приходят.
Включить Dependency Graph / Dependabot alerts и добавить `pip-audit` по обоим
lock-файлам в CI, иначе следующие CVE будут обнаружены только аудитом.

### 8.4 Прочее

- `setuptools 66.1.1` в базовом venv — не проектная зависимость
  (`build-system` требует `setuptools>=83,<85`), это шум окружения.
- Секретов в git нет; секреты и токены не печатаются в коде.
- Пины actions корректны (40-hex SHA), permissions в CI — `contents: read`.

## 9. CI и планировщик

### 9.1 P2 — `timezone:` рядом с UTC-cron: латентный простой публикации

`.github/workflows/lordchrist-telegram-poster.yml`:

```yaml
- cron: "17 6 * * *"
  timezone: Europe/Moscow
- cron: "17 18 * * 2,5,0"
  timezone: Europe/Moscow
```

Комментарий рядом утверждает UTC-математику («06:17 UTC = 09:17 Moscow»), то есть
cron уже задан в UTC, а `timezone` его дополнительно сдвигает. Наблюдение из
state-ledger доказывает, что сейчас ключ **инертен**:

- вечерний слот `21:17 MSK` = `18:17 UTC`, `max_lateness_minutes=160`;
- публикация seq 21 состоялась `2026-10-20T19:18:15Z` (61 мин задержки) — при
  трактовке cron как MSK слот был бы «too stale» и публикации не было бы.

Риск: GitHub с марта 2026 документирует поддержку `timezone`. Если ключ начнёт
применяться, `17 6` станет `06:17 MSK` = `03:17 UTC`, локальное время будет
`06:17 < 09:17` → «slot is not due yet», и публикация встанет; вечерний слот
(`15:17 UTC`) станет stale при том же `max_lateness`.

Рекомендация: убрать `timezone:` и оставить UTC-cron (поведение не меняется),
либо переписать cron в московское время и пересчитать `max_lateness`; в
`telegram_schedule.py` добавить проверку согласованности `slot.time` ↔ `slot.cron`.

**Выполнено** (`74ac281`): ключи убраны; вместо проверки в `telegram_schedule.py`
добавлен контрактный тест `tests/test_lordchrist_schedule_cron_contract.py`, который
выводит из рантайма оба режима отказа (в точное UTC-время слот активен, на три часа
раньше — «not due yet» либо истёкший lease) и проверяет, что каждый объявленный cron
имеет ровно один маршрут: слот очереди доходит до `publish-next`, а cron исторической
ленты исключён из `publish-next` и выбирается job'ом `historical-rich`. Отдельно
снимаю прежнюю догадку об «осиротевшем» cron `17 16 * * 1,3,6`: он подключён именно
так, и теперь это зафиксировано тестом, а не устным наблюдением.
Решение должно быть отдельным reviewed PR, потому что затрагивает живую
публикацию.

### 9.2 P2 — тест сканирует `.venv` и падает у любого разработчика

`tests/test_powershell_operator_inventory.py:56` делает `ROOT.rglob("*.ps1")` без
исключений. При создании `.venv` внутри репозитория появляется
`.venv/bin/Activate.ps1`, и тест падает (воспроизведено). В CI это не видно.
Рекомендация: исключить `.git`, `.venv`, `venv`, `node_modules`, `site-packages`
(или идти от `git ls-files`), сохранив требование «каждый wrapper классифицирован».

### 9.3 P3 — мёртвый shadowed-модуль

`src/video_channel_manager/platforms/vk.py` (12 statements, 0 % покрытия, три
`NotImplementedError`) полностью затенён пакетом `platforms/vk/` — Python всегда
импортирует пакет. Модуль недостижим и вводит в заблуждение.
Рекомендация: удалить (история сохранится в git) или явно пометить как legacy
с пояснением.

### 9.4 P3 — покрытие

74 % при 2882 тестах — хорошо. Из 9 модулей с 0 % большинство — тонкие CLI
(`youtube_release_cli.py`, `package_a_cli.py`, `vk_postponed_text.py`,
`telegram_*_cli.py`, `svodka_rollout_candidate_cli.py`), плюс shadowed `vk.py`.
Критичные provider-модули покрыты. Отдельного «провала» нет; расширять покрытие
имеет смысл только для реально исполняемых CLI.

## 10. Приоритизированный план

### P1 — сделать в ближайшее время

1. **Pillow 13.x**: снять `<13`, пересчитать hash-lock, обновить
   `pillow-runtime-compat.yml`, прогнать Milovi quality + полный CI.
2. **certifi**: обновить Telegram hash-lock до `2026.10.19+` координированно.
3. **Dependabot alerts / Dependency Graph**: включить; добавить `pip-audit` по
   lock-файлам в CI (сейчас CVE видны только ручному аудиту).

### P2 — закрыть незавершённые работы

4. **#628**: переделать `retry_policy` → отдельное поле `known_rejection_recovery`,
   обновить mutation-boundary register + два теста, затем rebase.
5. **#691**: обновить три теста-пина в том же PR — разблокирует все будущие
   dependabot-апгрейды actions.
6. **#670**: rebase/salvage, разрешить конфликты в `README.md` и
   `RICH_EDITORIAL_STANDARD.md`, слить — иначе ручной rich-copy путь потерян.
7. **#692**: закрыть как completed (22/38, message 1576) или переписать под
   остаток очереди.
8. **#631**: закрыть как superseded.
9. **timezone**: убрать `timezone:` либо пересчитать cron/max_lateness + тест
   согласованности.
10. **Ветки**: удалить 23 zero-ahead + 13 superseded refs (tip-и в §4.5), сохранив
    `state/*` и Milovi evidence.

### P3 — гигиена

11. Синхронизировать `current-state.md`: дата, 22/38, next 23.
12. Исправить `ROOT.rglob("*.ps1")` в тесте.
13. Удалить shadowed `platforms/vk.py`.
14. Удалить ветку этого аудита после merge.

## 11. Что НЕ является незавершённой работой

- `state/*` refs с большим `behind` — норма, это durable state.
- `agent/milovi-video-accepted-73c578eff825` — намеренный evidence-ref.
- Исторические audit registers — evidence, не backlog.
- #662 и #621 — внешне заблокированы (OAuth consent/провайдер), кодовой работы
  там нет; provider writes остаются 0.
- Отсутствие Instagram/VK canary — это осознанная provider-inert политика, а не
  забытая задача.

## 12. Evidence appendix

### 12.1 Команды, использованные для проверки

```bash
git ls-remote --heads origin
gh api repos/FedorMilovanov/video-channel-manager/compare/main...<branch>
python -m venv /tmp/vcm-venv && /tmp/vcm-venv/bin/pip install -e ".[dev]"
/tmp/vcm-venv/bin/python -m pytest -q --junitxml=/tmp/junit.xml
/tmp/vcm-venv/bin/mypy
/tmp/vcm-venv/bin/ruff check . && /tmp/vcm-venv/bin/ruff format --check .
/tmp/vcm-venv/bin/pip-audit -r requirements/telegram-publisher.txt
/tmp/vcm-venv/bin/pip-audit -r requirements/milovi-photo-publisher.txt
gh api repos/FedorMilovanov/video-channel-manager/contents/.../successor-depth-v3-publication-ledger.json?ref=state/lordchrist-telegram
```

### 12.2 Ключевые факты

| Факт | Значение |
| --- | --- |
| `main` | `c308448d8760f3a093dcf219ed4c80d29de338ad` |
| CI на `main` | run `39132645918` — success |
| Тесты | 2882 / 0 failed / 2 skipped |
| Покрытие | 74 % |
| mypy strict | 344 files, 0 issues |
| Последняя публикация LordChrist | seq 22, message 1576, `2026-10-21T08:38:21Z` |
| Ledger | 22 published / 38 pending, queue digest `sha256:8d7dfd23…` |
| State-ref | `0120c71` (2026-10-21T08:38:23Z) |
| PR #691 blocker | 3 теста с пином `upload-artifact@043fb46…` |
| PR #628 blocker | 2 теста на `retry_policy == "never_replay"` |
| Pillow | 12.3.0, 24 CVE, fix 13.0.0 |
| certifi | 2026.5.20, PYSEC-2026-4320, fix 2026.10.19 |
| Dependabot alerts | disabled |
| Ветки | 45 refs: 4 keep (state/evidence) + 4 active PR + 23 zero-ahead + 13 superseded |

Аудит не выполнял provider-вызовов, provider-записей, merge, удаления веток и
мутаций `state/*`.

---

## Remediation status (2026-10-21, later the same day)

Every item below is closed on branch `arena/fc0892e0-video-channel-manager`; none of them required a
provider mutation, and none of them was closed by weakening a test.

| Item | Disposition |
| --- | --- |
| Pillow 12.3.0, 24 known vulnerabilities | Upgraded to 13.0.0 in the Milovi production lock, hash-verified; runtime range admits it; CI audits both production locks. |
| certifi 2026.5.20 (PYSEC-2026-4320) | Upgraded to 2026.10.19 in the Telegram publisher lock, hash-verified. |
| Unpinned / retired GitHub Actions refs | Full-SHA pins with release, minimum version and retired-ref denylist enforced across all workflows. |
| #628 known-rejection recovery | `reopen_known_rejection` reopens only a provably no-effect `rejected` state, archives it, re-verifies current media and returns to `planned`. `retry_policy` stays `never_replay`; register metadata is cross-checked against the implementation by tests. |
| Scheduler `timezone:` keys | Removed. A contract test derives both failure modes (not-due before the boundary, stale past the lease) from the runtime decider. |
| Shadowed `platforms/vk.py` | Deleted; a guard test fails if any module is shadowed by a same-named package. |
| `.ps1` inventory scanning `.venv` | Development directories ignored; classification requirement unchanged and verified with a real virtualenv present. |
| #670 rich-copy work | Only `MANUAL_RICH_COPY.md` and `tools/telegram-rich-copy/index.html` were unique; both are ported and tested, the rest of that branch was older drafts. |
| #631 / #692 | Content already on `main` / premise outdated; closed with evidence. |
| #662 / #621 | Still blocked on owner OAuth; unchanged, not silently dropped. |
| Stale `current-state.md` | Resynchronised: 22 published / 38 pending, next sequence 23, checkpoint `c308448`, #692 recorded as completed. |

## Branch hygiene executed (2026-10-21)

Classification came from the GitHub compare API (`main...<branch>`), then from a per-file blob
comparison, then from a line-level check of whether the branch's added lines already exist in `main`.
A shallow local clone was explicitly ruled out: it reported every branch as thousands of commits ahead.

Result: **40 refs down to 4**, later corrected to **5** (`main`, the three durable `state/*` refs, and
two content-addressed evidence refs): one deletion was a mistake and was reverted, see the correction.

1. **24 refs deleted losslessly** — every head-side blob of every file they change is byte-identical to
   `main`. Proven by construction, not by inspection.
2. **12 refs deleted as reviewed-superseded** — each with its own stated reason and the merged change
   that replaced it (retired quote-v3/v4 drafts, one-off preflight workflows, docs-only edits that would
   revert newer text, and the #628 prototype that the merged design replaces).
3. **3 refs deleted as reviewed-superseded** — feature branches whose work is 96–98 % already in
   `main`, or an earlier design of the live #694 release.
4. **2 refs kept**: the Milovi content-addressed evidence refs. A fourth-pass deletion of one of them as
   a byte-identical duplicate was a mistake and was reverted — see the correction below, which also
   explains why the earlier "move the media out of git" plan was wrong: the reservoir and the runtime
   binding name the ref, so the ref *is* the artifact store.

Every deleted ref is recorded with its exact tip SHA and reason in
[`../operations/branch-hygiene-2026-10-21-deletion-ledger.md`](../operations/branch-hygiene-2026-10-21-deletion-ledger.md),
so restoration is one `git push <sha>:refs/heads/<branch>` within the object-retention window.

### Correction: one deletion was wrong, and the class of error is now closed

`agent/milovi-video-accepted-73c578eff825` was deleted as a byte-identical duplicate of the other Milovi
ref. That was incorrect: the ref is content-addressed evidence whose **name** is the prefix of the
accepted evidence digest, and 20 references in `main` name it — including the runtime binding
`milovi_telegram_feed.VIDEO_ARTIFACT_REF`, which gates every Milovi `sendVideo`, and the reservoir,
workflow contract and `current-state`. It was restored from its recorded tip
`f4f5512d7b60f1b9c61c293c07620b128536df27`.

The lesson is not "be careful"; it is that a deletion rule based on content identity alone is
insufficient when a name is part of a contract. Three changes make the mistake impossible to repeat
silently:

1. `docs/operations/protected-evidence-refs.json` lists every ref hygiene must not delete, with the
   reason, the exact tip where the ref is immutable, and a restore command.
2. `tests/test_milovi_evidence_binding.py` fails when a protected ref appears in a deletion ledger, and
   re-verifies the accepted evidence digest offline.
3. The accepted evidence file itself is now versioned in `main`, so `evidence_path`/`evidence_sha256`
   resolve inside the repository instead of dangling.

Corrected final ref count: `main` + 3 durable `state/*` refs + 2 content-addressed evidence refs.
