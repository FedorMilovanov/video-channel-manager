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
operations: 2
ready + already_applied: 2
conflicts: 0
remote_writes: 0
```

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

Повторный запуск безопасен только с тем же проверенным dry-run ZIP. Уже применённые операции должны получить `already_applied`; writer не отправляет их повторно.

## Ошибка

При ошибке helper создаёт **диагностический apply ZIP**, а не объявляет волну завершённой. Повторный `-Execute` запрещён до проверки result journal и финального snapshot: запись могла успеть завершиться до ошибки wrapper или postflight.
