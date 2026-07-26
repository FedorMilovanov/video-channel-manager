# VK catalog, wall post and SEO article runbook

Дата: 2026-07-25  
Сообщество: `235216998` — The Legendary Poet  
Режим: fresh snapshot → reviewed plan → dry-run → exact confirmations → locked execute → postflight

## Цель

Этот контур решает три разные задачи отдельными проверяемыми операциями:

1. привести VK Видео к единой структуре альбомов и описаний;
2. опубликовать ровно один выбранный ролик на стене без дубля;
3. связать ролик с глубокой статьёй, где каждый факт имеет источник.

Массовая публикация на стену, удаление альбомов, переименование существующих альбомов и автоматическое литературное переписывание не входят в этот workflow.

## 0. Один рабочий writer

Во время любой команды с `--execute` должны быть остановлены:

- старый YouTube → VK transfer;
- thumbnail sync;
- cleanup descriptions;
- другой catalog/wall executor для сообщества `235216998`.

Оба новых executor используют один per-community lock, но старые процессы, запущенные из несовместимой ветки, всё равно необходимо остановить вручную.

## 1. Подготовить unified worktree

Рекомендуемый отдельный worktree:

```powershell
$repo = "C:\Users\Fedor\Projects\video-channel-manager"
$unified = "C:\Users\Fedor\Projects\video-channel-manager-unified"

cd $repo
git fetch origin

if (-not (Test-Path $unified)) {
    git worktree add $unified origin/integration/youtube-vk-unified-v2
}

cd $unified
git switch integration/youtube-vk-unified-v2
git pull --ff-only

if (-not (Test-Path .\.venv)) {
    py -3.11 -m venv .venv
}
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Общие OAuth/VK tokens, snapshots и journals остаются в основном data directory:

```powershell
$env:VCM_DATA_DIR = "$repo\data"
video-manager doctor
```

## 2. Создать свежие read-only снимки

```powershell
video-manager youtube scan --account legendary-poet
video-manager vk scan --account legendary-poet --community 235216998

$yt = Get-ChildItem "$repo\data\exports\youtube-legendary-poet-*.json" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$vk = Get-ChildItem "$repo\data\exports\vk-legendary-poet-235216998-*.json" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

Write-Host "YouTube snapshot:" $yt.FullName
Write-Host "VK snapshot:" $vk.FullName
```

Не использовать старый VK snapshot: после частичного transfer журнал и live-каталог могли разойтись.

## 3. Построить подписанный catalog plan

Проверенная карта 11 загрузок хранится отдельно:

```text
content/mappings/youtube-vk-reviewed-20260725.json
```

Builder проверяет, что каждый указанный VK remote ID присутствует в свежем снимке. Отсутствующий или повторно использованный ID блокирует построение плана.

```powershell
python .\scripts\build_vk_catalog_plan.py `
    "$($yt.FullName)" `
    "$($vk.FullName)" `
    --mapping-json .\content\mappings\youtube-vk-reviewed-20260725.json `
    --output "$repo\data\reports\vk-catalog-plan.json" `
    --report "$repo\data\reports\vk-catalog-plan.md"
```

Открыть и проверить:

```powershell
notepad "$repo\data\reports\vk-catalog-plan.md"
```

План разделяет:

- `album_operations` — только создание отсутствующих альбомов;
- `placement_operations` — только отсутствующие memberships;
- `text_operations` — exact before/after title и description;
- `review_only` — неоднозначные сопоставления и редакционные проблемы, исключённые из automation.

Каждое обычное описание проходит VK-native renderer:

- YouTube Markdown снимается;
- URL и hashtags сохраняются;
- `https://thelegendarypoet.ru/` добавляется ровно один раз;
- неподтверждённые смысловые изменения не создаются.

## 4. Catalog dry-run

```powershell
python .\scripts\apply_vk_catalog_plan.py `
    "$repo\data\reports\vk-catalog-plan.json" `
    --account legendary-poet `
    --community 235216998
```

Требуемый результат перед execute:

```text
conflicts: 0
Dry-run only. No VK mutation method was called.
```

`review-only` может быть больше нуля: эти элементы исключены из automation. Для полного покрытия нужно внести точные reviewed mappings или вручную исправить исходный текст, затем пересобрать план.

## 5. Catalog execute

Подставить четыре значения, показанные текущим dry-run:

```powershell
python .\scripts\apply_vk_catalog_plan.py `
    "$repo\data\reports\vk-catalog-plan.json" `
    --account legendary-poet `
    --community 235216998 `
    --execute `
    --confirm-community 235216998 `
    --confirm-ready EXACT_READY_COUNT `
    --confirm-plan-sha256 "sha256:EXACT_PLAN_DIGEST" `
    --confirm-video-coverage "sha256:EXACT_VIDEO_COVERAGE" `
    --write-delay 2
```

Executor:

- повторяет live preflight после lock;
- классифицирует операции как `ready`, `already_applied` или `conflict`;
- создаёт только отсутствующие альбомы;
- добавляет только отсутствующие memberships;
- меняет текст только из точного reviewed before-state;
- пишет result после каждой операции;
- выполняет свежий VK scan и полный postflight.

