# Video Channel Manager

**Video Channel Manager** — safety-first инструмент для аудита, редакционной проверки, организации и синхронизации видеоканалов YouTube, VK и локального медиархива.

Это не одноразовый YouTube → VK скрипт. Проект строится как платформенно-нейтральный модульный монолит:

- несколько локальных YouTube/VK account aliases;
- полные read-only снимки `AuditPackage`;
- единые canonical editorial records и платформенные renderers;
- версионированные `ChangePlan` и платформенные планы;
- точные remote IDs без угадывания;
- deterministic text renderers для каждой платформы;
- dry-run, exact confirmations и per-target single-writer locks;
- backup, per-operation journal, postcondition verification и guarded rollback;
- локальный media/image QC и SHA-256 fingerprints;
- SQLAlchemy/Alembic foundation для будущего operation ledger.

> **Текущий операционный статус:** текущие Telegram/YouTube hardening-контуры разделены по типу незавершённости. Issue #154 остаётся artifact-level open до физического rerender/verification «Чёрного человека» из семи accepted quality masters; отдельно Issue #232 владеет будущей repository-level реализацией current-main guarded YouTube release executor / existing-target adoption и сам по себе не авторизует provider writes. Исторический Black Man target `x-puy27S2qs` уже зафиксирован как verified public provider evidence, но это не превращает старые media bytes в current-policy artifact proof и не разрешает повторный upload. Канонический live-статус: [`docs/operations/current-state.md`](docs/operations/current-state.md). Исторические audit registers — evidence only.
>
> Приведённые ниже write/dry-run/execute-команды документируют возможности и safety protocol кода, но сами по себе не разрешают запуск. Любая будущая provider mutation требует нового явного запроса пользователя, нового точного project-bound issue, свежего bounded preflight, reviewed immutable exact-ID plan и отдельной авторизации.

## Основные инварианты

1. **Read-only по умолчанию.** Сканирование и аудит не меняют платформы.
2. **AI анализирует, deterministic executor исполняет.** AI не получает токены и не вызывает provider API напрямую.
3. **Нет guessed IDs.** Все объекты адресуются точными platform/channel/remote IDs.
4. **Before/after state, а не слепая revision.** Ревизия диагностична; фактическое изменяемое поле является источником истины.
5. **Idempotence.** `before → ready`, `after → already applied`, третье состояние → `conflict`.
6. **Single writer на remote target.** Два процесса не могут одновременно менять одно сообщество или канал.
7. **Locked re-preflight.** Перед первой записью live-state проверяется повторно уже после захвата lock.
8. **Immutable evidence.** Snapshot, plan, backup и result остаются отдельными JSON-артефактами и связываются SHA-256.
9. **Postcondition, а не доверие HTTP 200.** После write выполняется повторное provider read.
10. **Human editorial boundary.** Факты, интерпретации и неоднозначная пунктуация не исправляются автоматически.

## Архитектура

```text
Human editor / external AI
           │
           │ AuditPackage ↔ canonical content ↔ reviewed Plan
           ▼
┌────────────────────────────────────────────────┐
│             Video Channel Manager              │
│                                                │
│ CLI → Editorial Core → Renderer → Plan Guard   │
│                              │                 │
│ Preview → Platform Adapter → Guarded Executor  │
│                              │                 │
│ Domain + exchange schemas + persistence        │
│                              │                 │
│ YouTube adapter | VK adapter | Local media     │
└────────────────────────────────────────────────┘
```

Полный mutation protocol:

```text
complete snapshot + SHA-256
→ canonical reviewed content
→ deterministic platform rendering
→ self-validating plan
→ readable preview / diff
→ dry-run
→ exact confirmations
→ target lock
→ locked re-preflight
→ backup
→ journaled writes
→ per-item verification
→ full postflight
→ immutable result / guarded rollback
```

См. [`docs/architecture.md`](docs/architecture.md), [`docs/exchange-format.md`](docs/exchange-format.md) и [`docs/adr/0003-guarded-remote-mutations.md`](docs/adr/0003-guarded-remote-mutations.md).

## Документы, являющиеся источником истины

### Unified editorial

