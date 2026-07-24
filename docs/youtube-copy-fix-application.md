# Автоматическое исправление описаний YouTube

Канал: **The Legendary Poet**  
Назначение: пакетное исправление детерминированных ошибок описаний без ручного поиска роликов.

## Что исправляется автоматически

- парные `*...*` и `_..._` удаляются только из первого абзаца, потому что SHARE-превью не передаёт жирный и курсив;
- разметка во втором и последующих абзацах сохраняется;
- завершающая точка, запятая, точка с запятой, `!`, `?` и `…` переносятся внутрь выделения только в безопасных случаях;
- лишняя точка после уже имеющихся `?`, `!` или `…` удаляется;
- подписи `VK`, `Telegram`, `RUTUBE` и плейлистов получают двоеточие внутри выделения;
- лишние пробелы у краёв `*...*` и `_..._` убираются;
- три и более перевода строки сводятся к одной пустой строке.

## Что не меняется автоматически

- факты и литературные интерпретации;
- заголовки видео;
- tags и хэштеги;
- ссылки;
- эмодзи;
- длинные абзацы;
- плейлисты и Shorts;
- приватность и другие настройки видео.

Для фактологических описаний с известными проблемами, например «Тучи» Пушкина, нужен отдельный проверенный текст. Технический автофикс не выдаёт косметическую правку за полный фактчекинг.

## 1. Построить локальный план

```powershell
python .\scripts\autofix_youtube_copy.py `
  .\data\exports\youtube-legendary-poet-UC-78ys2S3cQ3lpqgXfo-SvQ-20260724-202430.json
```

Будут созданы:

```text
data\reports\youtube-legendary-poet-...-copy-fix-plan.json
data\reports\youtube-legendary-poet-...-copy-fix-report.md
```

Исходный AuditPackage и YouTube не изменяются.

## 2. Выполнить live-preflight

Write-доступ для этого шага не нужен:

```powershell
video-manager youtube apply-copy-fixes `
  .\data\reports\youtube-legendary-poet-UC-78ys2S3cQ3lpqgXfo-SvQ-20260724-202430-copy-fix-plan.json `
  --account legendary-poet `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ
```

Команда читает каждое текущее описание и проверяет:

- точный video ID;
- точный channel ID;
- исходную revision;
- полное совпадение текущего описания с `before_description`;
- отсутствие ручных изменений после снимка.

При любом несовпадении весь preflight останавливается до первой записи.

## 3. Один раз выдать write-доступ

```powershell
video-manager youtube login `
  --account legendary-poet `
  --write `
  --force
```

Google снова откроет OAuth-окно. Токен с read-only доступом будет заменён токеном с guarded write-доступом.

Наличие доступа проверяется командой:

```powershell
video-manager youtube accounts
```

В колонке `Access` должно быть `write`.

## 4. Применить пакет

```powershell
video-manager youtube apply-copy-fixes `
  .\data\reports\youtube-legendary-poet-UC-78ys2S3cQ3lpqgXfo-SvQ-20260724-202430-copy-fix-plan.json `
  --account legendary-poet `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --execute
```

Перед первой записью создаётся резервная копия:

```text
data\reports\youtube-copy-backup-YYYYMMDD-HHMMSS.json
```

После выполнения создаётся журнал:

```text
data\reports\youtube-copy-apply-YYYYMMDD-HHMMSS.json
```

Каждый ролик после записи перечитывается с YouTube. Если операция внутри пакета падает, уже применённые описания откатываются в обратном порядке с проверкой новой revision.

## Идемпотентность

Повторный запуск:

- пропускает описания, уже равные `after_description`;
- не перезаписывает ролики, изменённые вручную;
- не применяет план к другому каналу;
- не превышает `--max-operations`;
- не пишет без `--execute`.

## Когда нужен новый снимок

Если preflight сообщает `revision mismatch` или `description mismatch`, выполнить:

```powershell
video-manager youtube scan --account legendary-poet
```

Затем построить новый copy-fix plan из свежего AuditPackage. Старый план применять нельзя.
