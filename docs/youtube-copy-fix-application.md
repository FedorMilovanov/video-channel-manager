# Автоматическое исправление описаний YouTube

Канал: **The Legendary Poet**  
Назначение: пакетное исправление детерминированных ошибок описаний без ручного поиска роликов.

## Что исправляется автоматически

- парные `*...*` и `_..._` удаляются только из первого абзаца, потому что SHARE-превью не передаёт жирный и курсив;
- разметка во втором и последующих абзацах сохраняется;
- пунктуация меняется только в узких детерминированных случаях; общая синтаксическая пунктуация остаётся редакторским решением;
- лишняя точка после уже имеющихся `?`, `!` или `…` удаляется;
- однозначные подписи вроде `*VK:*` нормализуются;
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

Для фактологических описаний с известными проблемами нужен отдельный проверенный текст. Технический автофикс не выдаёт косметическую правку за полный фактчекинг.

## Текущий safety protocol

Будущие массовые операции используют copy plan **schema v3**:

```text
AuditPackage
→ deterministic autofix
→ exact checked_video_ids
→ before/after hashes
→ target_channel_id
→ plan_sha256
→ Markdown diff
→ live dry-run
→ exact count + plan SHA confirmation
→ Windows-safe channel lock
→ locked re-preflight
→ backup
→ per-attempt journal
→ postflight
→ guarded rollback
```

Исторические schema v2 plans и уже завершённые result logs остаются доказательствами прошлых операций. Их не нужно и нельзя повторно исполнять новым v3 executor.

## 1. Построить свежий локальный план v3

Сначала создать новый read-only AuditPackage:

```powershell
video-manager youtube scan `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ
```

Затем:

```powershell
python .\scripts\autofix_youtube_copy.py `
  .\data\exports\youtube-legendary-poet-UC-78ys2S3cQ3lpqgXfo-SvQ-<timestamp>.json
```

Будут созданы:

```text
data\reports\youtube-legendary-poet-...-copy-fix-plan.json
data\reports\youtube-legendary-poet-...-copy-fix-report.md
```

Plan v3 содержит:

- точный `target_channel_id`;
- отсортированный полный `checked_video_ids`;
- SHA-256 списка проверенных ID;
- SHA-256 исходного AuditPackage;
- before/after SHA-256 каждой операции;
- `plan_sha256` всего документа.

Исходный AuditPackage и YouTube не изменяются.

## 2. Проверить plan offline

```powershell
python .\scripts\validate_youtube_copy_plan.py `
  .\data\reports\youtube-legendary-poet-...-copy-fix-plan.json
```

Любое ручное изменение JSON после генерации нарушит `plan_sha256`. Исправления следует вносить в правила/исходник и затем создавать новый план, а не редактировать JSON.

## 3. Прочитать Markdown diff

Открыть созданный `copy-fix-report.md` и проверить:

- начало, середину и конец;
- первый абзац нескольких роликов;
- ссылки с подчёркиваниями;
- подписи VK/Telegram/RUTUBE;
- отсутствие изменений фактов и литературных трактовок;
- список `Unresolved error-level findings`.

Unresolved-видео не входят в automatic operations и разбираются отдельно.

## 4. Выполнить live dry-run

Для будущих plan v3 используется строгий executor:

```powershell
python .\scripts\apply_youtube_copy_plan_v3.py `
  .\data\reports\youtube-legendary-poet-...-copy-fix-plan.json `
  --account legendary-poet `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ
```

Write-доступ для dry-run не нужен. Команда:

- валидирует schema v3 и self-digest;
- проверяет exact target channel;
- проверяет before/after hashes;
- читает текущее описание каждого operation video;
- классифицирует `ready / already applied / conflict`;
- допускает unrelated revision drift только при совпадении фактического `before`;
- не вызывает write-методов.

Ожидаемый итог:

```text
YouTube plan v3 preflight: ready N | already applied M | revision drift tolerated R
Dry-run only. No remote write method was called.
```

При ошибке ничего не менять. Сначала разобрать точный video ID и причину.

## 5. Один раз выдать write-доступ

```powershell
video-manager youtube login `
  --account legendary-poet `
  --write `
  --force
```

Проверка:

```powershell
video-manager youtube accounts
```

В колонке `Access` должно быть `write`.

## 6. Зафиксировать подтверждения

Из dry-run и plan:

```powershell
$plan = Get-Item ".\data\reports\youtube-legendary-poet-...-copy-fix-plan.json"
$planJson = Get-Content $plan.FullName -Raw | ConvertFrom-Json
$ready = <число ready из dry-run>
$planSha = $planJson.plan_sha256
```

Не брать значения из старого чата, старого plan v2 или прошлой операции.

## 7. Применить пакет v3

Перед запуском остановить другие YouTube writers и не сохранять описания вручную через Studio.

```powershell
python .\scripts\apply_youtube_copy_plan_v3.py `
  "$($plan.FullName)" `
  --account legendary-poet `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --execute `
  --confirm-count $ready `
  --confirm-plan-sha256 $planSha
```

После захвата channel lock preflight выполняется заново. Только затем проверяются точный ready count и plan SHA.

До первой записи создаётся:

```text
data\reports\youtube-copy-backup-v3-YYYYMMDD-HHMMSS.json
```

Журнал:

```text
data\reports\youtube-copy-apply-v3-YYYYMMDD-HHMMSS.json
```

Каждый ролик перечитывается после `videos.update`. Если YouTube кратко возвращает pre-update snippet, повторяются только verification reads — сам ambiguous write автоматически не повторяется.

## 8. Сбой и rollback

При исключении или `Ctrl+C`:

1. новые операции прекращаются;
2. затронутые операции рассматриваются в обратном порядке;
3. backup повторно записывается только из известного after/original state;
4. третье неизвестное состояние не перезаписывается;
5. каждый rollback сохраняется в result log.

Статусы:

```text
completed
failed_rolled_back
failed_partial_rollback
```

При `failed_partial_rollback` не создавать новый массовый apply до разбора `rollback_failed`.

## 9. Контроль после успешного применения

Повторный dry-run того же v3-плана должен показать:

```text
ready 0
already applied N
```

Поздний whole-record revision drift сам по себе не означает неудачу: источником истины является verified `after_description` и completed result log.

## 10. Ruleset rebuild

Когда меняются только безопасные editorial rules, completed result можно пересчитать:

```powershell
python .\scripts\rebuild_youtube_copy_plan.py `
  .\data\reports\youtube-copy-apply-<timestamp>.json
```

Новый rebuild также создаёт plan schema v3 с `plan_sha256`. Он не откатывает всю прошлую партию и предлагает только реально отличающиеся corrective operations.

## 11. Историческая CLI-команда

```text
video-manager youtube apply-copy-fixes
```

сохраняется для совместимости с уже завершёнными историческими schema v2 workflows. Для новых планов и будущих массовых применений использовать только:

```text
scripts/apply_youtube_copy_plan_v3.py
```

После контролируемого объединения YouTube- и VK-веток строгий v3 executor будет зарегистрирован как основной CLI backend без переписывания OAuth/read-only команд.