- [`docs/editorial/unified-editorial-standard.md`](docs/editorial/unified-editorial-standard.md) — canonical schema, evidence boundary, anti-hallucination и approval rules;
- [`docs/editorial/platform-rendering-rules.md`](docs/editorial/platform-rendering-rules.md) — общие и платформенные правила YouTube/VK, fallback и layout diagnostics;
- [`docs/editorial/content-authoring-guide.md`](docs/editorial/content-authoring-guide.md) — как писать факт, вопрос, ссылки, variation key и suitability;
- [`docs/operations/unified-editorial-runbook.md`](docs/operations/unified-editorial-runbook.md) — validate, preview, signed plan, immutable snapshot preflight и platform apply paths.

### YouTube

- [`docs/youtube-editorial-standard.md`](docs/youtube-editorial-standard.md) — структура канала, названия, плейлисты, фактчекинг и approval rules;
- [`docs/youtube-comment-editorial-standard.md`](docs/youtube-comment-editorial-standard.md) — source-led top-level comments и schema v2 compatibility;
- [`docs/operations/youtube-comment-publishing-runbook.md`](docs/operations/youtube-comment-publishing-runbook.md) — audit, queue, signed plan, dry-run, execute и resume для комментариев;
- [`docs/youtube-description-rendering-standard.md`](docs/youtube-description-rendering-standard.md) — точная YouTube-разметка, первый абзац, пунктуация и emoji policy;
- [`docs/youtube-copy-automation-safety.md`](docs/youtube-copy-automation-safety.md) — узкая deterministic boundary для автоматических исправлений;
- [`docs/youtube-copy-fix-application.md`](docs/youtube-copy-fix-application.md) — plan v3, dry-run, execute, backup, postflight и rollback;
- [`docs/youtube-share-preview-standard.md`](docs/youtube-share-preview-standard.md) — требования к SHARE preview;
- [`docs/audits/2026-07-25-copy-validation-v2.md`](docs/audits/2026-07-25-copy-validation-v2.md) — ручная триаж-проверка реального канала.

### VK

- [`docs/vk-description-rendering-standard.md`](docs/vk-description-rendering-standard.md) — почему VK Видео не рендерит YouTube Markdown и как строится plain text;
- [`docs/operations/vk-description-cleanup-runbook.md`](docs/operations/vk-description-cleanup-runbook.md) — whole-library VK cleanup v2;
- [`docs/operations/vk-catalog-wall-and-article-runbook.md`](docs/operations/vk-catalog-wall-and-article-runbook.md) — guarded catalog, wall post и article workflow;
- [`docs/vk-readonly.md`](docs/vk-readonly.md) — VK token/inventory и безопасные read-only команды;
- [`docs/research/2026-07-25-vk-api-source-ledger.md`](docs/research/2026-07-25-vk-api-source-ledger.md) — VK API source ledger;
- [`docs/research/2026-07-25-cross-platform-hardening-source-ledger.md`](docs/research/2026-07-25-cross-platform-hardening-source-ledger.md) — cross-platform hardening ledger.

### Local media / Resi DASH

- [`docs/operations/resi-dash-local-handoff.md`](docs/operations/resi-dash-local-handoff.md) — канонический Resi/DASH `Manifest.mpd` → retained master → optional exact trim → ffprobe/SHA-256 workflow;
- [`docs/operations/operator-output-handoff-rule.md`](docs/operations/operator-output-handoff-rule.md) — canonical Windows outbox и copy/paste contract;
- [`docs/audits/2026-08-10-resi-postmerge-operator-audit.md`](docs/audits/2026-08-10-resi-postmerge-operator-audit.md) — post-merge аудит operator UX/provenance и закрытые классы дефектов.

Operational docs и versioned plans имеют приоритет над памятью чата.

## Установка — Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

video-manager doctor
video-manager db init
video-manager schema export --output-dir .\schemas
video-manager example export --output-dir .\examples\generated
```

Секреты хранятся только в ignored paths:

```text
secrets/client_secret.json
data/secrets/
```

Никогда не выполнять `git clean -fdx` в рабочем дереве с ignored OAuth/VK credentials, exports, backups и result logs.

# Unified editorial/content pipeline

## Validate and preview

Один canonical record или существующий YouTube comment record schema v2 можно валидировать и рендерить без remote API:

```powershell
video-manager content validate --input .\content\editorial

video-manager content preview `
  --platform youtube `
  --surface comment `
  --input .\content\editorial\examples\tyutchev-night-sea.json

video-manager content preview `
  --platform vk `
  --surface video_description `
  --input .\content\editorial\examples\tyutchev-night-sea.json
```

Batch preview:

```powershell
video-manager content preview `
  --platform vk `
  --surface video_description `
  --input .\content\editorial `
  --strict `
  --json-output .\data\reports\vk-editorial-preview.json
```

