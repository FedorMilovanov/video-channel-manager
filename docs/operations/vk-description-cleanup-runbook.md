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

Внешние или исходные YouTube-ссылки, для которых нет точного собственного VK-соответствия, сохраняются. В текущем плане остаются четыре такие ссылки: две ссылки на исходный материал «Шабаш» группы АЛИСА и две ссылки на источник KINO для `Calm Night`.

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

Текущий порядок:

1. выполнить и применить отдельный косметический title patch;
2. заново построить descriptions-only план на новом snapshot;
3. выполнить свежий dry-run описаний;
4. проверить единый ZIP;
5. выполнить descriptions execute только из этого проверенного ZIP.

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

В Проводнике автоматически выделяется ZIP. Оператор отправляет только его. Execute-helper также принимает этот ZIP как источник истины и не требует искать JSON вручную.

## 5. Косметический title patch

Dry-run одной командой:

```powershell
pwsh -File .\scripts\Invoke-VkCosmeticTitlePatch.ps1
```

Wrapper сам берёт snapshot из последнего `vk-description-wave-dry-run-*.zip` или успешного title-wave ZIP, строит новый title-only plan и требует ровно три косметические операции:

- удалить декоративные `《》` у китайского названия;
- `Шабаш - Алиса Cover` → `Шабаш ⚡ АЛИСА Cover`;
- `Внимая Ужасам Войны... - Николай Некрасов` → `Внимая Ужасам Войны... ⚡ Николай Некрасов`.

Ни одна semantic-label метка не меняется. После проверки dry-run ZIP execute выполняется тем же helper с явным `-Execute`; helper извлекает и проверяет подписанный план из ZIP.

## 6. Новый dry-run описаний

После успешного применения косметических названий:

```powershell
pwsh -File .\scripts\Invoke-VkDescriptionWave.ps1
```

Default-режим:

- строит новый descriptions-only plan;
- открывает HTML «До / После»;
- выполняет полный live preflight;
- не вызывает mutation API;
- создаёт один ZIP.

Разрешённый результат:

```text
ready: N
already applied: 0
conflicts: 0
review-only excluded: 0
Dry-run only. No VK mutation method was called.
```

Текущий проверенный dry-run от `2026-07-27 16:45:35` содержит:

```text
ready: 111
already applied: 0
conflicts: 0
review-only excluded: 0
plan SHA-256: sha256:b4eede44954bcb148550bcb2c0a372e4f23b72d892cc3aadcc5d71321a2e9294
```

Source snapshot побайтно совпадает с final snapshot успешного косметического title apply. Все 111 title guards и membership coverage совпадают с live preflight.

## 7. Выполнение описаний

После внешней проверки ZIP используется отдельный reviewed execute-helper:

```powershell
pwsh -File .\scripts\Invoke-VkReviewedDescriptionWave.ps1 -Execute
```

Он автоматически выбирает последний `vk-description-wave-dry-run-*.zip` и до вызова writer проверяет:

- `status=dry_run_completed` и `mode=dry-run`;
- `component_scope=descriptions_only`;
- exact community и expected operation count;
- `ready=N`, `already_applied=0`, `conflicts=0`;
- размер и SHA-256 каждого обязательного файла по `manifest.json`;
- совпадение manifest plan SHA и embedded plan SHA;
- exact source snapshot identity;
- нулевые изменения названий, альбомов и каталога;
- `description_changed=true` и `semantic_body_preserved=true` во всех операциях;
- byte-identical текущую и проверенную editorial policy.

После этого helper передаёт извлечённые plan и source snapshot основному wrapper. Основной wrapper делает новый live preflight и берёт фактическое количество `ready`. Executor затем требует точные:

- community ID;
- ready count;
- plan SHA-256;
- video coverage SHA-256;
- membership-state SHA-256.

После single-writer lock preflight повторяется непосредственно перед первой записью.

## 8. Read-only отказ VK API 204

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

Диагностика независимо проверяет:

- текущую личность токена через `users.get`;
- личное право `video.get`;
- наличие сообщества среди управляемых;
- доступ к видеотеке конкретного сообщества.

Команда повторного входа предлагается только при фактической проблеме токена или permissions. До полного успешного live preflight мутации запрещены.

## 9. Обязательные postconditions

Успешное завершение требует одновременно:

```text
status = completed
ready after apply = 0
conflicts after apply = 0
memberships SHA-256 unchanged
```

Writer передаёт в `video.edit` только реально изменяемое поле. При description-only операции `name` не отправляется.

## 10. Запрещённые действия

- не добавлять `-Execute` к свежему автоматически построенному плану;
- не выполнять непроверенный dry-run ZIP;
- не редактировать VK Studio параллельно;
- не запускать второй VK writer;
- не менять JSON plan вручную;
- не использовать старый dry-run после изменения любого exact-before названия;
- не считать ответ API достаточным доказательством без повторного provider read;
- не переиспользовать SHA, count или snapshot из старого чата.

## 11. Источник истины

Приоритет имеют:

1. live snapshot;
2. signed plan;
3. plan SHA-256;
4. dry-run ZIP;
5. result journal;
6. final snapshot.

Operational artifacts имеют приоритет над памятью чата.
