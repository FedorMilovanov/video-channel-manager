# Cross-platform hardening source ledger — 80 первичных ссылок

Дата прохода: **25 июля 2026 года**  
Проект: **Video Channel Manager / The Legendary Poet**  
Область: YouTube, VK Видео, получение медиа, безопасные массовые изменения, Windows, тестирование, CI, наблюдаемость и резервное копирование.

## Метод

Приоритет источников:

- **P1** — официальная документация платформы, языка или инструмента;
- **P2** — официальный репозиторий и его wiki/issues;
- **S** — сторонний инструмент, допустимый только после фиксации версии и отдельной проверки.

Статусы решений:

- **NOW** — внедрено или следует внедрить в текущем цикле;
- **NEXT** — полезно после стабилизации текущего VK/YouTube контура;
- **LATER** — оправдано только при росте объёма/команды;
- **NO** — изучено, но сейчас добавит риск или лишнюю сложность.

Этот документ не является списком «установить всё». Он фиксирует, какое решение принято после просмотра источников.

---

## A. VK API и модель обычного описания

1. **P1** [VK API schema](https://github.com/VKCOM/vk-api-schema) — каноническая машинная схема API 5.199. **NOW:** использовать как основной источник параметров и response-форм.
2. **P1** [video/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/video/methods.json) — `video.get`, `video.save`, `video.edit`, альбомы и лимиты. **NOW:** plain-text `description/desc`, offset-пагинация, точные owner/video IDs.
3. **P1** [video/objects.json](https://github.com/VKCOM/vk-api-schema/blob/master/video/objects.json) — поля видео, `type`, изображения, размеры. **NOW:** сохранять raw metadata и прямой `short_video` признак.
4. **P1** [video/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/video/responses.json) — контейнеры ответов видео-методов. **NOW:** runtime validation и tolerant parsing.
5. **P1** [errors.json](https://github.com/VKCOM/vk-api-schema/blob/master/errors.json) — общий каталог кодов VK. **NOW:** повторять только временные ошибки.
6. **P1** [groups/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/groups/methods.json) — управляемые сообщества и `groups.getById`. **NOW:** подтверждать администрирование перед записью.
7. **P1** [groups/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/groups/responses.json) — актуальный контейнер `groups`. **NOW:** не полагаться на старую форму голого массива.
8. **P1** [base/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/base/responses.json) — общие response-типы. **NOW:** учитывать `1/true` и документировать расхождения.
9. **P2** [Schema vs documentation issue #209](https://github.com/VKCOM/vk-api-schema/issues/209) — подтверждение расхождений представлений документации. **NOW:** сохранять сырой ответ и покрывать предположения тестами.
10. **P2** [Wrong video.addToAlbum response issue #220](https://github.com/VKCOM/vk-api-schema/issues/220) — реальный пример неверной response-схемы. **NOW:** проверять postcondition через повторное чтение.
11. **P2** [Community token error issue #242](https://github.com/VKCOM/vk-api-schema/issues/242) — ограничения group auth. **NOW:** user token для текущего CLI.
12. **P1** [VK Java SDK](https://github.com/VKCOM/vk-java-sdk) — официальный SDK, генерируемый из схемы. **NEXT:** использовать для перекрёстной проверки новых методов.
13. **P1** [VK PHP SDK](https://github.com/VKCOM/vk-php-sdk) — официальный OAuth/API wrapper. **NEXT:** сверять scopes и action signatures.

### Вывод

Обычное поле описания VK Видео не имеет Markdown/HTML `parse_mode`. Следовательно, `*...*`, `_..._` и `~~...~~` должны превращаться в читаемый plain text **до** `video.save` или `video.edit`. Ответ write-метода не является достаточной проверкой — нужен повторный `video.get`.

---

## B. YouTube Data API и OAuth

14. **P1** [YouTube Data API reference](https://developers.google.com/youtube/v3/docs) — полный каталог ресурсов и методов. **NOW:** точные parts и минимальные запросы.
15. **P1** [Video resource](https://developers.google.com/youtube/v3/docs/videos) — структура snippet/status/contentDetails/statistics. **NOW:** сохранять только поддерживаемые mutable fields при update.
16. **P1** [Videos: list](https://developers.google.com/youtube/v3/docs/videos/list) — чтение до/после, стоимость 1 unit. **NOW:** verification reread и пакетное чтение ID.
17. **P1** [Videos: update](https://developers.google.com/youtube/v3/docs/videos/update) — обновление metadata, стоимость 50 units. **NOW:** не выполнять лишние повторные writes.
18. **P1** [Videos: insert](https://developers.google.com/youtube/v3/docs/videos/insert) — resumable upload и upload quota bucket. **NEXT:** только для будущего прямого издателя.
19. **P1** [Videos: delete](https://developers.google.com/youtube/v3/docs/videos/delete) — удаление и quota cost. **NO:** destructive operations остаются выключенными.
20. **P1** [YouTube API errors](https://developers.google.com/youtube/v3/docs/errors) — API-specific errors, включая quota/access. **NOW:** классификация terminal/retryable.
21. **P1** [Google API global errors](https://developers.google.com/youtube/v3/docs/core_errors) — общие HTTP/domain errors. **NOW:** ограниченный retry только для временных классов.
22. **P1** [Quota costs](https://developers.google.com/youtube/v3/determine_quota_cost) — стоимость операций. **NOW:** считать writes и не маскировать повторные update.
23. **P1** [YouTube API revision history](https://developers.google.com/youtube/v3/revision_history) — изменения методов и квот. **NEXT:** проверять перед крупными релизами.
24. **P1** [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2) — поддерживаемые OAuth-сценарии. **NOW:** desktop/installed app с локальным redirect.
25. **P1** [OAuth for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app) — loopback redirect и PKCE-контекст. **NOW:** не использовать устаревший OOB flow.
26. **P1** [OAuth security best practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices) — хранение client credentials и refresh tokens. **NOW:** локальный ignored token store, минимальные scopes.
27. **P1** [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies) — требования к authorization UX. **NOW:** не использовать embedded user-agent.
28. **P1** [OAuth scopes](https://developers.google.com/identity/protocols/oauth2/scopes) — каталог областей доступа. **NOW:** readonly/write aliases разделены явно.
29. **P1** [OOB migration](https://developers.google.com/identity/protocols/oauth2/resources/oob-migration) — отказ от copy/paste OOB. **NOW:** loopback flow.
30. **P1** [PlaylistItems: update](https://developers.google.com/youtube/v3/docs/playlistItems/update) — пропущенное поле может быть удалено. **NOW:** preserve-on-update и полное чтение mutable resource.

### Вывод

YouTube update дорогой по квоте и может стирать не переданные mutable fields. Значит обязательны `before` snapshot, минимальный ChangePlan, идемпотентный `already applied`, повторное чтение и запрет автоматического повторного execute после подтверждённого результата.

---

## C. Получение собственных YouTube-медиа

31. **P2** [yt-dlp repository](https://github.com/yt-dlp/yt-dlp) — основной extractor/downloader. **NOW:** pin/record version in operation logs.
32. **P2** [yt-dlp Installation](https://github.com/yt-dlp/yt-dlp/wiki/Installation) — официальные варианты установки и обновления. **NOW:** воспроизводимая установка, не случайный бинарник.
33. **P2** [yt-dlp FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ) — cookies, IP/header binding и типовые ошибки. **NOW:** cookies только для изолированной сессии и только при необходимости.
34. **P2** [YouTube PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) — современный ответ на часть HTTP 403. **NEXT:** автоматический provider, фиксированная версия, отдельный threat review.
35. **P2** [yt-dlp Plugins](https://github.com/yt-dlp/yt-dlp/wiki/Plugins) — plugin architecture. **NEXT:** allowlist provider plugins; не загружать произвольные плагины.
36. **P2** [yt-dlp Extractors](https://github.com/yt-dlp/yt-dlp/wiki/Extractors) — ограничения YouTube clients и cookies. **NOW:** не считать один client универсальным.
37. **P2** [yt-dlp releases](https://github.com/yt-dlp/yt-dlp/releases) — частые extractor fixes. **NEXT:** controlled update + regression test, не auto-latest перед write run.
38. **S** [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — рекомендуемый сообществом PO provider. **NEXT:** только после code review, pin SHA/version и sandboxed setup.

### Вывод

Для собственного архива приоритет источников: локальный мастер → Google Takeout → проверенный кэш → yt-dlp без cookies → PO provider → изолированные cookies. Основной аккаунт нельзя превращать в постоянный downloader credential.

---

## D. Media QC и контейнеры

39. **P1** [FFmpeg documentation index](https://ffmpeg.org/documentation.html) — актуальная документация toolchain. **NOW:** фиксировать версию в diagnostic output.
40. **P1** [ffprobe documentation](https://ffmpeg.org/ffprobe.html) — machine-readable inspection и exit codes. **NOW:** обязательный pre-upload QC.
41. **P1** [ffmpeg documentation](https://ffmpeg.org/ffmpeg.html) — декодирование, remux/transcode. **NOW:** отдельный deep decode check для подозрительных файлов.
42. **P1** [FFmpeg formats](https://ffmpeg.org/ffmpeg-formats.html) — containers/demuxers/muxers. **NEXT:** explicit allowlist при нормализации контейнеров.
43. **P1** [FFmpeg protocols](https://ffmpeg.org/ffmpeg-protocols.html) — протоколы и ограничения seek/IO. **NEXT:** не передавать временные signed URLs стороннему downloader без headers.
44. **P1** [libavformat](https://ffmpeg.org/libavformat.html) — container layer. **LATER:** только при переходе от subprocess к библиотечному worker.
45. **P1** [FFmpeg general capabilities](https://ffmpeg.org/general.html) — поддерживаемые форматы/codecs. **NEXT:** startup diagnostics.
46. **P1** [MediaInfo](https://mediaarea.net/en/MediaInfo) — независимое второе представление metadata. **NEXT:** optional cross-check для проблемных файлов.
47. **P1** [QCTools](https://mediaarea.net/QCTools) — визуальный QC. **LATER:** ручной анализ артефактов/уровней, не обязательный batch gate.

### Вывод

Расширение `.mp4` и ненулевой размер не доказывают пригодность. Минимальный gate: SHA-256, контейнер, video stream, audio stream, положительная duration, codecs и dimensions. Именно этот gate внедрён перед exact-ID upload и в safe wrapper.

---

## E. Python/Windows: процессы и атомарные файлы

48. **P1** [Python `os`](https://docs.python.org/3.11/library/os.html) — на Windows обычный `os.kill` вызывает `TerminateProcess`. **NOW:** никогда не использовать `os.kill(pid, 0)` как liveness probe в Windows.
49. **P1** [Python `subprocess`](https://docs.python.org/3.11/library/subprocess.html) — timeout, pipes, process termination. **NOW:** bounded timeouts и capture limits.
50. **P1** [Python `tempfile`](https://docs.python.org/3.11/library/tempfile.html) — безопасные временные файлы. **NEXT:** использовать для крупных generated artifacts.
51. **P1** [Python `pathlib`](https://docs.python.org/3.11/library/pathlib.html) — filesystem paths и `replace`. **NOW:** нормализованные абсолютные пути в logs.
52. **P1** [Python `hashlib`](https://docs.python.org/3.11/library/hashlib.html) — SHA-256. **NOW:** file/description/plan manifests.
53. **P1** [Python `json`](https://docs.python.org/3.11/library/json.html) — deterministic serialization требует явных separators/sort_keys. **NOW:** canonical plan digest.
54. **P1** [Python `ctypes`](https://docs.python.org/3.11/library/ctypes.html) — Win32 FFI. **NOW:** non-destructive process liveness probe.
55. **P1** [OpenProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess) — безопасное открытие process handle. **NOW:** `PROCESS_QUERY_LIMITED_INFORMATION`.
56. **P1** [GetExitCodeProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess) — `STILL_ACTIVE` liveness state. **NOW:** Windows writer lock.
57. **P1** [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights) — минимальные права process handle. **NOW:** не запрашивать terminate/all-access.

### Вывод

Старый Unix-паттерн `kill(pid, 0)` был опасен на Windows. Lock v2 использует Win32 query API, hostname/nonce, grace period для ещё не заполненного файла, атомарное quarantine stale-lock и ownership-safe release.

---

## F. Схемы, журнал и локальная БД

58. **P1** [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) — запрет нежелательного coercion. **NOW:** strict exchange models.
59. **P1** [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) — validation/serialization lifecycle. **NOW:** AuditPackage и ChangePlan.
60. **P1** [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/) — machine-readable contracts. **NOW:** versioned schemas.
61. **P1** [Pydantic mypy plugin](https://docs.pydantic.dev/latest/integrations/mypy/) — строгая типизация моделей. **NOW:** CI.
62. **P1** [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) — transaction boundaries. **NEXT:** перенос operation ledger из разрозненных mutable JSON в SQLite.
63. **P1** [SQLAlchemy Session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) — unit of work. **NEXT:** одна короткая transaction на переход состояния.
64. **P1** [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) — versioned DB migrations. **NEXT:** migration для operation ledger.
65. **P1** [SQLite WAL](https://sqlite.org/wal.html) — concurrent reads и serialized writes. **NEXT:** WAL + busy timeout для локального ledger.
66. **P1** [SQLite isolation](https://sqlite.org/isolation.html) — visibility/transaction isolation. **NEXT:** не смешивать remote write и долгую DB transaction.
67. **P1** [SQLite locking](https://sqlite.org/lockingv3.html) — filesystem locking model. **NEXT:** локальная БД не заменяет remote single-writer invariant.

### Вывод

JSON остаётся immutable evidence: snapshots, plans, backups, results. Текущее mutable состояние очереди следует постепенно перенести в SQLite ledger, не отказываясь от подписанных/хешированных JSON-артефактов.

---

## G. HTTP, retry и rate limiting

68. **P1** [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/) — connect/read/write/pool timeout. **NOW:** ни одного бесконечного сетевого ожидания.
69. **P1** [HTTPX transports](https://www.python-httpx.org/advanced/transports/) — connect retries и MockTransport. **NOW:** deterministic API tests; application retries отдельно.
70. **P1** [Tenacity documentation](https://tenacity.readthedocs.io/en/stable/) — bounded retry/backoff/jitter. **NOW:** retry только для явно временных ошибок.
71. **P1** [Tenacity API](https://tenacity.readthedocs.io/en/stable/api.html) — stop/wait/retry predicates. **NOW:** central retry policy вместо scattered sleep loops.

### Вывод

Retry не должен охватывать validation, access denied, invalid token, wrong channel, before-state conflict или content review error. Повторяются только transient HTTP/API classes с верхней границей попыток и времени.

---

## H. Тестирование и качество

72. **P1** [pytest fixtures](https://docs.pytest.org/en/stable/reference/fixtures.html) — `tmp_path`, `monkeypatch`. **NOW:** filesystem/process tests без live API.
73. **P1** [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — scoped patching. **NOW:** Windows dispatch и subprocess tests.
74. **P1** [pytest tmp_path](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — isolated filesystem. **NOW:** lock/journal tests.
75. **P1** [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html) — model-based state machines. **NEXT:** transitions `planned→reserved→uploaded→verified/failed`.
76. **P1** [Ruff configuration](https://docs.astral.sh/ruff/configuration/) — lint/format config. **NOW:** correctness and formatting gates.
77. **P1** [Ruff rules](https://docs.astral.sh/ruff/rules/) — rule catalogue. **NEXT:** gradually add UP/SIM/RUF, not one disruptive switch.
78. **P1** [mypy configuration](https://mypy.readthedocs.io/en/stable/config_file.html) — strict typing. **NOW:** source package strict mode.
79. **P1** [pre-commit](https://pre-commit.com/) — local hooks. **NEXT:** Ruff, whitespace, secret scan before commit.
80. **P1** [pip-audit](https://github.com/pypa/pip-audit) — Python vulnerability audit. **NOW:** CI informational first, then blocking with documented exceptions.
81. **P2** [Gitleaks](https://github.com/gitleaks/gitleaks) — secret scanning. **NOW:** repository/history scan and pre-commit/CI.

---

## I. GitHub Actions и supply-chain безопасность

82. **P1** [Security for GitHub Actions](https://docs.github.com/en/actions/how-tos/secure-your-work) — минимальные permissions, untrusted input, OIDC. **NOW:** preserve `contents: read`, no platform tokens in CI.
83. **P1** [Security concepts](https://docs.github.com/en/actions/concepts/security) — secrets, token, injection, runners. **NOW:** no live YouTube/VK mutation workflows.
84. **P1** [Dependency review action](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-dependency-review-action) — block vulnerable additions. **NEXT:** PR workflow where repository plan permits.
85. **P1** [Artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations) — provenance for distributable artifacts. **LATER:** when publishing binaries/packages, not every test log.
86. **P1** [Using artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations) — signing workflow. **LATER:** release pipeline.
87. **P1** [Dependency caching security](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching) — restored cache is untrusted input. **NOW:** cache only dependencies, never credentials/reports.
88. **P1** [Secret scanning](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning) — leaked credential alerts. **NOW:** enable where available plus Gitleaks fallback.
89. **P1** [Dependabot alerts](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-alerts) — vulnerable dependency notifications. **NEXT:** controlled version updates with CI.

---

## J. Наблюдаемость, backup и orchestration

90. **P1** [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/) — traces/metrics stable, logs evolving. **NEXT:** trace IDs for long transfer runs.
91. **P1** [OpenTelemetry instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/) — manual spans/metrics. **NEXT:** download/upload/verification spans without description bodies or tokens.
92. **P1** [OpenTelemetry metrics](https://opentelemetry.io/docs/concepts/signals/metrics/) — counters/histograms. **NEXT:** attempts, latency, retry count, failure class.
93. **P1** [Prometheus Python instrumentation](https://prometheus.github.io/client_python/instrumenting/) — counters/gauges/histograms. **LATER:** only when there is a persistent service.
94. **P1** [Prometheus HTTP exporter](https://prometheus.github.io/client_python/exporting/http/) — metrics endpoint. **LATER:** not needed for occasional CLI runs.
95. **P1** [Sentry Python](https://docs.sentry.io/platforms/python/) — exceptions and tracing. **NEXT:** optional, with aggressive PII/token scrubbing.
96. **P1** [restic introduction](https://restic.readthedocs.io/en/stable/010_introduction.html) — encrypted content-addressed backups. **NEXT:** backups of DB/reports/config, excluding tokens unless separately protected.
97. **P1** [restic troubleshooting/check](https://restic.readthedocs.io/en/stable/077_troubleshooting.html) — `check --read-data` and repair workflow. **NEXT:** scheduled integrity verification.
98. **P1** [restic retention](https://restic.readthedocs.io/en/latest/060_forget.html) — forget/prune policy. **NEXT:** conservative retention and check after prune.
99. **P1** [restic scripting](https://restic.readthedocs.io/en/stable/075_scripting.html) — JSON/exit codes. **NEXT:** machine-readable backup task.
100. **P1** [rclone documentation](https://rclone.org/docs/) — cloud backends and transfer options. **NEXT:** storage transport beneath restic or separate archive copy.
101. **P1** [rclone sync](https://rclone.org/commands/rclone_sync/) — destructive mirror semantics. **NO by default:** prefer `copy`; use sync only with retention/versioning.
102. **P1** [Prefect tasks](https://docs.prefect.io/v3/concepts/tasks) — retries, caching, concurrency. **LATER:** after SQLite ledger and stable idempotent tasks.
103. **P1** [Prefect caching](https://docs.prefect.io/v3/concepts/caching) — cache keys/result persistence/file locks. **LATER:** media/task cache with content hashes.
104. **P1** [Prefect retries](https://docs.prefect.io/v3/how-to-guides/workflows/retries) — retry predicates. **LATER:** replace home-grown orchestration only when operational value is clear.
105. **P1** [APScheduler user guide](https://apscheduler.readthedocs.io/en/master/userguide.html) — local recurring jobs. **NEXT:** read-only audit/backup schedule; no unattended remote writes.

---

# Принятый технологический порядок

## Внедрено в текущем hardening-цикле

```text
Windows-safe single-writer lock
VK-native plain-text publication policy
ffprobe A/V QC
SHA-256 media manifest
self-validating cleanup plan v2
full live-ID coverage verification
before/after conflict detection
postflight verification
backup + guarded rollback
```

## Следующий небольшой слой

```text
pip-audit + pip check + Gitleaks
operation-state transition tests
SQLite operation ledger
structured JSON logging
restic backup runbook
```

## После стабилизации

```text
PO Token provider with pinned version
Hypothesis state-machine tests
OpenTelemetry/Sentry without content bodies
scheduled read-only audits
controlled dependency updates
```

## Пока не внедрять

```text
unattended YouTube/VK writes
Temporal/Celery/Redis cluster
Prometheus/Grafana stack for occasional CLI
arbitrary yt-dlp plugins
cookies of the main channel as default downloader identity
rclone sync without remote versioning/retention
```

# Архитектурный вывод

Проект должен оставаться safety-first modular monolith:

```text
live snapshot
→ validated immutable plan
→ human-readable diff
→ exact confirmations
→ single-writer lock
→ locked re-preflight
→ journaled operation
→ remote postcondition
→ full batch postflight
→ immutable result / guarded rollback
```

Orchestrator, dashboards и distributed queue не исправляют отсутствующую идемпотентность. Сначала доказывается корректность каждого перехода состояния; только затем имеет смысл масштабировать исполнение.
