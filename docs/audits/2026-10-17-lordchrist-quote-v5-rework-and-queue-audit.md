# Переработка формата цитат @lordchrist (quote-v5) и аудит очередей — 17 октября 2026

## Вывод

1. **Формат маленьких постов-цитат переработан штатно, без костылей.** Презентационный слой в этой архитектуре изначально отделён от запечатанных карточек: новая политика `lordchrist-quote-v5` меняет только рендер, не трогая sealed payloads, порядок очереди и опубликованную историю. Все проверки (render proof, rolling checkpoint, миграция, preflight) прогнаны офлайн на точном durable state — зелёные.
2. **Биографии никуда не делись — они стоят в durable state.** Линия исторических постов замерла после сентябрьских canary по трём независимым причинам: cron в UTC срабатывал в 22:17 МСК при freshness-окне до 21:17 МСК; в v2-ledger никогда не был записан `canary_verified_at_utc`; все плановые даты цикла 2026-09 истекли. Возобновление требует: исправленного cron (сделано в этом PR), editorial approval canary (ручной workflow с точным подтверждением) и нового reviewed цикла с будущими датами.
3. **Исследовательская линия закрыта навсегда решением владельца (#286, 2026-08-10).** Августовская отправка осталась в состоянии `may_exist`; disposition `retired_no_replay` запрещает replay, inferred receipt/absence и successor activation от этой retired-отправки. Это не потеря данных: все 5 research-постов и ledger сохранены в репозитории и state.

## Что сделано с форматом (quote-v5)

Читательская претензия: маленькие посты-цитаты не должны открываться служебным заголовком; заголовок допустим только когда он реально нужен — и тогда с воздухом (пустой строкой) перед цитатой, не впритык.

Проверка по reviewed-данным `quote-standalone-review-v1.json` (45 карточек 16..60): 42 открытия `self_contained`, 3 — `title_resolved_anaphora` (№17 Герналл, №32 Златоуст, №36 Беньян) — только у этих трёх заголовок разрешает анафору в цитате.

Новый рендер v5:

```text
самодостаточная карточка (42 из 44 pending):
  <blockquote>цитата</blockquote>
  — подпись (одной строкой, tight)
  <воздух>
  разъяснение
  <воздух>
  #хэштеги

load-bearing карточка (№17, 32, 36):
  Жирный заголовок
  <воздух>
  <blockquote>цитата</blockquote>
  — подпись
  <воздух>
  разъяснение
  <воздух>
  #хэштеги
```

Артефакты и крипто-связки:

| Артефакт | Значение |
| --- | --- |
| `presentation-policy-v5.json` | `lordchrist-quote-v5`, digest `sha256:1baa56feba381fcf6147222a8cdc6e0e2da569ad9af3b159fe1b0e548307c1f6`; `title_mode=reviewed_load_bearing_only`; ровно 3 payload-привязки заголовков |
| `successor-depth-presentation-migration-v2.json` | immutable граница v4→v5: `published_boundary=16` |
| `successor-depth-runtime-activation-v5.json` | schema v3, `verified_prefix`, `required_published_prefix=16`, `required_pending_suffix=44`, history digest `sha256:aff979b43beeca9d1bdd12f8ed9ee96022b668c75f1be59a70274516012ec400` (точная принятая история 1–16 из state ref `0666ec7`) |
| `production-schedule.json` | policy v5; cron слотов `17 6 * * *` (утро) и `17 18 * * 2,5,0` (вечер) |

№16 — единственный пост, вышедший в v4 (сообщение 1566, 2026-10-16): остаётся immutable history, его durable v4 rendered evidence продолжает проверяться в составе принятой истории. С №17 публикуется v5. Ровно один тест-инвариант: рендер-пруф сверяет набор заголовочных payload-хэшей политики с `title_resolved_anaphora`-строками standalone-review — дрейф невозможен.

Длины цитат в pending-суффиксе 17–60: 18 коротких (<150 символов, №43–60), 26 средних (150–400); минимальная 40, максимальная 224 символа. «Больших» (≥400) в очереди нет — это свойство запечатанного корпуса, а не рендера; волновой порядок строгий, короткие афоризмы идут в конце очереди.

## Аудит: где биографии и исследования

| Линия | Состояние на state ref `0666ec7` | Причина остановки |
| --- | --- | --- |
| Quote depth-v2 (текущая) | 16 published/verified, 44 pending | активна; №16 вышел 2026-10-16, далее v5 |
| Historical v2 (биографии: Беньян, Джадсон, холера 1854, Кэри, Фуллер, Тиндал, Стэм, Саттлер) | 1 published (canary, сообщение 1515 от 2026-09-07), 8 pending `impossible` | cron `17 19 * * 1,3,6` = 19:17 **UTC** = 22:17 МСК; слот 19:17 МСК + freshness 120 мин истекает в 21:17 МСК → каждый плановый запуск «succeeded» со skip `slot_expired_no_backfill`; отдельно — `canary_verified_at_utc=None` (editorial approval canary не выполнен) и плановые даты 2026-09-14..30 истекли |
| Historical v3 media (Spurgeon archival) | 1 published/verified (сообщение 1516 от 2026-09-08) | та же причина: cron за окном freshness, даты сентября истекли |
| Research (5 постов: three-preachers-numbers, sermons-survive-century, learning-across-generations, three-expository-patterns, hidden-discipline) | 1 `unknown/may_exist` → `retired_no_replay`, 4 pending `impossible` | перманентный retirement #286 от 2026-08-10 после unresolved отправки; replay и successor activation запрещены самим disposition |

Путь возобновления биографий (без костылей, по шагам):

1. Cron исправлен в этом PR: `17 16 * * 1,3,6` = 16:17 UTC = 19:17 МСК (внутри freshness-окна).
2. Требуется ручной `lordchrist-historical-editorial-approval.yml` с точным подтверждением `APPROVE-HISTORY:<message_id>` для canary — он закрывает editorial-флаги в durable ledger.
3. Требуется новый reviewed production-release цикла с будущими датами (существующие `production-release-2026-09-cycle-02*.json` sealed и сентябрьские). Контент 8 биографий проверен и готов; v3-архивная редакция имеет media-материал.

Вечерний слот цитат имел тот же UTC-баг: cron `17 21 * * 2,5,0` = 21:17 UTC = 00:17 МСК следующих суток, всегда за пределами lease 160 минут — вечерние запуски «succeeded» без публикации. Утренний выживал только благодаря lease 720 минут, поэтому фактические публикации шли в ~12:17–14:30 МСК вместо 09:17 МСК. Теперь: утро `17 6 * * *` (09:17 МСК), вечер `17 18 * * 2,5,0` (21:17 МСК). Лимиты не изменились: 1 verified/слот, максимум 2/день, backfill запрещён.

## Проверки

- Baseline до изменений: rolling v4 checkpoint прогнан офлайн на точном state ref `0666ec7` (16/44, следующий №17) — зелёный.
- После изменений: v5 render proof и v5 rolling checkpoint (`--require-provider-writes`) прогнаны на том же state — зелёные; следующий пост №17 c заголовком и воздухом, №18+ без заголовка.
- Тесты: полный набор репозитория — 2860 passed, 1 skipped, 1 xfailed; ruff на изменённых файлах — чисто.
- Никаких Telegram-отправок, state-мутаций или изменений sealed-карточек в ходе этой работы не выполнялось.

## Границы

- Дата: 2026-10-17. State ref на момент расчёта history digest: `state/lordchrist-telegram` @ `0666ec7d90e1f510a3b48d50b795957ab461d6ba` (16 published).
- Если до слияния этого PR успеет выйти №17 в старом формате (следующее окно — понедельник 2026-10-19 ~09:17–11:17 UTC), границу активации нужно пересчитать на 17/43 по той же процедуре; всё остальное не меняется.
- Дефект перевода №44 остаётся учтён в `quote-pending-content-findings-v1.json`; исправление — только новым reviewed release/rebind.