При сетевой ошибке не создавать новый план вслепую. Сначала повторить dry-run того же плана: уже подтверждённые состояния будут классифицированы как `already_applied`.

## 6. Первый wall candidate

Проверенный по transfer journal кандидат:

```text
YouTube: U4D40EQg10U
VK:      -235216998_456239142
Title:   О, Русь моя! Жена моя! ⚡ НА ПОЛЕ КУЛИКОВОМ ⚡ Александр Блок
```

Свежий VK snapshot обязан подтвердить exact remote ID и текущий текст. Старый transfer journal сам по себе не является разрешением на `wall.post`.

Подготовлены:

```text
content/wall-posts/aleksandr-blok-na-pole-kulikovom.txt
content/wall-posts/aleksandr-blok-na-pole-kulikovom.sources.json
content/video-articles/aleksandr-blok-na-pole-kulikovom.md
content/video-articles/aleksandr-blok-na-pole-kulikovom.sources.json
```

Статья пока имеет статус `editorial-review`. Когда страница будет опубликована на сайте, предпочтительно заменить ссылку на корень сайта в wall draft одной ссылкой на точную статью и передать её через `--article-url`.

## 7. Построить wall plan

До публикации статьи текущий draft ведёт на главную сайта ровно один раз:

```powershell
python .\scripts\build_vk_wall_post_plan.py `
    "$($vk.FullName)" `
    --video "-235216998_456239142" `
    --message .\content\wall-posts\aleksandr-blok-na-pole-kulikovom.txt `
    --sources .\content\wall-posts\aleksandr-blok-na-pole-kulikovom.sources.json `
    --output "$repo\data\reports\vk-wall-post-plan.json"
```

После публикации статьи использовать её точный URL:

```powershell
python .\scripts\build_vk_wall_post_plan.py `
    "$($vk.FullName)" `
    --video "-235216998_456239142" `
    --message .\content\wall-posts\aleksandr-blok-na-pole-kulikovom.txt `
    --sources .\content\wall-posts\aleksandr-blok-na-pole-kulikovom.sources.json `
    --article-url "https://thelegendarypoet.ru/EXACT-PUBLISHED-ARTICLE-ROUTE" `
    --output "$repo\data\reports\vk-wall-post-plan.json"
```

Перед вторым вариантом текстовый draft тоже должен содержать тот же article URL вместо главной страницы, иначе message hash и содержимое будут расходиться.

## 8. Wall dry-run

```powershell
python .\scripts\apply_vk_wall_post_plan.py `
    "$repo\data\reports\vk-wall-post-plan.json" `
    --account legendary-poet `
    --community 235216998
```

Executor читает точный live video, сравнивает title/description с планом и сканирует до 500 последних записей сообщества по exact video attachment.

Требуемый результат:

```text
duplicate posts found: 0
Dry-run only. wall.post was not called.
```

## 9. Опубликовать ровно один пост

Подставить exact values из текущего dry-run:

```powershell
python .\scripts\apply_vk_wall_post_plan.py `
    "$repo\data\reports\vk-wall-post-plan.json" `
    --account legendary-poet `
    --community 235216998 `
    --execute `
    --confirm-community 235216998 `
    --confirm-video "-235216998_456239142" `
    --confirm-plan-sha256 "sha256:EXACT_PLAN_DIGEST" `
    --confirm-message-sha256 "sha256:EXACT_MESSAGE_DIGEST" `
    --confirm-duplicate-count 0
```

Wall executor:

- использует `owner_id=-235216998` и `from_group=true`;
- прикрепляет exact `video-235216998_456239142`;
- использует deterministic `guid`;
- не повторяет неоднозначно завершившийся `wall.post`;
- после ответа читает созданную запись через `wall.getById`;
- проверяет exact message и video attachment;
- при ошибке требует нового dry-run, который сначала ищет возможный уже созданный дубль.

## 10. Стандарт статьи для каждого видео

Каждая статья получает два файла:

```text
content/video-articles/<slug>.md
content/video-articles/<slug>.sources.json
```

Source ledger обязан содержать:

- exact YouTube/VK IDs;
- proposed slug и publish status;
- список проверяемых claims;
- связь каждого claim с `source_id`;
- тип источника: primary text, author context, archive edition или secondary research;
- запрет автоматического литературного переписывания;
- human editorial gate.

Приоритет источников:

1. текст произведения и авторская публицистика;
2. цифровые коллекции государственных библиотек и музеев;
3. академические издания и статьи;
4. популярные обзоры — только как дополнительный контекст.

В wall post выносится краткий проверенный тезис и несколько главных ссылок. Полный анализ, библиография и редакционные оговорки остаются в статье, чтобы пост не превращался в перегруженный список URL.

## 11. После выполнения

```powershell
video-manager vk scan --account legendary-poet --community 235216998
```

Сохранить независимо от Git:

- свежий VK snapshot;
- catalog plan и Markdown review;
- catalog apply result;
- wall post plan;
- wall post result с exact wall URL;
- опубликованный article URL и окончательный source ledger.
