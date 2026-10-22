# @lordchrist content contract

Эта папка разделяет **verified source evidence** и **Telegram presentation**.

## Agent start here

Если агенту дали только ссылку на репозиторий и задачу по `@lordchrist` / «Господь Бог — Сила Моя», сначала открыть:

1. `AGENTS.md` — локальный read order и приоритет правил;
2. `RICH_EDITORIAL_STANDARD.md` — канонический стандарт больших богословских/исторических постов;
3. `QUOTE_ATTRIBUTION_STANDARD.md` — цитаты, подписи и точное правило воздуха перед цитатами;
4. `DIRECT_COPY_TO_TELEGRAM.md` — ручная rich-copy вставка на Android и `U+2060` spacing (lane L1);
5. `RICH_EDITOR_ARTICLE_STANDARD.md` — длинные статьи в редакторе «Статья» (lane L2, до 32 768): заголовки, списки, цитаты, воздух;
6. `MANUAL_RICH_COPY.md` — диагностика потери форматирования и `tools/telegram-rich-copy/index.html` для ручной rich-copy;
7. только затем task-specific research/evidence.

## Quote-v5 — текущий ридерский формат постов-цитат (2026-10-17)

Редакционная переработка по прямому запросу читателя: **маленькие посты-цитаты открываются самой цитатой, без обязательного заголовка**. Формат карточки:

```text
<blockquote>Цитата — большая, средняя или маленькая</blockquote>
— Автор, труд, год            ← tight, одной строкой под цитатой

Качественное разъяснение.      ← обычный абзацный воздух

#Хэштеги
```

Заголовков нет ни у одной карточки: политика `lordchrist-quote-v5` задаёт `title_mode=none`, а depth-v3 restore переписал проблемные открытия (32 и 36) на полные самодостаточные цитаты. `title_resolved_anaphora` моделью v2 запрещён, поэтому заголовок больше не компенсирует обрывок. Историческая карточка 17 вышла под quote-v4 с заголовком и остаётся неизменяемой историей. Если заголовок всё же появится, после него обязателен **настоящий абзацный воздух** (пустая строка) перед цитатой:

```text
Жирный заголовок

<blockquote>Цитата</blockquote>
— Автор, труд, год
…
```

Действующие артефакты v5:

```text
presentation-policy-v5.json                     — policy digest sha256:1baa56fe…307c1f6; title_mode=reviewed_load_bearing_only
successor-depth-presentation-migration-v2.json  — immutable граница v4→v5: 16 published / 44 pending
successor-depth-runtime-activation-v5.json      — schema v3, verified_prefix, exact history hash 1–16
.github/workflows/lordchrist-quote-v4-preflight.yml — read-only preflight (проверяет rolling v5 checkpoint)
```

№16 (`lordchrist-successor-depth-v2-16-spurgeon-sovereignty-comfort`, сообщение 1566 от 2026-10-16) — единственный пост, вышедший в старом формате v4 с заголовком впритык; он остаётся immutable history со своим durable v4-rendered evidence. С №17 очередь публикуется в формате v5. Длины цитат в суффиксе 17–60 варьируются естественно: 18 коротких афоризмов (<150 символов), 26 средних; длина не является критерием качества, короткий полный афоризм допустим.

Слоты расписания теперь реально совпадают с документируемым московским временем: утренний cron `17 6 * * *` (06:17 UTC = 09:17 МСК, ежедневно), полуденный `0 9 * * 2,5` (09:00 UTC = 12:00 МСК, вт/пт), вечерний `17 18 * * 2,5,0` (18:17 UTC = 21:17 МСК, вт/пт/вс), исторический `17 16 * * 1,3,6` (16:17 UTC = 19:17 МСК, пн/ср/сб). Полуденный слот — не третий час для цитат: он закреплён за lane `rich_article` (длинные статьи L2, серия по Чарноку) в `telegram_schedule.SLOT_LANES`, и запуск цитатной линии на нём отвергается, а не тратит его на карточку. Сами статьи выходят вручную из страницы копирования, поэтому бот этот слот не потребляет. Прежние выражения `17 9`/`17 21`/`17 19` срабатывали на три часа позже заявленных слотов: утренний выживал только за счёт lease 720 минут (фактическая публикация ~12:17–14:30 МСК), вечерний и исторический не публиковались никогда. Подробности — в `docs/audits/2026-10-17-lordchrist-quote-v5-rework-and-queue-audit.md`.

## Quote-v4 — непрерывная публикация reviewed-очереди (#692, история)

Релиз depth-v2 (`successor-depth-runtime-activation-v4.json`, schema v2) связывает начальную границу **15 published / 45 pending**, exact hash всей принятой истории 1–15 и политику `verified_prefix`. Это граница миграции, а не требование навсегда оставаться на 15 постах. После каждой verified-публикации допускается только непрерывный рост prefix; для каждого нового поста обязательны durable reviewed v4 `dispatches/<run>-<attempt>/rendered.json`, точный target и pristine remaining suffix. Неоднозначные outcomes, пробел в порядке или изменённая история блокируют продолжение. Доказательства reviewed-слоя:

