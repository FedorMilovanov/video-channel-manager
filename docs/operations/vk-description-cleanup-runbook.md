# Техническая волна описаний VK Видео — операционный регламент

Канал: **The Legendary Poet**  
Сообщество: `235216998`

Цель: безопасно очистить описания всей VK-видеотеки от неподдерживаемой разметки и устаревших ссылок, не переписывая факты, интерпретации и авторский текст.

## 1. Текущий рабочий процесс

Описание проходит отдельной волной после каталога и названий:

```text
fresh VK snapshot
→ deterministic technical cleanup
→ semantic-body gate
→ signed descriptions_only plan
→ HTML/Markdown review
→ live dry-run
→ explicit execute
→ postflight
→ one ZIP handoff
```

Операция описаний не может менять:

- название видео;
- название альбома;
- membership видео в альбомах;
- состав видеотеки;
- содержательные слова, пунктуацию и порядок авторских абзацев.

## 2. Что разрешено менять автоматически

Только механически доказуемые элементы:

- YouTube playlist URL → точный VK album `share_url`;
- ссылка на собственное YouTube-видео → точный URL соответствующего VK-видео;
- видимые `*`, `` ` `` и `_` вне URL;
- zero-width символы;
- неправильный `https://thelegendarypoet` → `https://thelegendarypoet.ru/`;
- старые или дублированные footer-строки;
- количество хэштегов до policy limit;
- избыточные пустые строки и варианты декоративного разделителя;
- единый канонический блок The Legendary Poet.

Факты и литературная интерпретация не исправляются в этой волне. Они сохраняются и попадают в `deferred_editorial_review` для отдельного фактчекинга.

## 3. Semantic-body gate

Для каждого before/after вычисляется содержательная форма, из которой исключены только:

- URL;
- хэштеги;
- известный footer;
- Markdown-маркеры;
- декоративные линии;
- whitespace;
- zero-width символы.

Если после такого исключения остаётся хотя бы одно отличие в слове или пунктуации, генератор останавливается:

```text
Description cleanup changes semantic body for <video-id>
```

Такой ролик разрешается только через явный `description_review_only_ids` или отдельный вручную утверждённый override.

## 4. Что было исправлено после реального запуска названий

### Структурированный успех VK

`video.edit` может вернуть не только число `1`, но и объект:

```json
{"success": 1, "access_key": "..."}
```

Оба ответа считаются только acknowledgement. После них writer обязательно повторно читает live-состояние и подтверждает точный after.

### Неизменённые поля не отправляются

При title-only операции параметр `desc` не передаётся в `video.edit`. При description-only операции параметр `name` не передаётся. Это предотвращает нормализацию другого поля со стороны VK.

### Resume после частичного успеха

Каждый новый запуск классифицирует состояние:

- `before` → `ready`;
- `after` → `already applied`;
- третье состояние → `conflict`.

Частично выполненная волна безопасно продолжается без повторной записи уже применённых операций.

## 5. Подготовка

```powershell
cd C:\Users\Fedor\Projects\video-channel-manager

git fetch origin
git switch agent/vk-editorial-plan
git pull --ff-only

py -3.11 -m pip install -e ".[dev]"
```

Не запускать одновременно другой VK writer и не сохранять те же видео вручную через VK Studio.

## 6. Следующий шаг: построение плана и dry-run

Одна команда:

```powershell
pwsh -File .\scripts\Invoke-VkDescriptionWave.ps1
```

Скрипт автоматически:

1. находит последний `vk-title-wave-apply-*.zip`;
2. извлекает из него `04-final-vk-snapshot.json`;
3. строит подписанный `descriptions_only` plan;
4. создаёт Markdown и удобный HTML «До/После»;
5. выполняет свежий live dry-run;
6. создаёт один ZIP;
7. открывает HTML и Проводник с выделенным ZIP.

Отправлять нужно только:

```text
data\handoffs\vk-description-wave-dry-run-YYYYMMDD-HHMMSS.zip
```

## 7. Что проверить в dry-run ZIP

Обязательно:

```text
component_scope = descriptions_only
titles_to_update = 0
albums_to_rename = 0
placements_to_add = 0
placements_to_remove = 0
videos_to_delete = 0
conflicts = 0
```

Для каждой операции:

```text
semantic_body_preserved = true
semantic_body_sha256 = sha256:...
change_reasons = [непустой список]
```

HTML-отчёт открывает before/after каждого описания отдельными раскрывающимися блоками.

## 8. Execute

Новый план нельзя построить и сразу исполнить. Сначала нужен отдельный dry-run и проверка ZIP.

После проверки запускать с точным путём к плану:

```powershell
pwsh -File .\scripts\Invoke-VkDescriptionWave.ps1 `
  -Execute `
  -Plan .\data\reports\vk-editorial-description-wave-YYYYMMDD-HHMMSS.json
```

Скрипт самостоятельно читает фактические `ready / already applied / conflicts` и передаёт точные SHA-256 executor’у.

## 9. Итоговый ZIP

При успехе или ошибке ZIP создаётся в `finally` и содержит:

- source snapshot;
- plan JSON;
- Markdown report;
- HTML review;
- policy;
- preflight log;
- apply log;
- result journal;
- final snapshot при успехе;
- README;
- manifest с размером и SHA-256 каждого файла.

Отправлять нужно только один файл:

```text
data\handoffs\vk-description-wave-apply-YYYYMMDD-HHMMSS.zip
```

## 10. Условия успешного завершения

Требуется одновременно:

```text
result.status = completed
final preflight ready = 0
final preflight conflicts = 0
membership SHA-256 не изменился
названия видео не изменились
альбомы не изменились
semantic body каждого описания совпал
```

HTTP 200 или `success: 1` сами по себе не являются доказательством успеха.
