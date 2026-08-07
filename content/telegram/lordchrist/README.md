# @lordchrist content contract

Эта папка разделяет **verified source evidence** и **Telegram presentation**.

## Источник — не финальный визуальный шаблон

`verified-30-posts.json` и `verified-30-posts.md` фиксируют проверенные source cards: перевод непрерывного фрагмента, автора, труд, location, source URL, anchors и historical source attribution. После первого verified canary source JSON и его digest остаются immutable.

Поэтому встречающийся в source card текст вида:

```text
© Автор, «Название труда»
```

не является текущим визуальным шаблоном Telegram.

## Финальный Telegram presentation

Canonical policy:

```text
presentation-policy.json
policy_id = lordchrist-editorial-v1
```

Human-readable specification/examples:

```text
../../../docs/operations/lordchrist-telegram-presentation-v1.md
```

Финальный вид:

- первый прямой `«…»` в теле — **bold**;
- последующие прямые `«…»` — *italic*;
- без прямой речи тело остаётся plain;
- **Автор**, *«Название труда»*;
- visible `©` удаляется;
- перед hashtags — дополнительный пустой ENTER (`\n\n\n` после attribution);
- hashtags сохраняются.

Renderer реализован в:

```text
src/video_channel_manager/telegram_presentation.py
```

`preview` показывает одновременно immutable source payload и exact rendered provider payload. Source SHA и provider/presentation SHA намеренно являются разными доказательствами.

## Safety

Нельзя вручную изменять source JSON ради оформления уже начатой кампании: это изменит queue digest и нарушит ledger binding. Новое оформление вводится только новой reviewed presentation policy/version.
