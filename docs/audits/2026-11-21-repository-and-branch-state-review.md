# Ревизия репозитория, веток и незакрытых работ — 2026-11-21

**Тип:** point-in-time read-only review. **Не** является операционной инструкцией, разрешением на provider mutation или заменой `docs/operations/current-state.md`.
**База:** `main` = `66c91a41c507951d95033a5437921bf3a5443c3b` (2026-11-21 11:52 UTC), локальный checkout совпадает с этим tip.
**Provider-эффекты этой ревизии:** `none`. Выполнены только `git`, GitHub REST/GraphQL (чтение) и локальный запуск тестов. Ни одного запроса к YouTube, VK, Telegram, Instagram, Meta.

## 1. Метод и границы

Проверено:

- полный список remote refs (`git ls-remote`, GitHub compare API — не по возрасту и не по префиксу);
- открытые и недавно закрытые PR, их check runs, exact head SHA, mergeable state;
- все 18 открытых issues: заголовок, тело, последние комментарии, даты активности;
- protected evidence refs и правила классов ветвей из `AGENTS.md`;
- операционные ledger-состояния `state/lordchrist-telegram` и `state/milovi-cake-telegram` (чтение, без записи);
- инженерный контур: локальный прогон `pytest`, `ruff check`, `ruff format --check`, `mypy`, coverage;
- документация состояния, реестры coverage/диспозиций/mutation boundaries/retirement.

Ограничения:

- GitHub Actions log-файлы в этой среде недоступны (`results-receiver.actions.githubusercontent.com` вне allowlist). Причины падений scheduled-запусков установлены по именам шагов и журналам прогонов, а причина красного CI PR #1051 — локальным воспроизведением на точном head ветки.
- Server-side branch protection/rulesets через API недоступны текущему интеграционному токену (HTTP 403). Зафиксированные в `current-state.md` 8 required checks — **документированное свидетельство**, здесь не перепроверено.
- Owner-машина (Windows, `DESKTOP-O3FDOA4`) недоступна: утверждения о локальном runtime взяты из issue-комментариев с указанием даты и не считаются текущими.

## 2. Резюме

| Область | Вердикт | Основание |
| --- | --- | --- |
| Инженерный контур | **Здоров** | 4800 passed / 1 skipped, Ruff check + format чисто (1478 файлов), strict mypy 366 файлов, coverage 76.72 % при floor 75.01 %, CI на `main` зелёный |
| Архитектура и контракты | **Зрелая, но перегруженная** | 366 модулей, 43 workflow, 141 скрипт, 255 документов; 24 из 28 диспозиций ждут решения владельца |
| Доставка по расписанию | **Сломана как механизм** | Charnock: 4 из 4 scheduled-запусков упали на выборе слота; Milovi: 18 запланированных публикаций не вышли, слоты истекли |
| Редакционный шлюз | **Единственный реальный блокер** | 18 quote-v6 + 8 quiz-карточек на HOLD, 2 PR без независимого ревьюера |
| Ветки | **Управляемо, но есть мусор** | 18 refs: 10 кода/состояния/доказательств (защищены), 2 в открытых PR, 1 спасаемая, 5 кандидатов на удаление |
| Документация состояния | **Отстала** | `current-state.md` зафиксирован на checkpoint `c308448d`, от `main` его отделяют **574 коммита**; README-цифры устарели примерно в 6 раз |

**Главный вывод:** репозиторий инженерно сильнее, чем его операционная доставка. Код, тесты и guard-контуры работают; сбои происходят там, где нужен внешний исполнитель — GitHub cron, живой ревьюер, квоты и изолированные credentials.

**Отдельно:** зелёный scheduled-run **не означает публикацию**. Сегодняшние запуски quote-v6 (`44919361464`, `44917246886`) — `success`, но шаги 13–17 `sendMessage` — `skipped`; Shorts-publisher — `success` при ledger `0/4 + 0/4`; Milovi school-dispatcher — `success`, dispatch — `skipped`.

## 3. Инженерный контур (проверено локально 2026-11-21)

Среда: Python 3.11.2, чистый venv, `pip install -e ".[dev]"`.

