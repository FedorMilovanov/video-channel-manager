# @lordchrist content contract

Эта папка разделяет **verified source evidence** и **Telegram presentation**.

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

## Research / rich-линия — следующий редакционный стандарт

Большие исторические, сравнительные, биографические и объясняющие материалы **не должны** сводиться к растянутому quote-посту. Для них действует отдельный reader-first rich contract:

```text
RICH_EDITORIAL_STANDARD.md
```

Текущий подготовленный successor corpus:

```text
research-queues/editorial-successor-v3.json
research-posts-v3/
```

Rich-материал строится как короткая Telegram-статья: сильный точный заголовок, короткий lead, 2–4 смысловых раздела, доказательная визуальная поддержка там, где она реально помогает, и спокойный итог. Для исторических материалов допустимы и предпочтительны несколько изображений, если каждое выполняет отдельную роль: портрет/источник/артефакт/архив/схема/сравнение. Изображения не добавляются ради декора.

Старая research-v2 provider release, однажды получившая unresolved provider outcome, остаётся retired/no-replay. Её нельзя оживлять blind retry. Новая rich-линия должна выпускаться только как новый reviewed successor release с собственной canary/state identity.

## Safety

Нельзя вручную изменять source JSON ради оформления уже начатой кампании: это изменит queue digest и нарушит ledger binding. Новое оформление вводится только новой reviewed presentation policy/version или отдельным successor release.

Нельзя считать repository/editorial approval разрешением на Telegram provider write. Provider execution остаётся отдельным exact-target переходом с durable intent, одной mutation authority и readback/reconciliation без blind retry.
