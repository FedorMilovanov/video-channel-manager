# MASTER AUDIT MARATHON V2

**Проект:** `FedorMilovanov/video-channel-manager` и связанные операционные контуры  
**Срез:** 4 августа 2026 года  
**Фактический `main`:** `963955230e6fac269635337e8a2366fbfe54652d`  
**Кодовый merge Wave 7:** `df956bbbf19af6652f8711f95fb4fecf272e9951`  
**Активный инженерный фронт:** Wave 8 / issue `#86`  
**Владелец синхронизации аудита:** issue `#88`  
**Удалённые операции VK/YouTube в ходе этого аудита:** `0`

---

## 1. Главный вывод

Проект **не развален**. После Waves 0–7 у него уже есть сильное надёжное ядро:

- durable upload lifecycle и запрет слепого повтора;
- exact project/content identity;
- единый HTTP ownership, bounded safe-read retry и redaction;
- полное разделение upload и wall publication;
- один поддерживаемый PowerShell operator;
- versioned source → plan → apply → result → reconciliation engine;
- реестр 15 mutation boundaries;
- fault injection, corruption tests и replay barriers;
- exact-head CI на Python 3.11/3.12/3.13 и трёх PowerShell-средах.

Но утверждение **«осталась только issue #86 и после неё всё закончено»** слишком упрощает состояние.

Верная формулировка:

> **Wave 8 / #86 — единственный активный инженерный фронт ядра.**  
> Кроме него остаются: Audit A0 по синхронизации источников истины, Wave 9 с раздельным live-reconciliation обоих проектов, самостоятельный экспериментальный контур VK Audio и Wave 10 по архивированию/production governance.

Самая опасная новая находка — не очередной API-баг, а **расхождение документов высокого приоритета**. `current-state.md`, backlog и issue #64 уже говорят «Waves 0–7 завершены, Wave 8 активна», а корневой `AGENTS.md`, operations index и старый master audit всё ещё направляют следующего агента к Wave 1/4 и называют давно исправленные дефекты открытыми. Такой drift способен запустить повтор закрытой работы, создать новый несовместимый executor или ошибочно разблокировать старый пакет.

---

## 2. Что было изучено

### 2.1. Переданные материалы

Всего обработано **6 531 строк** пользовательских материалов:

| Файл | Строк | SHA-256 |
|---|---:|---|
| `Вставленный текст(275).txt` | 474 | `a59baae832b96e4e961b88e68706fc642b51a06223c18bfd22d0a63056037cb0` |
| `Вставленный текст (2)(10).txt` | 1 183 | `6b11c7f58f6b492febe5be28f2e1dcf6c626545ab0ed0791cf5166c1f062a752` |
| `Вставленный текст (3)(1).txt` | 2 209 | `1f433a7f54b1f3c3f37e3861108af5b9f845635ca4aaa448132733150a4ef3de` |
| `Вставленных __уценки (2).md` | 245 | `4e5f5d1e547d707534c495f6fb5f0942b283c48da59fcba6e6e2808dd94b3630` |
| `Вставленный текст (4).txt` | 1 171 | `379b624e8743fb3d940ccc939f1f650bfd8967891dbc4869c1df1c6d56b878e0` |
| `Вставленный текст (5)(1).txt` | 1 249 | `8852e93a8d7e2e9513c1bc0271e8c32b4cd0339c18f1150a92c78456a8dc82c8` |

Материалы включали:

- переписки нескольких агентов;
- старый master audit и audit-register;
- 20+ проходов аудита кода;
- отчёты Waves 0–7;
- логи CI;
- историю Legendary Poet Shorts/Clips;
- историю Lord God VK Audio;
- PowerShell-логи, browser canary, metadata/playlist attempts;
- пользовательские требования к exact identity, no blind retry, canary, wall safety и ручному решению по старым дублям.

### 2.2. Проверенный GitHub

Проверены:

- фактический `main`;
- issue #64, #79, #80, #86 и связанные live issues;
- PR #83, #84, #85, #87;
- `AGENTS.md`;
- `docs/operations/current-state.md`;
- `docs/operations/automation-backlog.md`;
- `docs/operations/README.md`;
- исходный `master-audit-2026-08-04.md`;
- `audit-register-2026-08-04.json`;
- `.github/workflows/ci.yml`;
- `application/cross_platform.py`;
- `scripts/sync_youtube_to_vk.py`;
- `platforms/vk/thumbnails.py`;
- архивные lessons/evidence из draft PR #85;
- exact-head workflow runs и job logs.

