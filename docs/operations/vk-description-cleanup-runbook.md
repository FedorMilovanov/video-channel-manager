# Полная очистка описаний VK Видео — операционный регламент

Канал: **The Legendary Poet**  
Сообщество: `235216998`  
Назначение: безопасно убрать неподдерживаемую YouTube/Markdown-разметку из **всей текущей VK-видеотеки**, сохранив фактический текст каждого ролика.

## 1. Основной принцип

Очистка строится не из старого YouTube-описания, а из фактического live-текста VK:

```text
live VK before → детерминированный plain-text renderer → reviewed VK after
```

Поэтому сохраняются:

- ручные дополнения;
- старые ссылки;
- уникальные абзацы;
- фактическая пунктуация и формулировки;
- названия вида `К ***`;
- подчёркивания внутри URL и технических ID.

Автоматически снимаются только парные маркеры, которые обычное описание VK показывает буквально, удаляются zero-width символы, нормализуются переносы и добавляется фирменный блок при отсутствии сайта.

## 2. Что нельзя делать

- Не запускать старый plan schema v1.
- Не редактировать VK Studio параллельно с `--execute`.
- Не запускать второй VK writer для сообщества `235216998`.
- Не передавать `--execute` до полного dry-run.
- Не менять JSON-план вручную после проверки Markdown diff.
- Не использовать `scripts/sync_youtube_to_vk.py` напрямую для новых публикаций; только безопасный wrapper.
- Не считать сообщение API об успехе достаточной проверкой: обязательна повторная live-проверка.

## 3. Почему старый план нужно пересоздать

План:

```text
vk-live-description-cleanup-20260725-054112.json
```

был создан до введения schema v2. Он корректно зафиксировал 111 live-видео на тот момент, но не содержит:

- `policy_version`;
- `coverage_remote_ids_sha256`;
- `plan_sha256`;
- строгой самопроверки счётчиков и before/after hashes.

Новый apply-скрипт намеренно отклоняет такие планы. Старый JSON и Markdown остаются диагностической историей, но не являются разрешением на запись.

## 4. Подготовка окружения

```powershell
cd "C:\Users\Fedor\Projects\video-channel-manager-vk"

git fetch origin
git switch feature/vk-description-rendering-v1
git pull --ff-only

python -m pip install -e ".[dev]"

$mainRepo = "C:\Users\Fedor\Projects\video-channel-manager"
$env:VCM_DATA_DIR = "$mainRepo\data"
```

Перед операцией убедиться, что нет другого локального VK writer:

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -match "sync_youtube_to_vk|resume_youtube_to_vk|apply_all_vk_description|video-manager vk"
  } |
  Select-Object ProcessId, Name, CommandLine
```

Read-only команды допускаются, но для согласованного снимка лучше на время аудита также не сохранять описания вручную.

## 5. Создание свежего plan v2 — только чтение

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

python .\scripts\audit_all_vk_descriptions.py `
  --account legendary-poet `
  --community 235216998 `
  --plan-output "$env:VCM_DATA_DIR\reports\vk-live-description-cleanup-$stamp.json" `
  --report-output "$env:VCM_DATA_DIR\reports\vk-live-description-cleanup-$stamp.md"
```

Скрипт обязан вывести:

```text
Checked N | ready A | review only B | already safe C
Live snapshot confirmation value: <UUID>
Plan SHA-256 confirmation value: sha256:<digest>
Coverage SHA-256: sha256:<digest>
```

Инварианты:

```text
N = A + B + C
remote ID каждого видео встречается ровно один раз
```

Для автоматического исполнения требуется:

```text
review only = 0
```

Если `review only > 0`, запись блокируется до отдельной редакторской проверки и нового аудита.

## 6. Проверка читаемого diff

Открыть созданный Markdown:

```powershell
notepad "$env:VCM_DATA_DIR\reports\vk-live-description-cleanup-$stamp.md"
```

Проверить как минимум:

- начало, середину и конец отчёта;
- несколько длинных описаний;
- названия с `***`;
- URL с `_`;
- строки `VK:`, `Telegram:`, `RUTUBE:`;
- описания с цитатами и многоточиями;
- отсутствие изменений фактов и порядка абзацев;
- отсутствие дубля `https://thelegendarypoet.ru/`.

JSON не редактировать. Любая модификация нарушит `plan_sha256`.

## 7. Выбор свежего плана

```powershell
$plan = Get-ChildItem `
  "$env:VCM_DATA_DIR\reports\vk-live-description-cleanup-*.json" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

