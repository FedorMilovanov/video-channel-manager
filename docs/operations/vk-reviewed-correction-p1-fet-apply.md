# VK reviewed correction P1 — Фет — guarded apply

Канал: **The Legendary Poet**  
Сообщество: `235216998`

## Назначение

Этот helper выполняет только ранее построенный и независимо проверенный dry-run:

```text
vk-reviewed-correction-p1-fet-dry-run-*.zip
```

Decision set:

```text
p1-fet-whisper-20260727
```

Целевые видео:

```text
-235216998_456239127
-235216998_456239143
```

Execute-helper не строит новый план, не пересчитывает формулировки и не расширяет scope. Он извлекает точный подписанный `plan.json` из dry-run ZIP.

## Проверенные данные dry-run

Независимо проверены два внешних ZIP-представления одного и того же точного набора внутренних файлов:

```text
исходный локальный ZIP:
sha256:0f8020fd76456f8b6490e17e2142d46ca8f18f397ded400c3c093bbf719539f5

загруженная копия ZIP:
sha256:8e173fba66cc0b298d1d87db384cb6a15e60c0c8d36c45db4ebb3e580a2221b9
```

Различие внешнего SHA возможно из-за упаковки ZIP. Допуск определяется не именем и не одним container SHA, а полным точным совпадением состава, размеров и SHA-256 каждого внутреннего файла.

Ключевые подписи содержимого:

```text
plan SHA-256:
sha256:095c0a1cce72a46eaee0a1ea37ca2e2ee6a682bbf393f3d02d6d7abece1872ec

decisions SHA-256:
sha256:ac13aaf20358d42db1808bcda46dd2a04fffc6c56abc85d6b3246fb10b3cd2d0

source Esenin apply ZIP SHA-256:
sha256:af11d5c882d8068b316b606723410f6d45bda49d5dd327c92dc011b265f23398

source deferred-review ZIP SHA-256:
sha256:f38191f18d859ef2bcd445f558204ac76e3c3ebbe4f6414cb3436542df7b4c61
```

Dry-run состояние:

```text
ready: 2
already_applied: 0
conflicts: 0
remote_writes: 0
```

Canonical guard-хэши используют проектный `text_sha256`, а не raw SHA байтов:

```text
-235216998_456239127: sha256:eb10b7f1e529c26c240dada4116d2a9666b33bb4e0e167839ad3f9762e959203
-235216998_456239143: sha256:76c74c96f9aaa93d952531094d42c4b7a168f901566688bd349febd8b7b0c6b9
```

## Разрешённые изменения

- ровно два описания «Шёпот, робкое дыханье…»;
- датировка 1850 года;
- точная атрибуция критики Чернышевского;
- разграничение факта, биографического фона и исследовательской гипотезы;
- исправление утверждений о Марии Лазич и поздней любовной лирике;
- атрибуция последних часов Фета воспоминаниям Е. В. Кудрявцевой;
- удаление одного оборванного фрагмента footer.

## Заморожено

- все 111 названий;
- остальные 109 описаний;
- 17 коллекций и их названия;
- 294 пары `(collection_id, video_id)`;
- состав из 111 видео;
- ссылки, хэштеги, текст стихотворения и музыкальная рамка.

## Перед execute

Helper независимо проверяет dry-run и требует:

```text
status: verified_dry_run
artifact_review: exact_independently_reviewed_contents
operations: 2
ready + already_applied: 2
conflicts: 0
remote_writes: 0
canonical_text_hashes_verified: true
reviewed_replacements_reconstructed: true
urls_and_hashtags_unchanged: true
exact_member_hashes_verified: true
```

Verifier повторно доказывает:

1. ZIP содержит точный обязательный набор файлов без дубликатов entries;
2. размер и SHA-256 каждого внутреннего файла совпадают с независимо одобренными значениями;
3. `plan.json` имеет корректную самоподпись и точный plan SHA-256;
4. decisions имеют точный canonical SHA-256 и guard algorithm `video-manager.text-sha256-v1`;
5. оба before-state совпадают с source snapshot и canonical description guards;
6. каждый из пяти reviewed replacements встречается ровно один раз и применяется в заданном порядке;
7. after-state целиком воспроизводится только этими заменами;
8. URL и хэштеги до и после полностью совпадают;
9. preflight доказывает `ready: 2`, `conflicts: 0` и отсутствие VK mutation call.

После этого проводится новый live read-only preflight. Execute разрешается только при совпадении:

- community ID;
- числа ready-операций;
- SHA-256 плана;
- SHA-256 покрытия 111 видео;
- SHA-256 membership identity.

## Запуск

Закрыть ручное редактирование двух роликов в VK Studio.

```powershell
pwsh -File .\scripts\Invoke-VkReviewedCorrectionFetApply.ps1 -Execute
```

Результат:

```text
data\handoffs\vk-reviewed-correction-p1-fet-apply-YYYYMMDD-HHMMSS.zip
```

## Postflight

Независимый verifier проверяет:

1. manifest, размеры и SHA-256 всех файлов;
2. предыдущий Fet dry-run целиком;
3. самоподпись `plan.json` и digest decisions;
4. ровно два target ID;
5. result journal со статусами `updated_and_verified` или `already_applied`;
6. точное совпадение двух финальных описаний с reviewed after-state;
7. неизменность остальных 109 описаний;
8. неизменность всех 111 названий;
9. неизменность 17 коллекций и 294 membership identity pairs;
10. обязательные подтверждённые формулировки и отсутствие запрещённых прежних утверждений.

Колебания поля `position` при неизменных membership identity pairs фиксируются отдельно как read-order metadata и не маскируют реальные добавления, удаления или перемещения между коллекциями.

## Возобновление

Повторный запуск безопасен только с dry-run ZIP, внутренние файлы которого полностью совпадают с независимо одобренным набором. Уже применённые операции должны получить `already_applied`; writer не отправляет их повторно.

## Ошибка

При ошибке helper создаёт **диагностический apply ZIP**, а не объявляет волну завершённой. Повторный `-Execute` запрещён до проверки result journal и финального snapshot: запись могла успеть завершиться до ошибки wrapper или postflight.