### 2.3. Иерархия доверия

При противоречиях использовался порядок:

1. текущий код `main`;
2. exact-head CI текущего merge;
3. фактический provider postflight / exact local ledger;
4. merged PR с точным scope;
5. актуальный `current-state.md` и issue #64;
6. свежий подписанный аудит;
7. старый аудит;
8. чат, скриншот, remembered count, гипотеза агента.

Число, название ZIP или сообщение «готово» не считается proof без machine-readable result/postflight.

---

## 3. Фактическое состояние репозитория

### 3.1. Waves 0–7 закрыты

| Wave | Состояние | Основной результат | Provider writes в разработке/CI |
|---|---|---|---:|
| 0 | завершена | canonical state, project boundary, issue ownership | 0 |
| 1 | завершена | journaled upload state machine, exact-ID recovery | 0 |
| 2 | завершена | fail-closed project/content pipeline | 0 |
| 3 | завершена | HTTP ownership, safe-read retries, limiter, redaction | 0 |
| 4 | завершена | upload ≠ wall, complete wall evidence | 0 |
| 5 | завершена | один supported PowerShell operator | 0 |
| 6 | завершена | versioned wave engine, atomic evidence, no replay | 0 |
| 7 | завершена | 15 mutation boundaries, fault/corruption/operator proofs | 0 |

Финальная Wave 7:

- PR #84;
- merge `df956bbbf19af6652f8711f95fb4fecf272e9951`;
- CI `30918639372`;
- `657 passed, 1 xfailed` на Python 3.11/3.12/3.13;
- Pester `25/25` в Windows PowerShell 5.1, PowerShell 7 Windows и PowerShell 7 Linux.

Living-state sync:

- PR #87;
- merge `963955230e6fac269635337e8a2366fbfe54652d`;
- CI `30920947841` — зелёный.

### 3.2. Wave 8 действительно активна

Issue #86 правильно владеет:

- exact-first matching;
- canonical text/URL identity;
- exact catalog/album identity;
- authoritative media/cache evidence;
- structured ffprobe validation;
- exact thumbnail postcondition.

Wave 8 не разрешает live VK/YouTube writes.

### 3.3. Live-очереди не закрыты архитектурным CI

#### Legendary Poet

Актуальная матрица:

- YouTube Shorts: **56**;
- exact pairs: **41**;
- missing: **15**;
- ambiguous: **0**.

Это отменяет старую формулировку «48 роликов». Доказанного завершённого V3 Apply в GitHub нет. Следовательно, состояние — `requires_reconciliation`, а не `completed`.

#### Lord God Strength

Часть machine evidence остаётся локально. Пока exact ledger/result не reconciled с live provider state, нельзя:

- считать очередь завершённой;
- повторять accepted/processing/unknown;
- строить новый transfer boundary по памяти.

#### VK Audio

Это соседняя экспериментальная система. Она доказала отдельные факты, но не production-completion:

- один MP3 canary был успешно загружен и найден;
- playlist/metadata automation неоднократно ошибалась в UI identity;
- были false `already_correct`, hangs и observer misses;
- read-only internal web request был доказан;
- 10 playlist positions были сведены к 8 unique tracks;
- batch runs имели pre-write crash и partial/deferred state;
- наблюдалась разница upload hosts `vk.ru` и `pu.vk.ru`.

Нельзя сводить это к «ничего не работает» или «всё готово». Корректный статус: **частично доказанная экспериментальная интеграция с неизвестными/отложенными item outcomes**.

---

## 4. Матрица находок V2