$plan.FullName
```

Убедиться, что это новый schema v2:

```powershell
$planJson = Get-Content $plan.FullName -Raw | ConvertFrom-Json
$planJson.schema_version
$planJson.videos_checked
$planJson.plan_sha256
$planJson.coverage_remote_ids_sha256
```

Ожидается `schema_version = 2`.

## 8. Обязательный dry-run

```powershell
python .\scripts\apply_all_vk_description_cleanup.py `
  "$($plan.FullName)" `
  --account legendary-poet `
  --community 235216998
```

Dry-run:

1. проверяет self-digest плана;
2. проверяет before/after hashes;
3. читает полный live-набор VK-ID;
4. требует точного совпадения coverage;
5. повторно читает описание каждой операции;
6. классифицирует `ready / already applied / conflict`;
7. не вызывает ни одного write-метода.

Разрешённый результат:

```text
ready A | already applied C | conflicts 0 | review-only excluded 0
Dry-run only. No remote write method was called.
```

При любом конфликте ничего не менять и создать свежий аудит после выяснения причины.

## 9. Зафиксировать подтверждения

```powershell
$ready = <число ready из dry-run>
$snapshot = $planJson.live_snapshot_id
$planSha = $planJson.plan_sha256
```

Не копировать значения из старого плана или старого чата.

## 10. Выполнение

Перед запуском остановить все другие VK writers и не сохранять вручную через VK Studio.

```powershell
python .\scripts\apply_all_vk_description_cleanup.py `
  "$($plan.FullName)" `
  --account legendary-poet `
  --community 235216998 `
  --execute `
  --confirm-community 235216998 `
  --confirm-count $ready `
  --confirm-live-snapshot $snapshot `
  --confirm-plan-sha256 $planSha
```

После захвата single-writer lock скрипт заново выполняет полный coverage/text preflight. Это закрывает гонку между dry-run и `--execute`.

До первой записи создаётся backup:

```text
vk-live-description-backup-<timestamp>.json
```

После каждой операции обновляется result journal:

```text
vk-live-description-apply-<timestamp>.json
```

## 11. Успешный итог

Требуется одновременно:

```text
status = completed
applied = ready
postflight_verified = ready
postflight_failures = []
rollback = []
```

Консоль должна завершиться сообщением:

```text
Completed A verified VK description updates; final postflight verified the whole batch.
```

## 12. Сбой и откат

При исключении или `Ctrl+C` скрипт:

1. прекращает новые операции;
2. читает фактический текст затронутых роликов в обратном порядке;
3. восстанавливает before только когда live-текст равен плановому after;
4. оставляет без изменения ролики, уже находящиеся в before;
5. не трогает третье неизвестное состояние;
6. записывает результат каждого отката.

Статусы:

```text
failed_rolled_back
failed_partial_rollback
```

При `failed_partial_rollback` не запускать новый массовый план. Сначала разобрать конкретные `rollback_failed`.

## 13. Контроль после операции

Повторный dry-run того же плана должен показать:

```text
ready 0
already applied A
conflicts 0
```

Затем создать новый read-only live-аудит. Он должен показать, что очищенные описания уже `already safe`, а неподдерживаемые маркеры не возвращаются.

Рекомендуется вручную открыть 5–10 роликов разных типов в VK:

- старый длинный ролик;
- недавно перенесённый ролик;
- очень длинное описание;
- описание с несколькими URL;
- название `К ***`;
- короткое видео, если оно входит в live-набор.

## 14. Новые YouTube → VK публикации

Используется только:

```powershell
python .\scripts\sync_youtube_to_vk_textsafe.py <аргументы>
```

Safe wrapper включает:

- VK plain-text renderer;
- централизованное название;
- блокировку сообщества;
- `ffprobe` QC;
- наличие видео- и аудиопотока;
- положительную длительность;
- SHA-256 медиафайла.

Для точечного восстановления exact-ID используется обновлённый:

```powershell
python .\scripts\resume_youtube_to_vk_exact_ids.py <source> <video-id...> ...
```

Он дополнительно требует `--confirm-manifest-sha256` и записывает промежуточные состояния `upload_reserved`, `uploaded_processing`, `uploaded_and_verified`.

## 15. Хранение результатов

Сохранять локально в ignored `data/`:

```text
data/exports/
data/reports/
data/cache/
data/locks/
```

В Git не коммитить:

- OAuth/VK токены;
- cookies;
- полные live-описания;
- backups и result journals;
- медиакэш.

Для внешней резервной копии использовать зашифрованный restic-репозиторий либо другой отдельный защищённый носитель. Проверка резервной копии важнее самого факта копирования.