```text
quote-standalone-review-v1.json      — 45 reviewed карточек 16..60: opening class, title-context resolution, пометки ревьюера
quote-source-web-audit-v2.json       — 99 reviewed страниц источников + 3 reviewed canonical equivalents
quote-source-live-probe-v2.json      — классификация retrieval по каждой странице (никогда не «источник мёртв»)
quote-depth-audit-v1.json            — semantic-key audit очереди
quote-depth-replacements-v1.json     — reviewed replacement-карточки (изменяют payload identity намеренно)
```

Правило карточки: reader-facing подпись — это **reviewed строка из карточки, verbatim**; рендер никогда не выводит её заново из evidence identity. Цитата и подпись образуют одну единицу чтения (`\n`), затем обычный абзацный воздух до редакционного текста. Короткие полные афоризмы допустимы; длина цитаты не является критерием качества.

Канонический read-only preflight — `.github/workflows/lordchrist-quote-v4-preflight.yml` (provider-inert). Он допустим как на выключенном, так и на reviewed-включённом расписании: `enabled` обязан совпадать с `provider_writes_authorized`, а policy digest — с activation checkpoint. Инертность доказывается отсутствием отправок/intent/outcome и неизменным state checkout, а не вечным запретом записи. Только main является production baseline.

### Canary для последовательности 16

Canary запускается **только** после явной provider-write авторизации и только на точном provider-inert SHA, где preflight зелёный:

```text
sequence 16 | lordchrist-successor-depth-v2-16-spurgeon-sovereignty-comfort
queue digest  sha256:c2ad28bb96e88a9e0633c4b7a55d6033bbf29c5a557e1aa4478cc2e0359e3441
policy        lordchrist-quote-v4 sha256:a87dd04d605a749c84ecd47d18c127dd921dddea500781c0fd75a0db20a7be9f
```

Ожидаемый результат: ровно один новый пост от `preaching_mp3_bot` (8716602202) в @lordchrist (-1001295216957); жирный заголовок, native blockquote, подпись `— Чарльз Сперджен, проповедь «Божественный суверенитет», 1856` непосредственно под цитатой без пустой строки, затем обычный абзац и хэштеги; durable ledger переходит в 15 опубликованных / 45 pending → 16 опубликованных / 44 pending ровно один раз, с `message_url`; дублей и backfill нет. Любое отклонение — fail closed: последовательность 17 не публикуется, инцидент фиксируется, состояние сверяется read-only с провайдером. После **успешного** canary verified receipt плюс точное durable v4-оформление разрешают №17 и далее без ручного переписывания checkpoint на каждом cron. Проверяется весь positional range 15..60; на 60 очередь корректно завершается, не запускается заново.

### Операционный контроль

Каждый запуск publisher пишет `GITHUB_STEP_SUMMARY` и `.runtime/lordchrist-publication-status.json`: `PUBLISHED` только при verified ответе и успешной durable-записи; `PAUSED`, `NO_SEND`, `BLOCKED`, `EXHAUSTED` не являются публикацией. При остатке ≤7 выдаётся предупреждение о reviewed successor. Корпус конечен: активация не разрешает генерировать или отправлять непроверенные новые цитаты автоматически. Дефект перевода №44 остаётся явно учтён в `quote-pending-content-findings-v1.json`; его исправляют новым reviewed release/rebind, не скрытой правкой sealed bytes.

**Research drafts не являются presentation authority.** Старый draft может хранить правильные факты и source anchors, но его типографику нельзя механически копировать, если она расходится с текущими стандартами.

## Источник — не финальный визуальный шаблон

`verified-30-posts.json` и `verified-30-posts.md` фиксируют проверенные source cards: перевод непрерывного фрагмента, автора, труд, location, source URL, anchors и historical source attribution. После первого verified canary source JSON и его digest остаются immutable.

Поэтому встречающийся в source card текст вида:

```text
© Автор, «Название труда»
```

не является текущим визуальным шаблоном Telegram.

## Историческая короткая quote-линия / source-v1 policy

Canonical policy:

```text
presentation-policy.json
policy_id = lordchrist-editorial-v2
```

Эта policy сохранена для исходной линии и source-v1 provenance. Текущий depth-v2 publisher использует `presentation-policy-v5.json`; нельзя откатывать его на source policy ради обхода gates. Immutable source cards не переписываются. `lordchrist-editorial-v2` выбирает для основного акцента самую содержательную прямую цитату, сохраняет спокойную типографику attribution и текущие spacing/link-preview правила.

Renderer реализован в:

```text
src/video_channel_manager/telegram_presentation.py
```

`preview` показывает одновременно immutable source payload и exact rendered provider payload. Source SHA и provider/presentation SHA намеренно являются разными доказательствами.