| ID | Приоритет | Статус | Волна | Находка |
|---|---|---|---|---|
| `TRUTH-001` | P0 | confirmed | Audit-A0 | Расхождение источников истины |
| `ADMIN-001` | P1 | fixed_during_audit | Audit-A0 | Параллельные владельцы завершённой Wave 7 |
| `ARCHIVE-001` | P1 | confirmed | Audit-A0 | CI не различает production-код и буквальный исторический код в Markdown |
| `MATCH-001` | P0 | confirmed | Wave-8A | Нет отдельной exact-first фазы сопоставления |
| `MATCH-002` | P0 | confirmed | Wave-8A | Неоднозначная пара может быть выбрана как match |
| `MATCH-003` | P1 | confirmed | Wave-8A | Полное O(N×M) fuzzy-сопоставление остаётся дорогим |
| `IDENTITY-001` | P1 | confirmed | Wave-8B | Один агрессивный normalize_title применяется к разным задачам |
| `ALBUM-001` | P0 | confirmed | Wave-8C | Дубликаты нормализованных названий альбомов молча перезаписываются |
| `CATALOG-001` | P0 | confirmed | Wave-8C | Album placement зависит от title-key, а не утверждённой identity |
| `MEDIA-001` | P0 | confirmed | Wave-8D | Кэш принимает MP4 без authority и integrity evidence |
| `MEDIA-002` | P0 | confirmed | Wave-8D | Fallback после yt-dlp может выбрать неавторитетный glob-result |
| `MEDIA-003` | P1 | confirmed | Wave-8D | MP4 remux не доказывает кодек/профиль |
| `THUMB-001` | P1 | confirmed | Wave-8E | Сохранение thumbnail не доказывает выбранную обложку видео |
| `LIVE-POET-001` | P0 | requires_reconciliation | Wave-9B | Legendary Poet Shorts/Clips не завершены как live-очередь |
| `LIVE-LORD-001` | P0 | requires_reconciliation | Wave-9A | Lord God long-form queue требует локального reconciliation |
| `AUDIO-001` | P1 | separate_system | Wave-9D-separate | VK Audio — отдельная экспериментальная система |
| `GOV-001` | P2 | confirmed | Wave-10 | Архив, supported code и operational state требуют разных правил |

---

## 5. Новые пропущенные дефекты

### 5.1. P0 — source-of-truth drift

**Что обнаружено**

- `AGENTS.md` говорит, что следующий этап — issue #65 / Wave 1.
- `docs/operations/README.md` говорит, что активна issue #36 / Wave 4.
- старый master audit основан на `main@b19d4faa...`;
- machine register не отражает фактический state-sync head `963955...`.

**Почему это P0**

`AGENTS.md` является обязательной инструкцией для будущего агента. Ошибка там способна вернуть в работу закрытые executors и повторно активировать исправленные P0.

**Правильное исправление**

Не удалять старую историю. Новый audit v2 становится актуальным указателем; старый audit маркируется историческим baseline. Все входные документы должны говорить:

- Waves 0–7 completed;
- Audit A0 / issue #88 — синхронизация;
- Wave 8 / #86 — единственный активный core-engineering owner;
- live writes запрещены;
- Wave 9 и Wave 10 идут позже.

### 5.2. P0 — matcher не exact-first

Текущий `compare_audit_packages()`:

1. строит декартово произведение source×target;
2. вычисляет fuzzy score;
3. сортирует кандидаты;
4. greedily занимает source/target;
5. только после выбора ставит `ambiguous=True`.

Это не соответствует требованию «exact identity прежде fuzzy». Кроме риска неверной пары, это O(N×M) с дорогим `SequenceMatcher`.

**Новый контракт**

1. exact stable ID / reviewed mapping;
2. exact canonical title + exact duration policy;
3. exact marker/source URL;
4. только затем bounded fallback;
5. ambiguous/conflict не создаёт mapping;
6. deterministic global assignment доказывается permutation tests.

### 5.3. P0 — duplicate normalized album names silently overwrite

Два места строят dict по `normalize_title(title)`. Если два альбома после нормализации одинаковы, последний объект молча побеждает. Это может направить `add_to_album` не в тот target.

**Обязательное поведение**

- zero candidates → missing;
- one exact reviewed target → selected;
- two+ targets → conflict;
- renamed target → reviewed remap;
- никакой выбор по dict overwrite.

### 5.4. P0 — media cache не является authoritative

Существующий MP4 принимается по маске имени и существованию файла. Не доказаны:

- source ID binding;
- точный путь;
- SHA-256;
- размер;
- streams/codecs;
- playability;
- duration;
- отсутствие partial/stale file.

После yt-dlp код сначала читает `after_move:filepath`, но при проблеме возвращается к glob и берёт последний результат. Это восстанавливает именно тот класс ошибок, который Wave 8 должна убрать.

