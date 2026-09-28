# @lordchrist content contract

Эта папка разделяет **verified source evidence** и **Telegram presentation**.

## Agent start here

Если агенту дали только ссылку на репозиторий и задачу по `@lordchrist` / «Господь Бог — Сила Моя», сначала открыть:

1. `AGENTS.md` — локальный read order и приоритет правил;
2. `RICH_EDITORIAL_STANDARD.md` — канонический стандарт больших богословских/исторических постов;
3. `QUOTE_ATTRIBUTION_STANDARD.md` — цитаты, подписи и точное правило воздуха перед цитатами;
4. `DIRECT_COPY_TO_TELEGRAM.md` — ручная rich-copy вставка на Android и `U+2060` spacing;
5. только затем task-specific research/evidence.

**Research drafts не являются presentation authority.** Старый draft может хранить правильные факты и source anchors, но его типографику нельзя механически копировать, если она расходится с текущими стандартами.

## Источник — не финальный визуальный шаблон

`verified-30-posts.json` и `verified-30-posts.md` фиксируют проверенные source cards: перевод непрерывного фрагмента, автора, труд, location, source URL, anchors и historical source attribution. После первого verified canary source JSON и его digest остаются immutable.

Поэтому встречающийся в source card текст вида:

```text
© Автор, «Название труда»
```

не является текущим визуальным шаблоном Telegram.

## Короткая quote-линия — текущий production

Canonical policy:

```text
presentation-policy.json
policy_id = lordchrist-editorial-v2
```

Короткая линия остаётся живым production-форматом и не должна переписывать immutable source cards. `lordchrist-editorial-v2` выбирает для основного акцента самую содержательную прямую цитату, сохраняет спокойную типографику attribution и текущие spacing/link-preview правила.

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

Если полная качественная версия поста помещается в Telegram, **не сокращать её только ради компактности**. Убирать повторы и слабые формулировки, а не полезную экзегезу, доказательства или контекст. Финальный preflight обязан считать точный вставляемый текст вместе с переводами строк и невидимыми spacing-символами.

Для ручной публикации статьи, собранной интерактивно в ChatGPT на телефоне, действует отдельный transport preflight:

```text
DIRECT_COPY_TO_TELEGRAM.md
```

Канонический Android-путь: rendered ChatGPT text → Copy → Telegram composer → long-press → system **Paste / «Вставить»**. Вставка из clipboard/history панели клавиатуры запрещена для rich posts, потому что она может превратить содержимое в plain text. Обычные пустые строки при rich paste могут схлопываться, поэтому нужный paragraph air сохраняется отдельной невидимой строкой `U+2060 WORD JOINER` согласно runbook.

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