`--strict` отклоняет не только renderer errors, но и warnings. Duplicate content IDs, variation keys и rendered text отклоняются на уровне batch.

## Signed generic content plan

Generic plan является review/preflight artifact, а не самостоятельным remote executor. Target manifest обязан содержать:

- immutable snapshot path/ID;
- `source_snapshot_sha256` точного audit JSON;
- timezone-aware snapshot timestamp;
- exact target IDs;
- exact-before text/revision для updates.

```powershell
video-manager content plan build `
  --platform vk `
  --surface video_description `
  --input .\content\editorial `
  --targets .\data\reports\vk-editorial-targets.json `
  --output .\data\reports\vk-editorial-plan.json

video-manager content plan validate .\data\reports\vk-editorial-plan.json

video-manager content plan preflight `
  .\data\reports\vk-editorial-plan.json `
  --state .\data\reports\vk-editorial-live-state.json `
  --json-output .\data\reports\vk-editorial-preflight.json
```

Preflight требует полный state coverage и explicit `exists: true/false`; отсутствующая строка никогда не считается доказательством отсутствия target.

## Platform apply paths

YouTube comments продолжают использовать зрелый guarded comment executor:

```powershell
python .\scripts\build_youtube_comment_plan.py ...
python .\scripts\apply_youtube_comment_plan.py ... # сначала dry-run
```

VK descriptions сначала встраиваются в существующий signed catalog plan, затем исполняются его guarded executor’ом:

```powershell
video-manager content plan adapt-vk-catalog `
  .\data\reports\vk-catalog-plan.json `
  --input .\content\editorial `
  --require-all `
  --output .\data\reports\vk-catalog-editorial-plan.json

python .\scripts\apply_vk_catalog_plan.py `
  .\data\reports\vk-catalog-editorial-plan.json ... # сначала dry-run
```

`adapt-vk-catalog` принимает только approved records с timezone-aware `reviewed_at`, сохраняет exact-before guards исходного VK plan и пересчитывает полный plan SHA-256.

# YouTube

## OAuth и read-only inventory

```powershell
video-manager youtube login --account legendary-poet
video-manager youtube accounts
video-manager youtube channels --account legendary-poet
video-manager youtube scan --account legendary-poet
```

Guarded description writes требуют отдельный explicit write token:

```powershell
video-manager youtube login --account legendary-poet --write --force
```

OAuth tokens и client secrets не включаются в `AuditPackage` и не коммитятся.

## Редакционная проверка

Один UTF-8 текст:

```powershell
python .\scripts\validate_youtube_copy.py .\description.txt --strict
```

Полный `AuditPackage`:

```powershell
python .\scripts\validate_youtube_copy.py `
  .\data\exports\youtube-audit-package.json `
  --output .\data\reports\youtube-copy-validation.md
```

Автоматизация меняет только механически доказуемые вещи: очищает первый абзац от видимых SHARE-маркеров, исправляет известные link labels, лишнюю точку после `?`, `!` или `…`, zero-width символы и избыточные пустые строки. Неоднозначные запятые, точки, двоеточия, факты и литературная интерпретация остаются review-only.

## Self-validating YouTube plan v3

Создание плана:

```powershell
python .\scripts\autofix_youtube_copy.py `
  .\data\exports\youtube-audit-package.json
```

Offline-проверка целостности:

```powershell
python .\scripts\validate_youtube_copy_plan.py `
  .\data\reports\youtube-copy-fix-plan.json
```

Plan v3 фиксирует:

- exact target channel;
- полный hash проверенных video IDs;
- before/after SHA-256 каждой операции;
- ruleset;
- self `plan_sha256`;
- unresolved videos, исключённые из automation.

Dry-run strict executor:

```powershell
python .\scripts\apply_youtube_copy_plan_v3.py `
  .\data\reports\youtube-copy-fix-plan.json `
  --account legendary-poet `
  --confirm-channel UC_EXACT_CHANNEL_ID
```

Execute разрешён только с точным количеством ready-операций и `plan_sha256`, показанными dry-run:

```powershell
python .\scripts\apply_youtube_copy_plan_v3.py `
  .\data\reports\youtube-copy-fix-plan.json `
  --account legendary-poet `
  --confirm-channel UC_EXACT_CHANNEL_ID `
  --confirm-count 56 `
  --confirm-plan-sha256 sha256:EXACT_DIGEST `
  --execute
```