### 5.5. P1 — remux не равен codec contract

`--remux-video mp4` гарантирует контейнер, но не H.264/AAC. MP4 может содержать VP9/AV1/Opus. Нужно либо:

- формально разрешить набор потоков и проверять его;
- либо отдельно транскодировать в утверждённый профиль.

Нельзя молча называть remux «подготовленным совместимым MP4».

### 5.6. P1 — thumbnail success не равен selected-thumbnail postcondition

Низкоуровневый writer хорошо проверяет upload/save response, но caller не доказывает, что именно эта картинка стала выбранной обложкой видео после eventual consistency.

Нужны:

- local image SHA/dimensions/quality;
- returned photo identity;
- observed selected image identity;
- delayed polling;
- conflict/timeout → reconciliation, не blind retry.

### 5.7. P1 — operational archive конфликтует с production formatter

Draft PR #85 полезен и не должен быть потерян. Его CI показывает:

- тесты зелёные;
- типизация зелёная;
- PowerShell зелёный;
- падение только потому, что Ruff форматирует исторический Python внутри Markdown.

Неправильные решения:

- форматировать forensic snapshots;
- выключить Ruff глобально;
- смержить красный PR;
- закрыть архив как «ненужный».

Правильное решение:

- отделить literal source evidence от executable/source-format scope;
- сохранить SHA;
- проверять архив отдельным history validator;
- не позволять archived code становиться entrypoint.

---

## 6. Что уже исправлено и запрещено возрождать

Следующие старые находки не должны снова превращаться в active work:

- позднее журналирование upload reservation — закрыто Wave 1;
- принятие incomplete visible object как reusable — закрыто Wave 1;
- слабый upload readiness — закрыто Wave 1;
- неполная per-record validation — закрыто Wave 2;
- исполняемый cross-project base sync — закрыто Wave 2;
- отсутствие bounded safe-read retry — закрыто Wave 3;
- per-request HTTP clients в supported paths — закрыто Wave 3;
- upload и wall как одна операция — закрыто Wave 4;
- старые PowerShell write wrappers — retired Wave 5;
- поколения V1/V2/V3/current как supported engine — закрыто Wave 6;
- отсутствие mutation-boundary fault proofs — закрыто Wave 7.

Также запрещено внедрять как факт:

- несуществующий публичный VK chunk/resume protocol;
- утверждение, что YouTube system Uploads автоматически создаёт VK album;
- старое число 48 как актуальную очередь;
- вертикальный формат или длительность как доказательство `short_video`;
- `guid` как полную wall idempotency;
- browser selector как стабильный provider API;
- «missing сейчас» как разрешение повторной загрузки.

---

## 7. Разрешение главных противоречий из переписок

| Противоречие | Итог |
|---|---|
| «В Господь Бог Shorts сделали клипами» vs «сделали обычными видео» | Было несколько этапов. Нельзя использовать проект как единый прецедент без exact object/result evidence. |
| «Все 48 надо загрузить» vs «56/41/15» | 48 — исторический пакет. Актуальная read-only матрица — 56/41/15/0, но требует нового reconciliation перед apply. |
| «video.save сам создаст Clip» vs «нужна форма Добавить клип» | Provider behavior недостаточно доказан как стабильный контракт. Требуется final surface/type postflight; способ dispatch является adapter detail. |
| «VK Audio через API» vs «через браузер» | Использовался hybrid: browser session/cookies + internal web HTTP, а иногда UI. Это не официальный token API и не стабильное core API. |
| «Осталась только #86» | Только в смысле active core architecture. Audit A0, live Wave 9, archive PR #85 и Wave 10 всё ещё существуют. |
| «CI зелёный — можно запускать очередь» | Нет. CI доказывает contracts, а не live provider state. |
| «Плейлист/metadata этап упал — upload неуспешен» | Неверно. Item stages независимы; verified upload нельзя повторять из-за позднего stage failure. |

---

## 8. Новый марафон волн

### Audit Wave A0 — синхронизация истины

**Владелец:** issue #88  
**Provider writes:** 0

#### Scope

