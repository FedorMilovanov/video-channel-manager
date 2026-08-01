# Стандарт описаний VK Видео

Канал: **The Legendary Poet**  
Project key: `legendary-poet`  
Статус: обязательный платформенный профиль для переноса YouTube → VK и очистки существующей библиотеки

Точные идентификаторы и ссылки проекта находятся в [`operations/project-identity-registry.md`](operations/project-identity-registry.md) и [`operations/legendary-poet-description-profile.md`](operations/legendary-poet-description-profile.md). При расхождении эти файлы имеют приоритет.

## 1. Базовый факт

Обычное описание видеозаписи VK хранится и отображается как простой текст. Поля `description` метода `video.save` и `desc` метода `video.edit` принимают строку, но не предоставляют режим Markdown или HTML.

Поэтому YouTube-разметка:

```text
*жирное*
_курсив_
~~зачёркнутое~~
```

в описании VK Видео отображается буквально вместе с `*`, `_` и `~`.

Это правило относится именно к обычным описаниям VK Видео. VK Видео Live, VK WorkSpace и другие продукты могут иметь собственные независимые режимы оформления; их нельзя переносить на поле `video.description`.

## 2. Точная идентичность проекта

```text
project_key: legendary-poet
YouTube channel ID: UC-78ys2S3cQ3lpqgXfo-SvQ
VK community ID: 235216998
VK owner ID: -235216998
```

Публичные маршруты:

- сайт: https://thelegendarypoet.ru/
- Telegram: https://t.me/thelegendarypoet
- канонический VK: https://vk.ru/thelegendarypoet
- совместимый VK: https://vk.com/thelegendarypoet
- VK Клипы: https://vkvideo.ru/@thelegendarypoet/clips
- RUTUBE: https://rutube.ru/channel/74579453/

Канонический новый вывод предпочитает `https://vk.ru/thelegendarypoet`. Адрес `https://vk.com/thelegendarypoet` остаётся допустимым compatibility/migration input.

Служебные ссылки кабинета автора:

- https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet
- https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet?filterPreset=published&section=video_my_content&subsection=video_my_content_clips

Ссылки `cabinet.vkvideo.ru` являются только operational/admin routes. Они запрещены в публичных описаниях, комментариях, постах, футерах и рекламных блоках.

## 3. Обязательное преобразование

Перед загрузкой или редактированием видеозаписи бот:

1. сохраняет слова, пунктуацию, абзацы, ссылки и хештеги;
2. снимает только парные маркеры выделения `*...*`, `**...**`, `_..._`, `__...__`, `~~...~~`;
3. не трогает подчёркивания внутри URL, технических ID и хештегов;
4. сохраняет литературное название вида `К *** (Я помню чудное мгновенье…)`;
5. превращает Markdown-ссылку `[подпись](https://...)` в открытый текст `подпись: https://...`;
6. удаляет невидимые `U+FEFF`, `U+200B`, `U+2060`;
7. приводит переносы строк к `LF` и оставляет одну пустую строку между смысловыми блоками;
8. добавляет только ссылки профиля `legendary-poet` и не дублирует одинаковые назначения;
9. предпочитает канонический VK `https://vk.ru/thelegendarypoet` в новом выводе;
10. не меняет факты, литературную интерпретацию или порядок абзацев;
11. отклоняет любую ссылку проекта Господь Бог — Сила Моя;
12. отклоняет кабинетный URL в публичном поле.

Неразрешённые маркеры, HTML, чужой project profile и operational/admin URL в публичном поле являются причиной остановки публикации для редакторской проверки, а не поводом для агрессивной очистки.

## 4. Разрешённое оформление

Для визуальной структуры используются только средства, которые остаются понятными в простом тексте:

- короткие абзацы;
- одна пустая строка между блоками;
- смысловые эмодзи без механического повторения;
- строки `Сайт: URL`, `Плейлист: URL`, `VK: URL`, `Telegram: URL`, `VK Клипы: URL`, `RUTUBE: URL`;
- открытые URL;
- хештеги;
- осторожные текстовые разделители.

Нельзя подменять жирный текст математическими Unicode-символами или псевдошрифтами: они ухудшают поиск, копирование, доступность и совместимость шрифтов.

## 5. Канонический публичный блок

Для обычного ролика допустим компактный блок:

```text
🎧 The Legendary Poet — русская поэзия, музыка и литературные материалы.
Сайт проекта: https://thelegendarypoet.ru/
Telegram: https://t.me/thelegendarypoet
Сообщество проекта в VK: https://vk.ru/thelegendarypoet
RUTUBE: https://rutube.ru/channel/74579453/
```

