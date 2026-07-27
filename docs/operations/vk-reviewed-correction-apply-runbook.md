# VK reviewed correction P1 — guarded apply

Канал: **The Legendary Poet**  
Сообщество: `235216998`

## Scope

Первая correction-only волна разрешает изменить ровно три описания «Исповедь Самоубийцы»:

- `-235216998_456239046`;
- `-235216998_456239047`;
- `-235216998_456239050`.

Разрешены только две reviewed replacements:

1. `1912 г.` → `1913–1915 гг. (предположительная датировка академического издания)`;
2. духовный вывод, согласованный с `PROJECT_CHARTER.md`, богословскими правилами The Legendary Poet, утверждённым профилем Есенина и Research.

Названия, остальные 108 описаний, альбомы, memberships, состав видеотеки, ссылки, хэштеги, footer и текст стихотворения заморожены.

## Проверенный dry-run

Перед execute ZIP должен независимо пройти `scripts/verify_vk_reviewed_correction_dry_run.py`.

Проверяются:

- manifest sizes и SHA-256;
- самоподпись `plan.json`;
- `policy_sha256` и `decisions_sha256`;
- вложенный source review ZIP и его manifest;
- редакционный профиль `the-legendary-poet-historical-evangelical-v1`;
- три точных VK ID;
- две точных замены;
- источники ФЭБ, The Legendary Poet и Research;
- source snapshot: 111 видео, 17 коллекций, 294 memberships;
- live dry-run: `ready=3`, `already applied=0`, `conflicts=0`, `remote writes=0`.

## Execute

```powershell
pwsh -File .\scripts\Invoke-VkReviewedCorrectionApply.ps1 -Execute
```

Helper:

1. выбирает последний `vk-reviewed-correction-p1-dry-run-*.zip`;
2. независимо проверяет его до распаковки;
3. повторяет свежий live preflight;
4. допускает безопасное продолжение, когда часть операций уже `already_applied`;
5. требует `ready + already_applied = 3` и `conflicts = 0`;
6. передаёт writer точные guards community, ready count, plan SHA-256, video coverage и memberships SHA-256;
7. пишет result journal;
8. выполняет свежий read-only VK scan;
9. создаёт один apply ZIP;
10. независимо проверяет финальный ZIP, добавляет embedded verification и проверяет ZIP ещё раз.

## Postflight invariants

Apply verifier доказывает:

- три target descriptions точно равны reviewed after-state;
- все три названия неизменны;
- остальные 108 названий и описаний неизменны;
- видео inventory остаётся 111;
- collection inventory и titles остаются 17 и неизменны;
- memberships остаются 294 и в том же порядке/составе;
- video coverage и membership SHA-256 совпадают с reviewed plan;
- result journal содержит только `updated_and_verified` или `already_applied`;
- previous reviewed dry-run повторно проходит независимую проверку.

## One-file handoff

Итоговый файл:

```text
data\handoffs\vk-reviewed-correction-p1-apply-YYYYMMDD-HHMMSS.zip
```

Внутри:

- `00-source-vk-snapshot.json`;
- `01-preflight.txt`;
- `02-apply.txt`;
- `03-result.json`;
- `04-final-vk-snapshot.json`;
- `05-independent-verification.json`;
- `plan.json`;
- `reviewed-decisions.json`;
- `plan-review.md` и `plan-review.html`;
- `previous-reviewed-dry-run.zip`;
- `source-review-bundle.zip`;
- `dry-run-verification.json`;
- `manifest.json` и `README.txt`.

## Failure and resume

Если read-only `video.get` временно возвращает error 204, повторяется только preflight. Execute автоматически не повторяется после начала записей.

При внешнем сбое helper всё равно создаёт один ZIP со всеми доступными журналами. Повторный запуск безопасен: live preflight классифицирует уже применённые операции как `already_applied`, а writer продолжает только оставшиеся `ready` операции.

Нельзя редактировать эти три описания вручную в VK Studio параллельно с helper.