Executor держит Windows-safe channel lock, повторяет preflight после lock, пишет backup до первой mutation, журналирует каждую попытку, выполняет bounded reread verification, полный postflight и guarded rollback.

Историческая команда `video-manager youtube apply-copy-fixes` сохранена для уже завершённых schema v2 workflows. Новые массовые операции должны использовать strict v3 executor.

После изменения ruleset пересчитывается только затронутый результат:

```powershell
python .\scripts\rebuild_youtube_copy_plan.py `
  .\data\reports\youtube-copy-apply-YYYYMMDD-HHMMSS.json
```

Recovery выполняется отдельным guarded script и никогда не перезаписывает третье неизвестное live-состояние:

```powershell
python .\scripts\recover_youtube_copy_apply.py `
  .\data\reports\youtube-copy-apply-YYYYMMDD-HHMMSS.json `
  --account legendary-poet `
  --confirm-channel UC_EXACT_CHANNEL_ID
```

Подтверждённый `status=completed` result не следует повторно выполнять только потому, что позднее изменилась whole-record revision.

# VK

## Token и read-only inventory

Текущий video contour использует **user access token** с ожидаемыми `video` и `groups` permissions.

```powershell
video-manager vk login --account legendary-poet
video-manager vk accounts
video-manager vk communities --account legendary-poet
video-manager vk scan --account legendary-poet --community 235216998
```

Снимок включает полный `owner_id_video_id`, `type`, размеры, albums, system markers и memberships.

## Обычное описание VK Видео — plain text

VK не предоставляет Markdown/HTML parse mode для обычного video description. Поэтому маркеры:

```text
*жирное*
_курсив_
~~зачёркнутое~~
```

снимаются до публикации. URL, hashtags, технические ID, абзацы и название `К ***` сохраняются. Неразрешённые HTML/Markdown-маркеры блокируют editorial plan и требуют review.

## Полный read-only аудит live-описаний

```powershell
python .\scripts\audit_all_vk_descriptions.py `
  --account legendary-poet `
  --community 235216998
```

Plan schema v2 содержит полный live-ID coverage, `coverage_remote_ids_sha256`, before/after hashes, `plan_sha256` и readable Markdown diff.

Offline-проверка:

```powershell
python .\scripts\validate_vk_description_cleanup_plan.py `
  .\data\reports\vk-live-description-cleanup-<timestamp>.json
```

Старые schema v1 plans остаются историей и намеренно отклоняются apply-скриптом.

## Dry-run whole-library cleanup

```powershell
python .\scripts\apply_all_vk_description_cleanup.py `
  .\data\reports\vk-live-description-cleanup-<timestamp>.json `
  --account legendary-poet `
  --community 235216998
```

Не добавлять `--execute`, пока Markdown diff не просмотрен и dry-run не показал `conflicts 0` и `review-only 0`. Полная процедура находится в runbook.

## Новые YouTube → VK публикации

Оператор использует только safe wrapper:

```powershell
python .\scripts\sync_youtube_to_vk_textsafe.py <аргументы>
```

Он включает centralized VK publication policy, community lock, `ffprobe` QC, обязательные video/audio streams, положительную duration и SHA-256 media fingerprint. Базовый `scripts/sync_youtube_to_vk.py` является implementation module, а не самостоятельным safety profile.

## Exact-ID recovery

```powershell
python .\scripts\resume_youtube_to_vk_exact_ids.py `
  <youtube-audit.json> `
  <exact-video-id...> `
  --journal <journal.json> `
  --cache-dir <cache> `
  --account legendary-poet `
  --community 235216998
```

Dry-run строит transfer manifest SHA-256. Execute требует подтвердить community, new upload count, source snapshot и manifest. Журнал фиксирует `upload_reserved → uploaded_processing → uploaded_and_verified`.

# Resi / DASH — локальное видео

Для обычного Resi/DASH `Manifest.mpd` используется repository-owned local-only handoff, а не заново собранная команда `yt-dlp`/FFmpeg из памяти чата:

```powershell
video-manager resi handoff "https://resi.media/.../Manifest.mpd?src=emb" `
  --title "Название ролика" `
  --start "50:12" `
  --end "1:49:52" `
  --encoder auto
```

`--start/--end` можно не указывать для полного скачивания. Времена принимаются как `MM:SS[.mmm]` или `HH:MM:SS[.mmm]`; длительность вычисляется автоматически. Если `--title` не задан, используется детерминированное source-derived имя, а не общий `Resi Download`.