## Research / rich-линия — текущий редакционный стандарт

Большие исторические, сравнительные, биографические и объясняющие материалы **не должны** сводиться к растянутому quote-посту. Для них действует reader-first rich contract:

```text
RICH_EDITORIAL_STANDARD.md
QUOTE_ATTRIBUTION_STANDARD.md
```

Ключевые reader-facing правила: жирный заголовок ALL CAPS; нормальные многопредложные абзацы без лозунговой дроби; проверенные первичные цитаты; текст цитаты внутри quote entity, а автор/труд или ссылка на Писание — отдельной курсивной строкой ниже; русские названия трудов в публикации; воздух перед большинством цитат и только узкое исключение для короткой однострочной связки, которая семантически принадлежит следующей цитате.

Если полная качественная версия поста помещается в Telegram, **не сокращать её только ради компактности**. Убирать повторы и слабые формулировки, а не полезную экзегезу, доказательства или контекст. Telegram `sendMessage` допускает **1–4096 символов после разбора entities**; финальный preflight обязан считать точный вставляемый текст вместе с переводами строк и невидимыми `U+2060` spacing-символами. Каноническая ссылка на лимит: `https://core.telegram.org/bots/api#sendmessage`.

Для ручной публикации статьи, собранной интерактивно в ChatGPT на телефоне, действует отдельный transport preflight:

```text
DIRECT_COPY_TO_TELEGRAM.md
```

Канонический Android-путь: rendered ChatGPT text → Copy → Telegram composer → long-press → system **Paste / «Вставить»**. Вставка из clipboard/history панели клавиатуры запрещена для rich posts, потому что она может превратить содержимое в plain text. Обычные пустые строки при rich paste могут схлопываться, поэтому нужный paragraph air сохраняется отдельной невидимой строкой `U+2060 WORD JOINER` согласно runbook.

Для длинных материалов, которые не помещаются в одно сообщение, действует отдельный контракт **lane L2** — `RICH_EDITOR_ARTICLE_STANDARD.md`. Он описывает публикацию через редактор «Статья» (до 32 768 символов и 500 блоков): настоящие заголовки (эмодзи — обычный ведущий маркер раздела там, где раздел состоит из полноценных абзацев; не ставится в нумерованных пунктах `1. 2. 3.` и на коротких рубриках короче ~600 знаков; в заголовке статьи и в теле абзаца — никогда), воздух только перед заголовками, каждый пункт списка отдельным блоком, цитата в `>` с курсивной подписью `— …` строкой ниже, без хэштегов. Невидимые `U+2060` в L2 запрещены.

Текущий подготовленный successor corpus:

```text
research-queues/editorial-successor-v3.json
research-posts-v3/
```

Rich-материал строится как короткая Telegram-статья: сильный точный заголовок, короткий lead, 2–4 смысловых раздела, доказательная визуальная поддержка там, где она реально помогает, и спокойный итог. Для исторических материалов допустимы и предпочтительны несколько изображений, если каждое выполняет отдельную роль: портрет/источник/артефакт/архив/схема/сравнение. Изображения не добавляются ради декора.

Старая research-v2 provider release, однажды получившая unresolved provider outcome, остаётся retired/no-replay. Её нельзя оживлять blind retry. Новая rich-линия должна выпускаться только как новый reviewed successor release с собственной canary/state identity.

## Historical editorial — reusable evidence-backed cycles

Для регулярных исторических публикаций используется отдельный provider-inert workflow:

```text
historical-editorial/README.md
historical-editorial/v1/source-catalog.json
historical-editorial/v1/theology-profile.json
historical-editorial/v1/cycles/<cycle>/manifest.json
```

Он предназначен для биографий служителей, истории миссий, мученичества, богословских споров и проверяемых исторических фактов. Источники шардируются по темам и переиспользуются между циклами; каждый material claim требует независимого cross-check и как минимум одного grade-A source. Богословская оценка хранится отдельно от исторического описания и привязана к exact commit профиля проекта.

Новый цикл не создаёт нового renderer или transport path. Sealed bundle материализуется в `HistoricalEditorialQueueV1`, затем в существующий `RichArticleDocument`. Канонический preflight и scaffold-next доступны через:

```bash
python -m video_channel_manager.telegram_historical_bundle preflight <manifest>
python -m video_channel_manager.telegram_historical_bundle scaffold-next <manifest> ...
```

Редакционный preflight никогда не является разрешением на Telegram provider write.

## Safety

Нельзя вручную изменять source JSON ради оформления уже начатой кампании: это изменит queue digest и нарушит ledger binding. Новое оформление вводится только новой reviewed presentation policy/version или отдельным successor release.

Нельзя считать repository/editorial approval разрешением на Telegram provider write. Provider execution остаётся отдельным exact-target переходом с durable intent, одной mutation authority и readback/reconciliation без blind retry.
