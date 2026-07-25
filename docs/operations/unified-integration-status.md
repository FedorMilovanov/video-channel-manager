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

GitHub compare после интеграции показывает для обеих исходных heads:

```text
status: ahead
behind_by: 0
```

Это означает, что unified branch является потомком обеих линий и не потеряла их коммиты.

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
- удалён одноразовый formatting workflow.

## CI критерии готовности

Каждая версия Python 3.11, 3.12 и 3.13 должна пройти:

```text
pip check
compileall
pip-audit
ruff check
ruff format --check
mypy
pytest --cov
```

До одновременного зелёного результата всех jobs:

- PR #13 остаётся draft;
- исходные PR #7–#10 не считаются заменёнными окончательно;
- слияние в `main` запрещено;
- live YouTube/VK execute не запускается из integration branch.

## После зелёного CI

1. Зафиксировать exact unified head и run ID.
2. Убедиться, что PR #13 остаётся mergeable.
3. Пометить PR #7–#10 как superseded by #13 либо закрыть без merge.
4. Сохранить старые локальные backups/results независимо от Git.
5. Перед любой новой platform mutation создать свежий snapshot и новый plan соответствующей schema.
