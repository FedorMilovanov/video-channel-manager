# Unified YouTube + VK integration status

Дата сборки: **2026-07-25**  
Интеграционная ветка: `integration/youtube-vk-unified-v2`  
Итоговый PR: **#13**  
Статус: **draft; remote platform writes не выполнялись**.

## История

Единая ветка создана из последнего зелёного VK hardening head:

```text
c2b0c9d1de2e160691b587eb2f0dea7546c13fe0
```

Поверх него обычным merge-коммитом добавлена полная актуальная история YouTube hardening head:

```text
7d119cd79c3f5cd2a6dcea9a3cc572a3ae5a2b91
```

После первичной сборки выяснилось, что read-only VK branch получила три более поздних коммита уже после создания дочерней rendering-ветки. Её актуальный head:

```text
da208e81fdc4b2dc895d6471b3e5ff5b0be9caa8
```

добавлен вторым родителем merge-коммита:

```text
c9e455a82e232dde931c5b0a3a35369e4f2ea0ca
```

Tree merge-коммита оставлен равным уже проверенному unified tree: более новые exact-ID resume и thumbnail hardening не откатывались, но поздняя история PR #7 теперь также входит в ancestry.

GitHub compare для heads PR #7, #8, #9 и #10 показывает:

```text
status: ahead
behind_by: 0
```

Это означает, что unified branch является потомком всех четырёх рабочих линий и не потеряла их коммиты.

## Проверенное наличие контуров

### YouTube

- `src/video_channel_manager/platforms/youtube/copy_plan.py` — self-validating plan schema v3;
- `src/video_channel_manager/platforms/youtube/write_lock.py` — Windows-safe per-channel lock;
- `scripts/apply_youtube_copy_plan_v3.py` — strict executor;
- `scripts/recover_youtube_copy_apply.py` — guarded recovery;
- `scripts/validate_youtube_copy_plan.py` — offline integrity check.

### VK

- `src/video_channel_manager/platforms/vk/live_description_audit.py` — whole-library plan schema v2;
- `src/video_channel_manager/platforms/vk/lock.py` — Windows-safe per-community lock;
- `scripts/apply_all_vk_description_cleanup.py` — locked whole-library executor;
- `scripts/resume_youtube_to_vk_exact_ids.py` — exact-ID transfer with media manifest;
- `scripts/sync_youtube_thumbnails_to_vk.py` — thumbnail manifest and image QC.

### Общий слой

- CLI одновременно регистрирует `youtube`, `vk` и `compare`;
- `setuptools>=83,<84` закрывает обнаруженную packaging vulnerability;
- `pip-audit` входит в обязательный CI gate;
- GitHub Actions pinned по commit SHA;
- Ruff formatting применён ко всему объединённому дереву одним механическим commit;
- одноразовый formatting workflow удалён тем же commit.

## CI доказательство

На unified tree полностью прошли GitHub Actions runs:

```text
335 — Python 3.11 / 3.12 / 3.13: success
337 — merge-head с полной ancestry: Python 3.11 / 3.12 / 3.13: success
```

Каждая версия прошла:

```text
pip check
compileall
pip-audit
ruff check
ruff format --check
mypy
pytest --cov
```

Final gate не запускался как failure; он был корректно skipped, поскольку все individual outcomes были успешными.

## Текущее правило

- PR #13 остаётся draft до отдельного решения о целевой base/main strategy;
- исходные PR #7–#10 могут быть закрыты без merge как superseded by #13;
- слияние в `main` без отдельного явного решения запрещено;
- live YouTube/VK execute не запускается из integration branch автоматически;
- старые backups/results сохраняются независимо от Git;
- перед любой новой platform mutation создаётся свежий snapshot и новый plan соответствующей schema.
