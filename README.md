# Video Channel Manager

**Video Channel Manager** — safety-first инструмент для аудита, редакционной проверки, организации и синхронизации видеоканалов YouTube, VK и локального медиархива.

Это не одноразовый YouTube → VK скрипт. Проект строится как платформенно-нейтральный модульный монолит:

- несколько локальных YouTube/VK account aliases;
- полные read-only снимки `AuditPackage`;
- версионированные `ChangePlan` и платформенные планы;
- точные remote IDs без угадывания;
- deterministic text renderers для каждой платформы;
- dry-run, exact confirmations и single-writer locks;
- backup, per-operation journal, postcondition verification и guarded rollback;
- локальный media QC и SHA-256 fingerprints;
- SQLAlchemy/Alembic foundation для будущего operation ledger.

> **Статус:** YouTube и VK read-only inventory работают. Для отдельных одобренных сценариев реализованы guarded writers и recovery scripts. Удаления и unattended remote writes по-прежнему выключены. Любая массовая запись требует свежего снимка, читаемого diff, dry-run и точных подтверждений.

## Основные инварианты

1. **Read-only по умолчанию.** Сканирование и аудит не меняют платформы.
2. **AI анализирует, deterministic executor исполняет.** AI не получает токены и не вызывает provider API напрямую.
3. **Нет guessed IDs.** Все объекты адресуются точными platform/channel/remote IDs.
4. **Before/after state, а не слепая revision.** Ревизия полезна, но фактическое изменяемое поле является источником истины.
5. **Idempotence.** `before → ready`, `after → already applied`, третье состояние → `conflict`.
6. **Single writer на remote target.** Два процесса не могут одновременно менять одно сообщество/канал.
7. **Locked re-preflight.** Перед первой записью весь live-state проверяется повторно после захвата lock.
8. **Immutable evidence.** Snapshot, plan, backup и result остаются отдельными JSON-артефактами.
9. **Postcondition, а не доверие HTTP 200.** После write выполняется повторное provider read.
10. **Human approval.** Факты, интерпретации и сомнительный текст не исправляются автоматически.

## Архитектура

```text
Human editor / external AI
           │
           │ AuditPackage ↔ reviewed Plan
           ▼
┌────────────────────────────────────────────────┐
│             Video Channel Manager              │
│                                                │
│ CLI → Plan Guard → Preview → Executor          │
│                │                               │
│ Domain + exchange schemas + persistence        │
│                │                               │
│ YouTube adapter | VK adapter | Local media     │
└────────────────────────────────────────────────┘
```

Полный mutation protocol:

```text
complete snapshot
→ deterministic proposal
→ self-validating plan
→ readable diff
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

См. [`docs/architecture.md`](docs/architecture.md) и [`docs/adr/0003-guarded-remote-mutations.md`](docs/adr/0003-guarded-remote-mutations.md).

## Документы, являющиеся источником истины

- [`docs/youtube-editorial-standard.md`](docs/youtube-editorial-standard.md) — структура канала, названия, плейлисты, фактчекинг и approval rules;
- [`docs/youtube-description-rendering-standard.md`](docs/youtube-description-rendering-standard.md) — точная YouTube-разметка, первый абзац, пунктуация и emoji policy;
- [`docs/vk-description-rendering-standard.md`](docs/vk-description-rendering-standard.md) — почему VK Видео не рендерит YouTube Markdown и как строится plain text;
- [`docs/operations/vk-description-cleanup-runbook.md`](docs/operations/vk-description-cleanup-runbook.md) — полный whole-library VK cleanup v2;
- [`docs/vk-readonly.md`](docs/vk-readonly.md) — VK OAuth/token/inventory и безопасные read-only команды;
- [`docs/research/2026-07-25-vk-api-source-ledger.md`](docs/research/2026-07-25-vk-api-source-ledger.md) — 52-source VK API ledger;
- [`docs/research/2026-07-25-cross-platform-hardening-source-ledger.md`](docs/research/2026-07-25-cross-platform-hardening-source-ledger.md) — 100+ первичных источников и решения NOW/NEXT/LATER/NO.

Не полагайтесь только на память чата: operational docs и versioned plans имеют приоритет.

## Установка — Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

video-manager doctor
video-manager db init
```

Секреты хранятся только в ignored paths, например:

```text
secrets/client_secret.json
data/secrets/
```

Никогда не выполнять `git clean -fdx` в рабочем дереве с ignored OAuth/VK credentials.

## YouTube

### OAuth и read-only inventory

```powershell
video-manager youtube login --account legendary-poet
video-manager youtube accounts
video-manager youtube channels --account legendary-poet
video-manager youtube scan --account legendary-poet
```

OAuth tokens и client secrets не включаются в `AuditPackage` и не коммитятся.

