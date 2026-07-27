# Техническая волна описаний VK Видео — операционный регламент

Канал: **The Legendary Poet**  
Сообщество: `235216998`

Назначение: безопасно очистить технические элементы описаний всей текущей VK-видеотеки, сохранив содержательный текст каждого ролика.

## 1. Основной принцип

Очистка строится из фактического live-текста VK:

```text
live VK before
→ deterministic technical cleanup
→ semantic-body equality gate
→ signed descriptions-only plan
→ HTML/Markdown review
→ live dry-run
→ explicit execute from reviewed ZIP
```

Разрешены только доказуемые технические изменения:

- замена YouTube-плейлистов на точные VK album `share_url`;
- замена известных собственных YouTube-ссылок на точные VK Video URL;
- снятие видимых Markdown-маркеров;
- удаление zero-width символов;
- нормализация переносов, пробелов и декоративных разделителей;
- удаление старого footer и добавление канонического footer;
- ограничение числа хэштегов.

Внешние, исходные или общие YouTube-ссылки, для которых нет точного собственного VK-соответствия, сохраняются. В завершённой волне осталось пять таких ссылок: две ссылки на исходный материал «Шабаш» группы АЛИСА, две ссылки на источник KINO для `Calm Night` и одна общая ссылка на страницу плейлистов The Legendary Poet.

Запрещены автоматические изменения фактов, интерпретации, содержательной пунктуации и порядка смысловых фраз.

## 2. Semantic-body gate

Для каждого описания вычисляется содержательное представление без URL, hashtags, известных footer-строк, Markdown-маркеров, декоративных линий, whitespace и zero-width символов.

```text
semantic_body(before) == semantic_body(after)
```

Если равенство нарушено хотя бы для одного видео, построение всей волны завершается ошибкой до dry-run.

Фактологические и чувствительные маркеры не переписываются. Они попадают в `deferred_editorial_review` только как будущая редакционная очередь.

## 3. Взаимодействие с названиями

Descriptions-only план хранит exact-before название каждого видео. Поэтому любые косметические изменения названий должны быть завершены до финального dry-run описаний.

Семантические ярлыки названий (`SHORTS`, `КОРОТКАЯ`, `ФРАГМЕНТ`, `НЕПОЛНЫЙ`, `ПОЛНАЯ`, `БОЛЕЕ ПОЛНАЯ`, `ФИНАЛЬНАЯ`, номера версий) нельзя выводить из длительности, ориентации кадра или наличия парного ролика. Они заморожены отдельной title-policy.

## 4. Один файл вместо поиска артефактов

Все wrappers создают ZIP в `finally`. ZIP содержит доступные на момент завершения:

- source snapshot;
- signed JSON plan;
- Markdown review;
- HTML review;
- editorial policy;
- live preflight;
- apply log;
- result journal;
- final snapshot;
- README;
- manifest с SHA-256 и размером каждого файла.

В Проводнике автоматически выделяется ZIP. Оператор отправляет только его.

## 5. Завершённый dry-run

Проверенный dry-run от `2026-07-27 16:45:35` содержал:

```text
ready: 111
already applied: 0
conflicts: 0
review-only excluded: 0
plan SHA-256: sha256:b4eede44954bcb148550bcb2c0a372e4f23b72d892cc3aadcc5d71321a2e9294
```

Source snapshot побайтно совпадал с final snapshot успешного косметического title apply. Все 111 title guards и membership coverage совпали с live preflight.

## 6. Завершённый apply

Apply от `2026-07-27 19:29:11` выполнил:

```text
operations: 111
updated_and_verified: 111
result status: completed
final descriptions matching reviewed after-state: 111
```

Независимая проверка подтвердила:

- 111 видео до и после;
- 111 изменённых описаний;
- 0 изменённых названий;
- 17 неизменённых альбомов;
- 294 неизменённых memberships;
- неизменный membership SHA-256 `sha256:bdb556321dce7b5dd9400de33c92fb186dce55faac327f0a5a077491bfd5b966`;
- все файлы ZIP совпали с manifest по размеру и SHA-256;
- все новые описания имеют канонический footer, не более 10 хэштегов и длину не более 5000 символов.

Внешний wrapper записал `status=failed` только потому, что дополнительный read-only scan после успешного writer postflight упал при печати Unicode-стрелки в legacy Windows console. Итоговый snapshot был полностью записан до console exception и прошёл независимую проверку.

## 7. Независимый verifier apply-ZIP

Для повторной машинной проверки используется:

```powershell
py -3.11 -X utf8 .\scripts\verify_vk_description_apply_bundle.py `
  .\data\handoffs\vk-description-wave-apply-YYYYMMDD-HHMMSS.zip
```

Verifier проверяет:

- размеры и SHA-256 manifest;
- `03-result.json status=completed`;
- operation IDs и допустимые operation statuses;
- точные reviewed after-title и after-description всех роликов;
- отсутствие title changes;
- неизменность video inventory, album titles и memberships;
- video coverage SHA-256;
- membership SHA-256;
- semantic-body guards.

Он умеет отличить успешный writer/result/final-state от последующего несущественного wrapper-output failure.

## 8. Следующий этап: deferred editorial review

Следующий этап является строго review-only:

```powershell
pwsh -File .\scripts\Invoke-VkDeferredEditorialReview.ps1
```

Helper:

1. автоматически берёт последний apply-ZIP описаний;
2. пропускает его через независимый verifier;
3. извлекает 148 отложенных маркеров по 96 роликам;
4. создаёт JSON, Markdown и HTML с полными текущими описаниями;
5. создаёт один ZIP `vk-deferred-editorial-review-*.zip`;
6. не вызывает VK mutation API и не создаёт correction plan.

В очереди:

```text
factual_editorial_review: 96
sensitive_claim_review: 52
remote writes: 0
```

Любые реальные исправления после этой очереди должны строиться отдельными reviewed correction-планами с точными source citations. Наличие маркера само по себе не означает, что текст ошибочен.

## 9. Read-only отказ VK API 204

Если VK возвращает точный ответ:

```text
VK API 204 in video.get: Access denied
```

до появления preflight counts, запись не начиналась. Reviewed helper:

1. повторяет только этот точный read-only отказ не более трёх раз;
2. использует увеличивающуюся паузу;
3. не открывает Проводник для внутренних неудачных попыток;
4. не повторяет plan, writer, validation или другие ошибки;
5. при устойчивом отказе запускает `diagnose_vk_video_access.py`.

До полного успешного live preflight мутации запрещены.

## 10. Обязательные postconditions

Успешное завершение требует одновременно:

```text
result status = completed
all operations = updated_and_verified or already_applied
final reviewed after-state = exact
memberships SHA-256 unchanged
```

Writer передаёт в `video.edit` только реально изменяемое поле. При description-only операции `name` не отправляется.

## 11. Запрещённые действия

- не выполнять непроверенный dry-run ZIP;
- не редактировать VK Studio параллельно;
- не запускать второй VK writer;
- не менять JSON plan вручную;
- не считать декоративный console-output источником истины;
- не считать ответ API достаточным доказательством без повторного provider read;
- не переиспользовать SHA, count или snapshot из старого чата.

## 12. Источник истины

Приоритет имеют:

1. live snapshot;
2. signed plan;
3. plan SHA-256;
4. result journal;
5. final snapshot;
6. независимый verifier;
7. handoff manifest.

Operational artifacts имеют приоритет над памятью чата и декоративным CLI output.