- новый master audit v2;
- обновление `AGENTS.md`;
- обновление operations index;
- указание, что старый master audit — historical baseline;
- обновление machine register baseline/new findings;
- закрытие duplicate Wave 7 issue/PR;
- решение CI boundary для PR #85;
- никаких изменений matching/media/provider executors.

#### Definition of Done

- все authoritative entrypoints показывают `WAVE_7_COMPLETED_WAVE_8_ACTIVE`;
- issue #86 остаётся единственным владельцем Wave 8;
- старые Waves 0–7 нельзя случайно повторить;
- exact-head CI зелёный;
- provider writes 0.

### Wave 8A — exact-first matching kernel

**Цель:** заменить fuzzy-first greedy assignment.

#### Реализация

- versioned match evidence model;
- exact candidate indexes;
- explicit `matched`, `missing`, `conflict`, `ambiguous`, `rejected`;
- no mapping from ambiguous;
- deterministic assignment independent of input order;
- performance indexes and bounded fallback.

#### Тесты

- duplicate exact titles;
- same duration/different media;
- reordered source/target;
- equal-score candidates;
- cross-project markers;
- large inventory benchmark;
- property/permutation tests.

#### Exit

Ни одна ambiguous pair не попадает в catalog mapping или live plan.

### Wave 8B — canonical text and URL identity

Раздельные canonicalizers:

- identity title;
- display title;
- description comparison;
- public URL;
- collection title;
- version/variation token.

Каждый результат сохраняет original, normalized, ruleset version, transformations и evidence/digest.

**Exit:** нормализация не может склеить разные проекты, версии, admin/public routes или разные коллекции без conflict.

### Wave 8C — catalog/album identity

- immutable reviewed source collection ID → target album ID;
- exact current target title/evidence;
- duplicate/renamed album conflict;
- semantic set membership;
- provider position ignored;
- no title-key authority.

**Exit:** ни одна album mutation не строится только по normalized title.

### Wave 8D — media/cache authority

- authoritative yt-dlp final path only;
- no glob fallback as success;
- cache manifest;
- SHA-256 и size;
- ffprobe JSON;
- duration/stream/container/codec policy;
- partial/corrupt/audio-only/multi-file rejection;
- source URL/ID и downloader-policy digest.

**Exit:** файл без complete structured evidence не может перейти в `media_verified`.

### Wave 8E — thumbnail identity and postcondition

- local image QC + SHA;
- remote photo result identity;
- selected-thumbnail postflight;
- delayed consistency;
- unknown result → reconciliation.

**Exit:** HTTP success без observed selected image не даёт `verified`.

### Wave 8F — integration proof and state sync

- объединить 8A–8E в supported planning path;
- migration/rejection tests для старых evidence;
- exact-head CI;
- обновить current-state/register/backlog/changelog/#64/#86;
- provider writes 0.

**Exit:** Wave 8 закрыта только после полного state sync.

### Wave 9A — Lord God live reconciliation

**Владелец:** issue #31

1. собрать exact local ledger/result inventory;
2. read-only live snapshot;
3. classify every item;
4. accepted/processing/unknown не повторять;
5. создать immutable manifest только для proof-backed missing;
6. one canary;
7. postflight;
8. отдельный result.

### Wave 9B — Legendary Poet Shorts/Clips reconciliation

**Владельцы:** issues #32/#38

1. fresh YouTube Shorts snapshot;
2. fresh VK video/clip inventory;
3. exact type/surface evidence;
4. reconcile existing ledgers/packages;
5. новая matrix без hard-coded count;
6. old ordinary VK Videos не удалять автоматически;
7. один native canary;
8. success только при доказанном user-required surface/type;
9. batch по immutable queue.

### Wave 9C — catalog/publication

**Владелец:** issue #33  
**Зависит от:** 9A/9B и Wave 8.

Album/catalog/publication plans строятся только из exact mapping evidence. Upload и wall остаются отдельными manifests.

### Wave 9D — VK Audio incubation, отдельно

Это не продолжение #86 и не часть обычного YouTube→VK Video engine.

Перед новым batch:

- отдельный project/repository boundary;
- versioned audio source/plan/result schemas;
- exact per-item stages;
- browser-session acquisition как adapter;
- internal web endpoints как unstable provider contract;
- allowlisted upload ticket host/path;
- exact artist/title fields;
- playlist identity;
- bounded heartbeat/deadline;
- partial result + reconciliation;
- canary;
- no newest-ZIP selection;
- no script generation cascade.

