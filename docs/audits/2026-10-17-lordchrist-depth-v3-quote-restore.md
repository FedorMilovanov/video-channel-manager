# Depth-v3: восстановление полных цитат @lordchrist — 17 октября 2026 (вторая ревизия того же дня)

## Вывод

1. **Читатель отверг пост №17 в формате quote-v5 от первой ревизии.** Цитата «Они даны защищать его в страдании…» открывается местоимением без антецедента: читатель не знает ни кто «они», ни кто «он». Вердикт владельца: нужны полноценные самодостаточные умные цитаты, а не обрывки; заголовок-костыль обрывок не компенсирует.
2. **Аудит всех 44 pending подтвердил ровно три афорных обрывка — №17, №32, №36** (все с вердиктом `keep` в depth-аудите). Корень — translation ledger (`successor-translation-ledger-v1.json`, scope `exact_fragment_only`): дословные фрагменты заменили полные рецензированные переводы sealed-корпуса. У остальных 41 карточки runtime-цитаты самодостаточны.
3. **№17 успел выйти до переделки** — 2026-10-17 10:40 UTC, слот «morning», durable сообщение [1567](https://t.me/lordchrist/1567), под политикой quote-v4 (жирный заголовок + обрывок). Это неизменная опубликованная история: restore для №17 отменён, граница handoff — **17 published / 43 pending**.
4. **Решение — штатный версионированный релиз depth-v3 restore**, без правки sealed payloads и без обхода гейтов: слоты №32/№36 восстановлены дословно на первое предложение исходного запечатанного перевода source-v1 (субъект назван в самой цитате); остальные 58 карточек байт-идентичны depth-v2. Политика quote-v5 переделана на `title_mode=none` — заголовков больше нет вообще ни у одной карточки.

## Что читатель увидит дальше (№18, первый pending)

```text
<blockquote>Моя праведность была Сам Иисус Христос, вчера, сегодня и вовеки Тот же.</blockquote>
— Джон Беньян, «Благодать, изливающаяся на величайшего из грешников», §229

разъяснение (2+ предложения)

#хэштеги
```

Восстановленные слоты (когда дойдёт очередь):

- №32 (Златоуст, Беседа 7 на Филиппийцам): «Христос стал послушным Отцу как Сын; это не низводит Его до рабского состояния.»
- №36 (Беньян, §233): «Если Христос и я соединены, тогда Его праведность — моя, Его заслуги — мои, Его победа — моя.»

## Артефакты и крипто-связки

| Артефакт | Значение |
| --- | --- |
| `successor-depth-restore-v1.json` | restore-релиз: entries №32/№36, `handoff_published_prefix=17`, identity digest = `sha256:8d7dfd231908855894412b780a6c7a73840420ae03d931a0bfb49bac4e292913` (canonical JSON от `{release_id, base_release_id, base_queue_digest, restores}`) |
| `presentation-policy-v5.json` | `lordchrist-quote-v5`, digest `sha256:4607230a3385d81d94dc49bd498fbe8f2fbd2d13e029710acf1413b1f8ef2f42`; `title_mode=none`; ни одной заголовочной привязки |
| `quote-standalone-review-v2.json` | schema v2: ровно 43 записи 18..60, все `self_contained`, `title_resolved_anaphora` запрещён моделью |
| `quote-pending-content-findings-v2.json` | открытая находка №44 перепривязана к v3 (boundary 17) |
| `successor-depth-presentation-migration-v2.json` | граница v4→v5: `published_boundary=17`; №16 и №17 — единственные посты quote-v4-эры (№17 = сообщение 1567) |
| `successor-depth-runtime-activation-v5.json` | schema v3, `required_published_prefix=17`, `required_pending_suffix=43`, history digest `sha256:2d08a58b30803d3db2b6c5a75b0a844d0aac144598da9f7fb8212431a0d9fd35` (принятая история 1–17, state ref `a708b30`) |
| `production-schedule.json` | `successor_queue_digest` = v3; следующий — №18 |

Гейты: publication_id остаются `lordchrist-successor-depth-v2-*` (стабильные ключи), `RESTORE_FORBIDDEN_OPENINGS` запрещают восстановленной цитате открываться на «они/он/она/его/их/этот/…», restore-валидатор требует одно предложение-строку, `_require_standalone_quotation` — структурную завершённость. Cross-track guard получил трек `depth_v3` (durable v3-ledger проверяется наравне с v2).

## Durable rebind (без правки запечатанного)

`initialize-v3-ledger` (подтверждение `INITIALIZE_REVIEWED_DEPTH_V3_LEDGER`) проверяет exact handoff: глубинный v2-ledger обязан иметь ровно 17 verified/published и 43 pristine pending; v3-ledger наследует 17 исторических записей с их durable-квитами байт-в-байт (payload-дрейф = hard fail) и создаёт 43 чистых pending. Инициализация выполняется guarded-конвейером при первой публикации после мержа (read-only preflight материализует её локально в `.runtime/` и валидирует против неё).

## Почему нужен merge

Запланированные публикации выполняются только с `main` (`github.ref == 'refs/heads/main'`). Пока PR не смержен, cron на main продолжает публиковать по старому коду и старым артефактам: старый cron-баг (слоты на 3 часа позже заявленных) и обрывки №32/№36 в старом рендере останутся в силе до слияния.