### Редакционная проверка

```powershell
python .\scripts\validate_youtube_copy.py .\description.txt --strict
```

Для полного снимка:

```powershell
python .\scripts\validate_youtube_copy.py `
  .\data\exports\youtube-audit-package.json `
  --output .\data\reports\youtube-copy-validation.md
```

YouTube update workflows используют field-level before/after equivalence, reread verification, backup и recovery. Подтверждённый completed result не следует повторно выполнять только потому, что поздняя whole-record revision изменилась.

## VK

### Token и read-only inventory

Текущий video contour использует **user access token** с ожидаемыми `video` и `groups` permissions.

```powershell
video-manager vk login --account legendary-poet
video-manager vk accounts
video-manager vk communities --account legendary-poet
video-manager vk scan --account legendary-poet --community 235216998
```

Снимок включает полный `owner_id_video_id`, `type`, размеры, albums, system markers и memberships.

### Обычное описание VK Видео — plain text

VK не предоставляет Markdown/HTML parse mode для обычного поля video description. Поэтому YouTube-маркеры:

```text
*жирное*
_курсив_
~~зачёркнутое~~
```

должны сниматься до публикации. URL, hashtags, технические ID, абзацы и название `К ***` сохраняются.

### Полный read-only аудит всех live-описаний

```powershell
python .\scripts\audit_all_vk_descriptions.py `
  --account legendary-poet `
  --community 235216998
```

Актуальный скрипт создаёт **plan schema v2** с:

- полным live-ID coverage;
- `coverage_remote_ids_sha256`;
- before/after hashes;
- `plan_sha256`;
- readable Markdown diff.

Проверка JSON без обращения к VK:

```powershell
python .\scripts\validate_vk_description_cleanup_plan.py `
  .\data\reports\vk-live-description-cleanup-<timestamp>.json
```

Старые schema v1 plans остаются историей и намеренно отклоняются apply-скриптом.

### Dry-run whole-library cleanup

```powershell
python .\scripts\apply_all_vk_description_cleanup.py `
  .\data\reports\vk-live-description-cleanup-<timestamp>.json `
  --account legendary-poet `
  --community 235216998
```

Не добавляйте `--execute`, пока Markdown diff не просмотрен и dry-run не показал `conflicts 0` и `review-only 0`. Полная процедура находится в runbook.

### Новые YouTube → VK публикации

Оператор использует только safe wrapper:

```powershell
python .\scripts\sync_youtube_to_vk_textsafe.py <аргументы>
```

Он включает:

- централизованный VK title/description policy;
- community single-writer lock;
- `ffprobe` media QC;
- обязательные video/audio streams;
- положительную duration;
- SHA-256 media fingerprint.

Базовый `scripts/sync_youtube_to_vk.py` является implementation module и не является самостоятельным safety profile.

### Exact-ID recovery

```powershell
python .\scripts\resume_youtube_to_vk_exact_ids.py `
  <youtube-audit.json> `
  <exact-video-id...> `
  --journal <journal.json> `
  --cache-dir <cache> `
  --account legendary-poet `
  --community 235216998
```

Dry-run строит transfer manifest SHA-256. Execute требует подтвердить community, new upload count, source snapshot и manifest. Журнал фиксирует промежуточные состояния remote reservation/upload/verification.

## Локальные данные

По умолчанию generated artifacts находятся в ignored `data/`:

```text
data/exports/   # snapshots
data/reports/   # plans, backups, results, readable reports
data/cache/     # downloaded media
data/locks/     # local writer locks
data/secrets/   # local credentials
```

JSON snapshots/backups/results не являются исходным кодом. Их не нужно пушить в публичный GitHub. Для отдельной копии используйте зашифрованное резервное хранилище и периодическую проверку восстановления.

## Разработка

```bash
pip check
python -m compileall -q src scripts tests
ruff check .
ruff format --check .
mypy src
pytest --cov=video_channel_manager --cov-report=term-missing
pip-audit --desc on
```

CI запускается на Python 3.11, 3.12 и 3.13. Blocking gates: dependency graph, compileall, Ruff correctness/formatting, mypy и pytest. Vulnerability audit пока сохраняется как diagnostic artifact, чтобы исключения вводились явно, а не скрывали отчёт.

## Текущий порядок развития

### Сейчас

```text
полная проверка VK cleanup v2
safe publication renderer
Windows-safe writer lock
media QC + manifests
journal + verification + rollback
```

### Следом

```text
SQLite operation ledger
state-machine tests
structured redacted logs
secret scanning
restic backup runbook
```

### Пока не добавлять

```text
unattended remote writes
Temporal/Celery/Redis cluster
cookies основного канала как downloader identity
arbitrary yt-dlp plugins
Prometheus/Grafana для редких CLI-запусков
```