Для материала, который продвигает именно короткий формат, можно добавить:

```text
VK Клипы: https://vkvideo.ru/@thelegendarypoet/clips
```

Блок не дублируется при повторном запуске. Не каждая поверхность обязана использовать все ссылки; выбирается минимальный уместный набор.

## 6. Разделение рендереров

YouTube и VK используют разные платформенные функции:

```text
render_youtube_description()
render_vk_video_description()
render_vk_clip_description()
```

VK-публикация дополнительно проходит централизованную policy-функцию:

```text
render_vk_publication_title()
render_vk_publication_description()
render_vk_publication()
```

Версия policy, `project_key`, точные provider IDs и SHA-256 готового описания сохраняются в журнале загрузки.

## 7. Защита записи

Для каждой операции фактический live-текст классифицируется так:

```text
expected before → ready
expected after  → already applied
третье состояние → conflict
```

Перед массовой операцией:

1. создаётся полный live-снимок всех VK-ID;
2. создаётся self-validating plan schema v2;
3. проверяются `project_key`, `community_id`, `owner_id`, `coverage_remote_ids_sha256` и `plan_sha256`;
4. проверяется соответствие каждой ссылки профилю `legendary-poet`;
5. оператор читает Markdown diff;
6. выполняется dry-run;
7. захватывается local single-writer lock;
8. после lock повторяются coverage и text preflight;
9. до первой записи создаётся backup;
10. каждая операция повторно проверяется через `video.get`;
11. вся партия проходит итоговый postflight;
12. при сбое запускается guarded rollback.

Изменение состава live-видеотеки после аудита инвалидирует whole-community plan.

## 8. Windows lock

На Windows нельзя использовать Unix-паттерн `os.kill(pid, 0)`: обычный числовой сигнал реализуется через `TerminateProcess`.

Lock использует non-destructive Win32 process query, а также:

- `hostname` и случайный `nonce` владельца;
- grace period для только что созданного пустого lock-файла;
- атомарное quarantine устаревшего lock;
- удаление lock только владельцем с совпадающим nonce.

## 9. Media QC перед новой загрузкой

Локальный файл допускается к VK upload только после:

- проверки ненулевого размера;
- успешного `ffprobe` JSON;
- наличия video stream;
- наличия audio stream;
- положительной duration;
- расчёта SHA-256;
- сохранения codecs/dimensions/sample rate/channels в журнале.

Exact-ID resume дополнительно строит подтверждаемый transfer manifest SHA-256.

## 10. Инструменты

### Проверка рендеринга YouTube-снимка — read-only

```powershell
python .\scripts\audit_vk_description_rendering.py `
  .\data\exports\youtube-legendary-poet-<channel>-<timestamp>.json
```

Этот отчёт отвечает на вопрос, как YouTube-тексты будут выглядеть в VK, но не заменяет live-аудит старых VK-видео.

### Полный live-аудит всей VK-видеотеки — read-only

```powershell
python .\scripts\audit_all_vk_descriptions.py `
  --account legendary-poet `
  --community 235216998
```

Он создаёт plan schema v2 и Markdown diff на основе текущих VK-описаний.

### Dry-run/применение whole-community plan

```powershell
python .\scripts\apply_all_vk_description_cleanup.py `
  <vk-live-description-cleanup-v2.json> `
  --account legendary-poet `
  --community 235216998
```

Полная процедура описана в:

```text
docs/operations/vk-description-cleanup-runbook.md
```

### Безопасный перенос новых видео

Разрешён только wrapper:

```powershell
python .\scripts\sync_youtube_to_vk_textsafe.py <аргументы>
```

`scripts/sync_youtube_to_vk.py` является внутренним implementation module и не должен запускаться оператором напрямую: базовый файл не является самостоятельным safety profile.

### Точечное exact-ID восстановление

```powershell
python .\scripts\resume_youtube_to_vk_exact_ids.py `
  <youtube-audit.json> `
  <exact-video-id...> `
  --journal <journal.json> `
  --cache-dir <cache> `
  --account legendary-poet `
  --community 235216998
```

Сначала всегда выполняется dry-run. Execute требует точного сообщества, количества новых uploads, source snapshot и transfer manifest SHA-256.

### Старый journal-only repair

```text
scripts/repair_vk_descriptions_from_sync_journal.py
```

остаётся узким recovery-инструментом для известных journaled uploads. Он не используется как полная проверка сообщества и не заменяет whole-community plan v2.