До выполнения этих условий старые v1.x/v2.x/v3.x пакеты — исторические артефакты, не supported entrypoints.

### Wave 10 — retirement and governance

- archive supported/compatibility/retired registry;
- merge/rebase/close PR #85 после history CI fix;
- удалить или quarantine stale pointers;
- release checklist;
- rollback/reconciliation runbook;
- provider-contract review cadence;
- audit expiry rules;
- machine register schema v2;
- coverage policy для supported scripts;
- historical evidence retention.

---

## 9. Немедленная последовательность PR

1. **Audit A0 PR** — master audit v2, pointers, register/state truth и administrative cleanup.
2. **Wave 8A PR** — matching models/indexes/assignment/tests.
3. **Wave 8B PR** — canonical identity and URLs.
4. **Wave 8C PR** — catalog/album reviewed mapping.
5. **Wave 8D PR** — media authority/cache/ffprobe.
6. **Wave 8E PR** — thumbnail postflight.
7. **Wave 8F state-sync PR** — полный integration proof и living-state.
8. Только затем Wave 9 live reconciliation.

Каждый PR:

- один issue owner;
- один exact head;
- zero unrelated writes;
- no temporary workflow tricks;
- exact-head CI;
- state update;
- no provider mutation as side effect of refactor.

---

## 10. Permanent rules из операционной истории

1. Stage success хранится поэтапно, не одним Boolean.
2. Поздний stage failure не отменяет подтверждённый ранний mutation.
3. `already_correct` требует exact per-field readback.
4. Global search и domain-specific search — разные UI targets.
5. Browser-opened не означает observer-attached.
6. PowerShell pipeline output всегда нормализуется для 0/1/N.
7. URL-shaped value не является upload authority.
8. Неизвестный provider outcome не retryable.
9. Fresh snapshot не исправляет плохой matcher.
10. Duration — evidence, не identity.
11. Vertical media — geometry, не Clip identity.
12. Historical script не становится supported после копирования.
13. Новый ZIP version не заменяет root-cause fix.
14. Отсутствие объекта в неполном endpoint не доказывает absence.
15. Counts — report output, не immutable contract.

---

## 11. GitHub administrative actions, выполненные во время аудита

- PR #83 закрыт без merge как superseded PR #84/#87.
- Issue #79 закрыта как duplicate завершённой issue #80.
- Создан issue #88 — владелец Audit Marathon V2.
- PR #85 сохранён открытым draft: его evidence полезно; требуется отдельное исправление archive/CI boundary.
- Никаких VK/YouTube writes не выполнялось.

---

## 12. Итоговый статус

```text
Waves 0–7                       COMPLETED
Audit Wave A0 / issue #88       ACTIVE
Wave 8 / issue #86              ACTIVE CORE ENGINEERING
Wave 9 live queues              BLOCKED BY WAVE 8 + RECONCILIATION
VK Audio incubation             SEPARATE / PARTIAL / NOT CORE-SUPPORTED
Wave 10 governance              LATER
Provider writes in this audit   0
```

### Разрешённое следующее действие

Закрыть Audit A0 exact-head PR, затем продолжить **Wave 8A**.  
Не запускать старые Shorts/Audio ZIP, не повторять unknown uploads, не удалять старые VK Video copies и не начинать catalog/wall operations до соответствующей Wave 9.

---

## Appendix A — authoritative baseline

- Repository: `FedorMilovanov/video-channel-manager`
- Main: `963955230e6fac269635337e8a2366fbfe54652d`
- Wave 7 code: `df956bbbf19af6652f8711f95fb4fecf272e9951`
- Wave 7 CI: `30918639372`
- State-sync CI: `30920947841`
- Active core issue: `#86`
- Audit synchronization issue: `#88`
- Historical archive draft: PR `#85`

## Appendix B — report limitations

Этот аудит не включает свежий live VK/YouTube scan и не делает выводов о текущем удалённом состоянии сверх уже сохранённого evidence. Это намеренно: задача — архитектурный и операционный аудит, а не новая provider mutation/reconciliation сессия.

Все live counts должны быть обновлены в Wave 9 read-only preflight непосредственно перед созданием нового immutable manifest.
