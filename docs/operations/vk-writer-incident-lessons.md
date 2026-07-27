# VK writer — постоянные уроки реальных запусков

Этот документ фиксирует не советы из памяти чата, а обязательные инженерные правила, полученные из реальных запусков The Legendary Poet.

## Инцидент 1: успешный `video.edit` был принят за ошибку

Наблюдавшийся ответ VK:

```json
{"access_key": "20286989e196b83cf1", "success": 1}
```

Старая проверка принимала только scalar `1` и завершила процесс как failed, хотя VK уже мог применить операцию.

Постоянное исправление:

1. принимать scalar `1` и object `success: 1` как acknowledgement;
2. не считать acknowledgement доказательством postcondition;
3. повторно читать target из VK;
4. сверять точные after-поля;
5. только после этого журналировать `updated_and_verified`.

## Инцидент 2: title-only запрос нормализовал description

При переименовании старый writer повторно отправлял неизменённое описание. VK удалил trailing spaces и zero-width символы у части описаний.

Видимый текст не изменился, но операция вышла за буквальную область title-only.

Постоянное исправление:

- title-only отправляет `name`, но не `desc`;
- description-only отправляет `desc`, но не `name`;
- оба поля отправляются только когда оба действительно меняются;
- verification проверяет и целевое поле, и неизменность второго поля.

## Инцидент 3: журнал был пуст после частичного remote success

Ошибка произошла после ответа VK, но до добавления операции в result journal. Повторный запуск не должен слепо повторять весь пакет.

Постоянное исправление:

- live preflight всегда классифицирует каждую операцию по фактическому before/after;
- `already applied` не записывается повторно;
- `conflict` блокирует весь execute;
- число `ready` берётся из нового preflight, а не из старого чата;
- executor повторяет preflight уже под single-writer lock.

## Инцидент 4: пользователю приходилось искать много файлов

Раньше plan, report, dry-run, result и snapshot лежали в разных папках.

Постоянное исправление:

- каждый operational wrapper создаёт один handoff ZIP;
- ZIP создаётся в `finally`, включая failed runs;
- внутри есть README и manifest;
- manifest содержит размеры и SHA-256;
- Проводник открывается с выделенным ZIP;
- пользователю нужно отправлять только один файл.

## Инцидент 5: техническая очистка может незаметно стать редактурой

Regex-cleanup допустим для ссылок и разметки, но не должен менять факты или литературную интерпретацию.

Постоянное исправление:

- description wave использует semantic-body fingerprint;
- из сравнения исключаются только URL, footer, hashtags, Markdown, decorative rules, whitespace и zero-width;
- любое оставшееся отличие блокирует план;
- фактические и чувствительные утверждения сохраняются и выносятся в deferred review.

## Обязательные acceptance criteria для новых writers

Каждый новый remote writer обязан иметь:

1. read-only default;
2. exact target identity;
3. signed plan;
4. exact-before guard;
5. idempotent before/after/conflict classification;
6. no resend of unchanged fields;
7. provider response-shape tests;
8. live postcondition read;
9. single-writer lock;
10. locked re-preflight;
11. per-operation journal;
12. resume after partial success;
13. full postflight;
14. unchanged unrelated-state digest;
15. one ZIP handoff with manifest.

## Документация имеет приоритет

При расхождении между старой командой из чата и текущим runbook источником истины являются:

- код текущей ветки;
- актуальный operational runbook;
- подписанный plan;
- свежий dry-run ZIP.