Сгенерированный UTF-8-BOM PowerShell handoff лежит в canonical `operator-output`, сам показывает `yt-dlp -F`, выбирает `bestvideo+bestaudio/best`, использует bounded retries, сохраняет полный master, валидирует A/V/duration через `ffprobe`, считает SHA-256 и пишет source receipt + result JSON. Existing master разрешено использовать повторно только при совпадении source fingerprint и текущего master SHA-256. При exact trim видео перекодируется для точной границы, исходный audio stream копируется без бессмысленного lossy up-bitrate.

Полный one-action Windows пример, NVENC/CPU policy, stop conditions и разбор реальных дефектов 2026-08-10 находятся в [`docs/operations/resi-dash-local-handoff.md`](docs/operations/resi-dash-local-handoff.md).

# Локальные данные

Generated artifacts находятся в ignored `data/`:

```text
data/exports/   # snapshots
data/reports/   # plans, backups, results, readable reports
data/cache/     # downloaded media and thumbnails
data/locks/     # local writer locks
data/secrets/   # local credentials
```

User-facing interactive artifacts, включая Resi handoff/master/result, находятся в ignored `operator-output/` по [`operator-output-handoff-rule.md`](docs/operations/operator-output-handoff-rule.md).

JSON snapshots/backups/results не являются исходным кодом и не должны попадать в публичный GitHub. Для отдельной копии используется зашифрованное резервное хранилище с проверкой восстановления.

# CLI

```text
video-manager version
video-manager doctor
video-manager db init
video-manager schema export
video-manager example export
video-manager plan validate plan.json
video-manager plan preview plan.json
video-manager content validate --input content/editorial
video-manager content preview --platform youtube --surface comment --input content/editorial
video-manager content preview --platform vk --surface video_description --input content/editorial
video-manager content plan build --platform vk --surface video_description --input content/editorial --targets targets.json
video-manager content plan validate editorial-plan.json
video-manager content plan preflight editorial-plan.json --state live-state.json
video-manager content plan adapt-vk-catalog vk-catalog-plan.json --input content/editorial --require-all
video-manager local scan H:\ --output local-inventory.json
video-manager resi handoff https://resi.media/.../Manifest.mpd --start 50:12 --end 1:49:52
video-manager youtube login --account legendary-poet
video-manager youtube accounts
video-manager youtube channels --account legendary-poet
video-manager youtube scan --account legendary-poet
video-manager vk login --account legendary-poet
video-manager vk accounts
video-manager vk communities --account legendary-poet
video-manager vk scan --account legendary-poet --community 235216998
video-manager compare audits youtube.json vk.json
```

# Разработка

```bash
pip check
python -m compileall -q src scripts tests
ruff check .
ruff format --check .
mypy src --show-error-codes
python -m pytest --cov=video_channel_manager --cov-report=term-missing
pip-audit --skip-editable --desc on
```

CI запускается на Python 3.11, 3.12 и 3.13. Blocking gates: dependency graph, compileall, vulnerability audit, Ruff correctness, Ruff formatting, strict mypy и full pytest. Completed-state CI `30994245235` прошёл во всех шести средах: `796 passed, 1 xfailed`, coverage `78%` по `14,306` statements, Ruff format `449` файлов, strict mypy `145` source files и три PowerShell environment green.

# Текущий статус развития

Исторические Waves 0–13 закрыты и остаются audit evidence. Текущий точный residual разделён на два независимых owning scope: #154 — artifact-level rerender/verification current-policy media из семи accepted quality masters; #232 — repository-level реализация будущего current-main guarded YouTube release executor с read-only existing-target adoption. Ни один из этих issue не является standing authorization для provider write.

Provider rollout исторических Black Man bytes уже зафиксирован как verified public evidence для `x-puy27S2qs`; этот факт блокирует забывчивый повторный upload, но не закрывает #154. Новая provider-facing execution по #232 потребует отдельного явного запроса пользователя, свежего exact preflight/review и отдельной авторизации. Unattended remote writes, произвольные playlist mutations и исторические executors не являются допустимым «следующим этапом».

## Вне текущего scope

```text
unattended remote writes
playlist mutations без нового отдельного контракта
Temporal/Celery/Redis cluster
cookies основного канала как downloader identity
arbitrary yt-dlp plugins
Prometheus/Grafana для редких CLI-запусков
```