| Гейт | Результат |
| --- | --- |
| `pytest` | **4800 passed, 1 skipped, 13 subtests passed** за 70.89 s (собрано 4801 тест) |
| coverage | **76.72 %** по 56 347 statements (floor 75.01 %, запас 1.71 п. п.) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 1478 файлов уже отформатированы |
| `mypy src --show-error-codes` | Success, 366 source files |
| CI на `main` | quality 3.11/3.12/3.13, PowerShell 5.1/7/Linux, gitleaks, Milovi feed, Pillow — все `success`/штатный `skipped` |

Масштаб:

- `src` — 366 файлов, 111 241 строка;
- `tests` — 607 файлов (604 `test_*.py`), 109 906 строк;
- `docs` — 255 Markdown-файлов, 37 148 строк;
- `.github/workflows` — 43 YAML; `scripts` — 141 Python-файл;
- `content` — 767 файлов, 66 MB; `.git` — 310 MB.

Гигиена кода: **0** маркеров TODO/FIXME/XXX/HACK в `src`, `tests`, `scripts` — незавершённость живёт в issues, а не в комментариях.

### Наблюдения по качеству

1. **Coverage-запас тонкий.** 76.72 % против 75.01 %; любой крупный непокрытый модуль может уронить ratchet.
2. **Ratchet отстал от факта.** `src/video_channel_manager/cli/youtube.py`: floor 10.98 %, фактически **75.51 %** после #1053. Floor не поднят — регрессия в этом модуле может пройти незамеченной.
3. **24 из 28 диспозиций — `pending_owner_decision`** (`module-disposition.json`, замер 2026-11-04). Это не «мёртвый код», а ещё не принятые решения: из 366 модулей 28 имеют явную диспозицию, и 24 из них описаны статусом «ждём владельца».
4. **Документы расходятся с кодом.** `README.md` (17.11) сообщает `796 passed`, `14,306 statements`, `449` файлов форматирования; факт — 4800 тестов, 56 347 statements, 1478 файлов. `docs/roadmap.md` (05.08) всё ещё описывает программу Waves 0–13 как текущую.

## 4. Ветки: полная инвентаризация

Классификация по `AGENTS.md`: durable state refs, content-addressed evidence refs, ephemeral work branches. Удаление регулируется **классом**, а не возрастом.

### 4.1 Сводка

