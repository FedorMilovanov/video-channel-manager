# The Legendary Poet — профиль описаний и ссылок

Project key: `legendary-poet`

Этот профиль относится только к проекту **The Legendary Poet — Легендарный Поэт**. Он не должен подмешивать сайт, YouTube, VK, Telegram, Rutube, плейлисты или идентификаторы проекта **Господь Бог — Сила Моя**.

## Точные идентификаторы

### YouTube

- Название канала: `The Legendary Poet`
- Handle: `@TheLegendaryPoet`
- Канал: https://www.youtube.com/@TheLegendaryPoet
- Видео: https://www.youtube.com/@TheLegendaryPoet/videos
- Shorts: https://www.youtube.com/@TheLegendaryPoet/shorts
- Channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- OAuth alias: `legendary-poet`

### VK

- Сообщество: `The Legendary Poet - Легендарный Поэт`
- Канонический публичный адрес: https://vk.ru/thelegendarypoet
- Совместимый адрес: https://vk.com/thelegendarypoet
- Публичная страница клипов: https://vkvideo.ru/@thelegendarypoet/clips
- Номер сообщества в интерфейсе VK: `club235216998`
- Community ID: `235216998`
- API owner ID: `-235216998`
- Общий локальный VK token alias: `legendary-poet`

Общий alias токена не определяет проект. Любая VK-операция обязана привязать `project_key`, `community_id` и `owner_id`.

## Подтверждённые публичные ссылки

- Сайт: https://thelegendarypoet.ru/
- Telegram: https://t.me/thelegendarypoet
- VK: https://vk.ru/thelegendarypoet
- VK compatibility: https://vk.com/thelegendarypoet
- VK Clips: https://vkvideo.ru/@thelegendarypoet/clips
- Rutube: https://rutube.ru/channel/74579453/

## Канонические YouTube-плейлисты

Эти URL предоставлены владельцем проекта. В конкретное описание добавляются только плейлисты, которые относятся к ролику; нельзя автоматически вставлять весь список.

- Эксперименты AI: https://www.youtube.com/playlist?list=PLy9lLJfoq3uYdxFo5bxzXEUI8HYIo-sHb
- Поющие Поэты: https://www.youtube.com/playlist?list=PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8
- Владимир Маяковский: https://www.youtube.com/playlist?list=PLy9lLJfoq3uaI7EGOexBWQp7WX-KVabKM
- Сергей Есенин: https://www.youtube.com/playlist?list=PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q
- Михаил Лермонтов: https://www.youtube.com/playlist?list=PLy9lLJfoq3ubOdGfY8orpQzGNAAvkqul5
- Александр Пушкин: https://www.youtube.com/playlist?list=PLy9lLJfoq3ua0FhqDhByHxyaBjVrk0-pE
- Александр Блок: https://www.youtube.com/playlist?list=PLy9lLJfoq3ua3Q9BQe1Dhuzn7Knbz2djU

Правило релевантности:

- для музыкальной интерпретации поэзии обычно уместен «Поющие Поэты»;
- авторский плейлист добавляется только для соответствующего автора;
- «Эксперименты AI» добавляется только когда AI-эксперимент является заметной частью редакционного угла;
- плейлисты других авторов в нерелевантный ролик не добавляются;
- отсутствующие URL не придумываются.

## Служебные ссылки кабинета VK Видео

Эти адреса предназначены только для владельца и оператора. Их нельзя вставлять в публичные описания, комментарии, посты, футеры, манифесты для зрителей или рекламные блоки.

- Кабинет автора: https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet
- Опубликованные клипы в кабинете: https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet?filterPreset=published&section=video_my_content&subsection=video_my_content_clips

## Канонический публичный футер

Для новых описаний предпочтителен такой набор:

```text
🌐 Сайт проекта: https://thelegendarypoet.ru/
Telegram: https://t.me/thelegendarypoet
Сообщество проекта в VK: https://vk.ru/thelegendarypoet
RUTUBE: https://rutube.ru/channel/74579453/
```

Для роликов и публикаций, которые продвигают именно короткий формат, можно добавить:

```text
VK Клипы: https://vkvideo.ru/@thelegendarypoet/clips
```

Адрес `https://vk.com/thelegendarypoet` остаётся рабочим и допустим как compatibility/migration input, но новый канонический вывод должен предпочитать `https://vk.ru/thelegendarypoet`.

## Правила YouTube-описаний

Точный стандарт форматирования и ручного copy/paste-handoff находится в [`../youtube-description-rendering-standard.md`](../youtube-description-rendering-standard.md) и является обязательным для этого профиля.

Перед созданием, аудитом или изменением YouTube-описания агент обязан сначала прочитать этот стандарт и текущую явную инструкцию владельца. Нельзя заменять установленный проектом формат общим предположением о платформе или внешней веб-справкой. Если внешний источник кажется противоречащим проектному контракту, нужно остановиться и явно согласовать расхождение, а не молча переписывать стандарт, рендерер, autofix или тесты.

В частности, существующие правила `*...*`, `_..._`, пунктуации внутри/снаружи выделения, оформления цитат, подписей ссылок и fenced `text`-блока для ChatGPT/operator handoff сохраняются. Агент не должен превращать этот контракт в plain-text-only модель без отдельного явного изменения владельцем.

1. Первый абзац должен точно описывать произведение, автора, исторический материал, музыкальную адаптацию или визуальный эксперимент.
2. Нельзя выдумывать даты, обстоятельства создания, цитаты, архивные факты, посвящения или авторские намерения.
3. URL остаются обычным текстом.
4. Плейлисты добавляются только по точному членству или из отдельно проверенного плана.
5. Ссылки проекта Господь Бог — Сила Моя запрещены.
6. Кабинетные ссылки `cabinet.vkvideo.ru` запрещены.

## Правила VK Видео и VK Клипов

VK-описания являются простым текстом. Перед публикацией нужно снять неподдерживаемые YouTube-маркеры форматирования, сохранив слова, пунктуацию, абзацы, ссылки, хештеги и проверенные таймкоды.

Для обычного VK Видео можно использовать сайт, Telegram, канонический VK и Rutube. Публичную ссылку на VK Clips добавлять только там, где она действительно помогает зрителю перейти к коротким роликам.

Внутри самого VK не нужно дублировать несколько вариантов одного и того же сообщества.

## Обязательные guards плана

Каждый исполняемый план для проекта должен включать или привязывать:

```text
project_key: legendary-poet
youtube_channel_id: UC-78ys2S3cQ3lpqgXfo-SvQ
vk_community_id: 235216998
vk_owner_id: -235216998
link_profile: legendary-poet
```

Перед состоянием `ready` preflight обязан отклонить:

- другой YouTube channel ID;
- другое VK community ID или owner ID;
- любую зарегистрированную ссылку проекта Господь Бог — Сила Моя;
- неизвестный сайт, Telegram, VK, VK Video, Clips или Rutube маршрут;
- кабинетный URL в публичном поле;
- выдуманную ссылку на плейлист;
- cross-project promotion без отдельного явного разрешения.

## Источник истины

Полный реестр двух проектов находится в:

```text
docs/operations/project-identity-registry.md
```

При расхождении этот реестр имеет приоритет, а операция останавливается до синхронизации документации, исходного allowlist и валидатора.