| Класс | Кол-во | Refs |
| --- | --- | --- |
| `main` | 1 | `main` |
| Durable state | 3 | `state/lordchrist-telegram`, `state/milovi-cake-telegram`, `state/svodka-telegram` |
| Content-addressed evidence | 6 | `agent/lordchrist-shorts4-media-20261106`, `agent/lordchrist-shorts8-media-20261106`, `agent/milovi-video-accepted-73c578eff825`, `agent/milovi-video-accepted-f0e25d9c905f`, `agent/milovi-video-muted-v12-3b680fe94b50`, `agent/milovi-video-muted15-80ee7f9fea` |
| Открытые PR | 2 | `agent/lordchrist-v6-three-calcified-translations-20261120` (#1049), `agent/lordchrist-v6-bilingual-word-review-20261120` (#1051) |
| Спасаемая работа | 1 | `fix/wave6-retired-import-dispatch-20261118` |
| Орфанные / superseded | 5 | `arena/27dc7396-…`, `arena/c2b6efc2-…`, `fix/milovi-vk-growth-photo-editorial-792`, `feat/lordchrist-1619-inline-callback-definitions`, `fix/lordchrist-1619-classic-instant-view-20261116` |

`docs/operations/protected-evidence-refs.json` перечисляет 10 refs: 9 существуют, `state/legendary-poet-telegram` зарезервирован и **не создан** (это корректно, но должно читаться как «не инициализирован», а не «потерян»).

### 4.2 Детально

| Ref | Класс | Tip | Дата | ahead/behind vs main | Диспозиция |
| --- | --- | --- | --- | --- | --- |
| `main` | baseline | `66c91a41` | 2026-11-21 | — | единственный code/runtime baseline |
| `state/lordchrist-telegram` | durable state | `bca3c01f` | 2026-11-20 | 297 / 2626 | **не удалять**; ledger quote-v6, quiz, Charnock |
| `state/milovi-cake-telegram` | durable state | `3ae7e91b` | 2026-11-07 | 27 / 1272 | **не удалять**; 18 pending-записей |
| `state/svodka-telegram` | durable state | `b7c06009` | 2026-08-19 | 26 / 2519 | **не удалять**; терминальный no-replay ledger |
| `agent/milovi-video-accepted-73c578eff825` | evidence | `f4f5512d` | 2026-08-19 | 1 / 1196 | **не удалять**: на имя ref ссылается `VIDEO_ARTIFACT_REF` |
| `agent/milovi-video-accepted-f0e25d9c905f` | evidence | `b77bbf5f` | 2026-10-21 | 1 / 566 | **не удалять** (воспроизводимость) |
| `agent/milovi-video-muted-v12-3b680fe94b50` | evidence | `686223b4` | 2026-11-06 | 1 / 306 | **не удалять** |
| `agent/milovi-video-muted15-80ee7f9fea` | evidence | `9331af0c` | 2026-11-06 | 1 / 301 | **не удалять** |
| `agent/lordchrist-shorts4-media-20261106` | evidence | `85990401` | 2026-11-06 | 1 / 297 | **не удалять** |
| `agent/lordchrist-shorts8-media-20261106` | evidence | `d45230ae` | 2026-11-06 | 1 / 288 | **не удалять** |
| `agent/lordchrist-v6-three-calcified-translations-20261120` | PR #1049 | `e60a0691` | 2026-11-19 | 5 / 3 | обновить ветку, провести ревью |
| `agent/lordchrist-v6-bilingual-word-review-20261120` | PR #1051 | `c01de43b` | 2026-11-19 | 14 / 2 | исправить форматирование, затем ревью |
| `fix/wave6-retired-import-dispatch-20261118` | ephemeral, **уникальная** | `a48f2a80` | 2026-11-18 | 13 / 20 | **спасти** в отдельном PR |
| `arena/27dc7396-video-channel-manager` | ephemeral orphan | `6826bf55` | 2026-11-02 | 6 / 409 | superseded; уникальны 4 бинарные иллюстрации |
| `arena/c2b6efc2-video-channel-manager` | ephemeral orphan | `84a36f91` | 2026-11-11 | 3 / 253 | superseded; уникальны 3 иллюстрации |
| `fix/milovi-vk-growth-photo-editorial-792` | ephemeral orphan | `0cc004d8` | 2026-11-05 | 2 / 309 | не влит research-документ на 49 источников |
| `feat/lordchrist-1619-inline-callback-definitions` | closed PR #975 | `9490b535` | 2026-11-16 | 6 / 118 | superseded — удалить после сверки tip |
| `fix/lordchrist-1619-classic-instant-view-20261116` | closed PR #974 | `ca37592b` | 2026-11-16 | 10 / 119 | superseded — удалить после сверки tip |

### 4.3 Почему `fix/wave6-retired-import-dispatch-20261118` стоит спасать

На `main` 28 скриптов помечены `_WAVE6_RETIRED_EXECUTOR = True`, но защита стоит только в `if __name__ == "__main__":`. Любой импорт и вызов `main()`/`run()` обходит её и доходит до provider-кода. Ветка добавляет **безусловный `raise` первой строкой** в 10 dispatchers и регрессионный тест, который проверяет это через AST и реальное исполнение в изолированном namespace. Ни один workflow эти dispatchers не импортирует (единственная ссылка — в другом retired-скрипте), поэтому риск минимален, а закрываемый класс дефектов — реальный: «retired executor снова запускаем из импорта».

### 4.4 Орфанные ветки: что в них уникально

- `arena/27dc7396` (02.11): статья о Реформации для Telegraph, `article-queue` запись, 4 изображения (Виттенберг, Вормс, Цвингли, Женева). `lordchrist-reformation-polished-draft.md` на `main` **байт-в-байт совпадает** с веткой; на `main` тема закрыта другой статьёй (`lordchrist-telegraph-charnock-history-02`) с тем же cover. Уникальны только 4 бинарных изображения.
- `arena/c2b6efc2` (11.11): «Рабство свободы» в каталоге `rich-v1/freedom/` с иллюстрациями «два всадника / рука / цепи». На `main` статья живёт в `rich-v1/rabstvo-svobody/` с другим визуальным рядом (вол/сын у порога/львиная клетка). Концепция superseded, уникальны 3 бинарных файла.
- `fix/milovi-vk-growth-photo-editorial-792` (05.11): research-документ «49 проверенных источников» для #792. На `main` отсутствует, issue на него не ссылается.

**Вывод:** ни одна орфанная ветка не содержит уникального кода. Решение по ним — редакционное: нужны ли альтернативные иллюстрации и research-библиография. Перед удалением зафиксировать tips (они в таблице) — восстановление `git push origin <sha>:refs/heads/<branch>`.

## 5. Открытые pull requests

### #1049 — `docs(lordchrist): correct three pending Russian translation calques without releasing`

- Head `e60a0691`, база `ff880bfe`, +189/−0, 3 файла, 5 коммитов, не draft.
- Checks: quality 3.11/3.12/3.13, PowerShell ×3, gitleaks, Milovi, Pillow — **success**; quote-v4 preflight — `skipped` (штатно).
- `mergeable=true`, `mergeable_state=behind` — требуется обновление ветки относительно `main`.
- Блокер: не технический, а **редакционный** — независимое двуязычное подтверждение и edition-specific права (issue #1044).

### #1051 — `docs(lordchrist): reconcile 18 pending EN/RU lexical risks and reader-facing quote formats`

- Head `c01de43b`, база `642b838f`, +1288/−0, 2 файла, 14 коммитов, **draft**, `behind` на 2 коммита.
- Красные гейты: `quality (3.11)`, `quality (3.12)`, `quality (3.13)` — шаг «Enforce quality gates».
- Причина воспроизведена локально на точном head: **`ruff format --check`** — 1 файл `tests/test_lordchrist_quote_v6_bilingual_previews_inert.py` требует переформатирования. `ruff check` чист, целевые тесты (5/5) проходят, strict mypy чист.
- Исправление: `ruff format tests/test_lordchrist_quote_v6_bilingual_previews_inert.py`, коммит, push, дождаться exact-head CI, затем снять draft **после** независимого ревью.

## 6. Незакрытые работы: 18 issues по направлениям

Легенда: **ACTIVE** — идёт кодовая/операционная работа; **HOLD** — редакционный или правовой запрет; **BLOCKED** — внешний блокер (credentials, квота, cron); **WAITING** — ждёт решения владельца/провайдера.

| # | Направление | Статус | Что фактически сделано | Что осталось / блокер |
| --- | --- | --- | --- | --- |
| 1044 | LordChrist quote-v6 | **HOLD** | ledger 30: **12 published/verified, 18 pending/impossible**; последняя публикация #1629 (19.11); publisher fail-closed; PR #1049/#1051 готовят редакцию | независимый ревьюер, права на издания, новый signed pending-only release |
| 1009 | LordChrist QUIZ | **HOLD** | ledger S03 10: **2 verified, 8 pending**; опубликован дефектный #1623 (17.11); #1010 закрыл серию | 8 переписанных вопросов + source/language/distractor review, новый release |
| 997 | Charnock 06–13 | **BLOCKED** | #09 опубликован 20.11 (message 1630, `verified`), календарь 8 слотов; у #06–#08 reissue-записи нет — только исторические удалённые id 1596–1598 | #06/#07/#08 не вышли; scheduled-cron падает на выборе слота 4/4; #13 editorial HOLD; впереди 24.11, 27.11, 01.12, 04.12 |
| 809 | Milovi Telegram | **BLOCKED** | 15 видео-слотов 08–22.11 + 3 school-слота; все **18 записей pending/impossible**, `message_id=null` | слоты 08–20.11 истекли; scheduled-run падает на `audit-expired` с 14.11; нужны новые даты/identities, не догон |
| 792 | Milovi VK | **BLOCKED** | отложенный календарь статей; аудит 19/19 public Clips | у 6 Clips публичный extractor не видит audio-форматов (риск «немого» видео), первый слот 21.11 19:00; VK code 9; research-док не влит |
| 869 | Lord God Instagram | **ACTIVE** | 7 published, 4 terminal_failure, 3 photo verified (17.11); Windows scheduler + 12/12 SHA preflight | ежедневный слот 19:00; флаг свободного места `C:` 10.5 GiB; нужны provider-подтверждения по каждому дню |
| 790 | Milovi Cake Instagram | **BLOCKED** | daily writer 19:00, `LastTaskResult=0` | прод-рантайм владельца на коммите `488e5380` (**305 коммитов позади main**); OIL `1363008` не объяснён |
| 789 | Legendary Poet Instagram | **BLOCKED** | HTTPS transport проверен (200, `video/mp4`, SHA); 2 Reel опубликованы | `container_unknown` при create; повтор запрещён без reconciliation; 62-Shorts очередь (2 published, 6 held, 54 inert) |
| 795 | Lord God YouTube | **ACTIVE** | 115 distinct edited; гарды #1041–#1053 в `main` | 1120 shelf-dirty, 8769 старых shelf URL, 1011 legacy appeals; owner-API чтения упираются в лимит Desktop Commander |
| 903 | Legendary Poet i18n | **BLOCKED** | 177/1780 locale-слотов, pilot подтверждён; screencast для Google доставлен | 1603 слота на 177 видео; квота YouTube API не восстановлена |
| 774 | Legendary Poet YouTube→VK | **BLOCKED** | 149/164 public + 15 scheduled (08.11) | VK code 9 / карантин credential; нельзя повторять `RuTmtXUuxm8` (`-235216998_456239224`) |
| 662 | VK code 9 | **BLOCKED** | карантин `legendary-poet`/`default` задокументирован; method circuits | нужен OAuth владельца для собственного app `54555649`; тишина 6/64/24 ч не помогла |
| 810 | LordChrist Shorts | **BLOCKED** | оба ledger **0/4 + 0/4**, `pending/impossible` | cron создавал запуски на 3–8 ч позже окна; нужны новые даты + provider-verified canary |
| 1036 | Legendary Poet MP3 | **WAITING** | `sendAudio` payload, MP3 SHA, caption, binding shared-bot подтверждены | нет доказанного отсутствия дубля в истории канала; нужен owner-approved one-shot |
| 940 | SHORTOREZ | **WAITING** | 6 статических 9:16 рендеров, 24 шота/21 crop, QA 6/6 | решение владельца по вариантам; публикации нет |
| 930 | Piper-MacArthur V25H | **HOLD** | 22 cut, master 53:20, QA, V25K YouTube 5/5 verified | master HOLD: L07/L11/L12; права не подтверждены; VK заблокирован code 9 |
| 782 | Атрибуция Лермонтова | **WAITING** | 4/4 title/description проверены read-only (06.11) | решение по top-level comment |
| 778 | Атрибуция «Скифов» | **WAITING** | caption исправлен, media ID и permalink сверены | остался неверный хэштег `#АлександрПушкин` → `#АлександрБлок` |

Суммарно: **2 ACTIVE, 3 HOLD, 9 BLOCKED, 4 WAITING**. Ни одна из 18 задач не является «забытой» — все имеют свежий комментарий или активный workflow, но 12 из 18 упираются во внешний фактор.

## 7. Приоритизированные находки

### P0 — ломает регулярную доставку

**F1. GitHub Actions не доставляет слоты.** Charnock: scheduled-запуски 10, 13, 17, 20 ноября падали на шаге «Select exact calendar slot…»; запуски создавались в 16:51–19:06 UTC при слотах 09:00–10:11 UTC — задержка 7–10 часов. Milovi: запуски 20:35–00:08 UTC при слоте 16:00 UTC; 18 публикаций не вышли. Код корректно fail-closed; проблема в транспорте расписания. **Следствие:** 4 будущих слота Charnock (24.11, 27.11, 01.12, 04.12) и последний слот Milovi (22.11) под тем же риском.

**F2. Редакционное ревью стало узким горлом.** 18 карточек quote-v6, 8 вопросов quiz, 2 PR, Charnock #13 — всё ждёт человека с мандатом. За неделю (15–21.11) слито 100+ PR, но ни один редакционный HOLD не снят. **Следствие:** канал цитат молчит с 19.11, quiz — с 17.11.

### P1 — искажает решения

**F3. Документация состояния устарела.** `current-state.md` (последняя правка 18.11) закреплён на `c308448d` — 574 коммита назад; счётчики quote-v6 в нём 7/30 против фактических 12/30. `README.md` заявляет 796 тестов и 14 306 statements против 4800 и 56 347. `roadmap.md` от 05.08 описывает закрытую программу Waves 0–13. Агент, читающий эти файлы, примет неверные решения.

**F4. Реестры качества не поспевают за кодом.** `cli/youtube.py`: floor 10.98 % при факте 75.51 %. 24 из 28 module dispositions — `pending_owner_decision` с замера 04.11. Ratchet работает, но перестал отражать реальный уровень.

**F5. Прод-рантайм владельца отстал от репозитория.** По #790 (18.11), scheduled task Milovi IG запускает `video-manager.exe` из checkout на `488e5380` (06.11) — **305 коммитов** позади `main`. Все исправления после 06.11 в этом канале не действуют.

**F6. VK-карантин держит четыре направления.** #662, #774, #792, #930 и музыкальная часть #869 зависят от одного внешнего шага — OAuth владельца для собственного приложения. Ретраи и «тихие окна» доказанно не помогают.

### P2 — гигиена и стоимость

**F7. Ветки: 5 кандидатов на удаление, 1 на спасение.** Ни одна орфанная ветка не содержит уникального кода; уникальны только бинарные иллюстрации. `fix/wave6-…` содержит реальный guard и должна быть влита.

**F8. Issue-гигиена отсутствует.** 0 labels на 18 issues при 14 доступных labels, 0 milestones, тела 32–36 KB (#869, #792), 100 комментариев (#795). Нет ни одного машинно-читаемого признака «кто блокирует» и «что дальше».

**F9. Репозиторий тяжёлый.** `.git` 310 MB при `content` 66 MB; медиа-доказательства живут в git-refs; LFS не используется. Каждый полный клон/архив несёт исторические бинарники.

## 8. План

### 24 часа

1. **PR #1051:** отформатировать один тестовый файл, push, exact-head CI, затем — ревью (не self-review).
2. **PR #1049:** обновить ветку от `main`, перезапустить CI, назначить независимого ревьюера.
3. **Milovi #809:** официально признать слоты 08–20.11 истёкшими в ledger-терминах; при желании владельца — новый календарь с 22.11 и новыми identity; не переотправлять.
4. **Charnock #997:** решить судьбу #06–#08 (новые даты или закрытие как missed), проверить готовность #10 к 24.11 12:00 MSK.
5. **State-sync PR:** обновить `current-state.md` (checkpoint, счётчики 12/18 и 2/8, Charnock #09), README-цифры, дату `roadmap.md`.

### 7 дней

6. Спасти `fix/wave6-retired-import-dispatch-20261118`: rebase, PR, exact-head CI, merge.
7. Удалить 5 class-3 refs (2 × 1619 immediately; 3 орфана — после решения по иллюстрациям и research-документу), записав tips и причину в branch-hygiene ledger.
8. Ввести labels (`lane/*`, `blocked/*`, `editorial-hold`, `owner-action`, `p2`) и 3 сохранённых view; назначить владельца каждой из 12 блокированных задач.
9. Закрыть 24 `pending_owner_decision`: для каждого — reachable / archive / delete; поднять coverage floors (`cli/youtube.py` → 75.5, total → 76.7).

### 30 дней

10. **Убрать зависимость критичных слотов от GitHub cron:** Windows Task Scheduler (уже используется для IG) или допуск «slot + N минут» с автоматическим re-issue и явной терминальной записью missed.
11. **Freshness-gate для операционной памяти:** тест, который падает, если `current-state.md` отстаёт от `main` больше чем на N коммитов/дней.
12. **Медиа вне git:** LFS или content-addressed Release/Pages с сохранением ref-binding контракта; зафиксировать политику в `protected-evidence-refs.json`.
13. **Процесс независимого ревью:** named reviewer, чек-лист (source span, права, читательский смысл), SLA 48 ч; без него HOLD не снимается.

## 9. Приложение

### Команды, воспроизводящие инженерные числа

```bash
python -m venv /tmp/vcm-venv && /tmp/vcm-venv/bin/pip install -e ".[dev]"
/tmp/vcm-venv/bin/python -m pytest -o addopts="" -q --tb=no
/tmp/vcm-venv/bin/python -m pytest -o addopts="" -q --cov=video_channel_manager \
  --cov-report=json:coverage.json
/tmp/vcm-venv/bin/ruff check .
/tmp/vcm-venv/bin/ruff format --check .
/tmp/vcm-venv/bin/mypy src --show-error-codes
```

### Read-only чтение ledger

```bash
git show origin/state/lordchrist-telegram:content/telegram/lordchrist/quote-v6-publication-ledger.json
git show origin/state/lordchrist-telegram:content/telegram/lordchrist/quiz/lordchrist-quiz-series-03-ledger.json
git show origin/state/milovi-cake-telegram:content/telegram/milovi-cake/feed/index.json
```

### Границы

Этот документ — свидетельство на 2026-11-21. Он не разрешает provider mutation, не переопределяет `current-state.md`, не отменяет HOLD и не заменяет owning issue. Любая публикация требует нового явного запроса, свежего bounded preflight, ревью и отдельной авторизации.
