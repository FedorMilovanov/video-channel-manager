# VK API source ledger — 52 ссылки

Дата проверки: **25 июля 2026 года**  
Назначение: обоснование архитектуры VK-модуля Video Channel Manager.  
Статус: **read-only; никаких изменений в VK не выполняется**.

## Метод

Источники разделены на три уровня:

- **P1** — официальная схема VK API и официальный код SDK; основной источник истины;
- **P2** — официальные репозитории, issues и примеры VK, полезные для выявления расхождений и реального поведения;
- **S** — сторонние реализации, используемые только как перекрёстная проверка, но не как основание для критических решений.

Глубоко проверены определения `video.get`, `video.getAlbums`, `video.getAlbumsByVideo`, `groups.get`, `groups.getById`, `users.get`, формы ответов, видео/альбомные объекты и каталог ошибок. Остальные ссылки использованы для проверки OAuth-потоков, типов токенов, областей доступа, SDK-генерации и известных расхождений документации.

## Главные выводы

1. Для чтения видео и альбомов официальная схема 5.199 указывает **пользовательский токен**.
2. Сообщество в `owner_id` обозначается отрицательным числом.
3. `video.get` поддерживает `count ≤ 200`, `offset`, `album_id`, `sort_album`.
4. `video.getAlbums` поддерживает `count ≤ 100`, `offset`, `extended`, `need_system`.
5. VK возвращает `width`, `height` и `type`, включая `short_video`; это надёжнее классификации по названию или длительности.
6. Полный ID видео необходимо хранить как `<owner_id>_<video_id>`.
7. `groups.getById` в актуальной схеме возвращает объект с массивом `groups`, а не старый голый список.
8. Ошибки `6`, `9`, `10`, `29` могут быть временными; ошибки авторизации и доступа должны останавливать операцию.
9. Токен сообщества не является универсальным: официальные issues фиксируют `method is unavailable with group auth` даже при заявленных правах.
10. Из-за известных расхождений сайта документации и schema runtime-ответы сохраняются в `metadata`, а критические предположения покрываются тестами.

## P1 — официальная схема VK API

1. [VKCOM/vk-api-schema](https://github.com/VKCOM/vk-api-schema) — канонический репозиторий схем.
2. [README схемы](https://github.com/VKCOM/vk-api-schema/blob/master/README.md) — структура, версия 5.199, назначение файлов.
3. [schema.json](https://github.com/VKCOM/vk-api-schema/blob/master/schema.json) — расширения JSON Schema для методов и параметров.
4. [schema-errors.json](https://github.com/VKCOM/vk-api-schema/blob/master/schema-errors.json) — схема ошибок.
5. [errors.json](https://github.com/VKCOM/vk-api-schema/blob/master/errors.json) — коды 5, 6, 7, 9, 10, 27, 29, 204, 260 и другие.
6. [video/](https://github.com/VKCOM/vk-api-schema/tree/master/video) — раздел видео API.
7. [video/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/video/methods.json) — параметры, лимиты и типы токенов видео-методов.
8. [video/objects.json](https://github.com/VKCOM/vk-api-schema/blob/master/video/objects.json) — поля видео, файлов, обложек и альбомов.
9. [video/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/video/responses.json) — формы ответов `video.get*`.
10. [groups/](https://github.com/VKCOM/vk-api-schema/tree/master/groups) — раздел сообществ.
11. [groups/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/groups/methods.json) — `groups.get`, `groups.getById`, фильтры ролей и лимиты.
12. [groups/objects.json](https://github.com/VKCOM/vk-api-schema/blob/master/groups/objects.json) — поля сообщества и уровень управления.
13. [groups/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/groups/responses.json) — актуальные контейнеры `groups`, `profiles`, `items`.
14. [users/](https://github.com/VKCOM/vk-api-schema/tree/master/users) — раздел пользователей.
15. [users/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/users/methods.json) — `users.get` для проверки личности токена.
16. [users/objects.json](https://github.com/VKCOM/vk-api-schema/blob/master/users/objects.json) — пользовательские поля.
17. [users/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/users/responses.json) — форма ответа `users.get`.
18. [base/](https://github.com/VKCOM/vk-api-schema/tree/master/base) — общие типы.
19. [base/objects.json](https://github.com/VKCOM/vk-api-schema/blob/master/base/objects.json) — bool-int, image, likes, reposts и общие структуры.
20. [base/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/base/responses.json) — общие response-типы.
21. [utils/](https://github.com/VKCOM/vk-api-schema/tree/master/utils) — разрешение screen name и служебные методы.
22. [utils/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/utils/methods.json) — `utils.resolveScreenName` как резервный путь разрешения адресов.
23. [utils/objects.json](https://github.com/VKCOM/vk-api-schema/blob/master/utils/objects.json) — типы результатов utils.
24. [utils/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/utils/responses.json) — формы ответов utils.
25. [execute/](https://github.com/VKCOM/vk-api-schema/tree/master/execute) — batch/execute-механика, пока не используемая из-за сложности ошибок.
26. [execute/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/execute/methods.json) — ограничения `execute`.
27. [execute/responses.json](https://github.com/VKCOM/vk-api-schema/blob/master/execute/responses.json) — формы batch-ответов.
28. [photos/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/photos/methods.json) — будущая проверка загрузки обложек, не включена в read-only фазу.
29. [wall/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/wall/methods.json) — будущая сверка публикаций на стене, не включена сейчас.
30. [apps/methods.json](https://github.com/VKCOM/vk-api-schema/blob/master/apps/methods.json) — сведения о приложениях и типах доступа.

## P1 — официальные SDK и OAuth-примеры

31. [VKCOM/vk-java-sdk](https://github.com/VKCOM/vk-java-sdk) — официальный Java SDK, сгенерированный из схемы 5.199.
32. [Java SDK README](https://github.com/VKCOM/vk-java-sdk/blob/master/README.md) — user/group/service actors, OAuth и обработка ошибок.
33. [Java SDK source tree](https://github.com/VKCOM/vk-java-sdk/tree/master/sdk/src/main/java/com/vk/api/sdk) — фактическая реализация клиента.
34. [Java video queries](https://github.com/VKCOM/vk-java-sdk/tree/master/sdk/src/main/java/com/vk/api/sdk/queries/video) — типизированные `video.get*` запросы.
35. [Java group queries](https://github.com/VKCOM/vk-java-sdk/tree/master/sdk/src/main/java/com/vk/api/sdk/queries/groups) — типизированные `groups.get*` запросы.
36. [Java user queries](https://github.com/VKCOM/vk-java-sdk/tree/master/sdk/src/main/java/com/vk/api/sdk/queries/users) — `users.get`.
37. [Java actors](https://github.com/VKCOM/vk-java-sdk/tree/master/sdk/src/main/java/com/vk/api/sdk/client/actors) — различия UserActor, GroupActor, ServiceActor.
38. [Java OAuth](https://github.com/VKCOM/vk-java-sdk/tree/master/sdk/src/main/java/com/vk/api/sdk/oauth) — OAuth response-модели.
39. [VKCOM/vk-php-sdk](https://github.com/VKCOM/vk-php-sdk) — официальный PHP SDK.
40. [PHP SDK README](https://github.com/VKCOM/vk-php-sdk/blob/master/README.md) — примеры user/community access token и redirect fragment.
41. [PHP VKOAuth](https://github.com/VKCOM/vk-php-sdk/blob/master/src/VK/OAuth/VKOAuth.php) — построение URL и обмен кода.
42. [PHP user scopes](https://github.com/VKCOM/vk-php-sdk/blob/master/src/VK/OAuth/Scopes/VKOAuthUserScope.php) — пользовательские области доступа.
43. [PHP group scopes](https://github.com/VKCOM/vk-php-sdk/blob/master/src/VK/OAuth/Scopes/VKOAuthGroupScope.php) — отдельный набор прав токена сообщества.
44. [PHP Video actions](https://github.com/VKCOM/vk-php-sdk/blob/master/src/VK/Actions/Video.php) — официальный wrapper видео-методов.
45. [PHP Groups actions](https://github.com/VKCOM/vk-php-sdk/blob/master/src/VK/Actions/Groups.php) — wrapper сообществ.
46. [PHP Users actions](https://github.com/VKCOM/vk-php-sdk/blob/master/src/VK/Actions/Users.php) — wrapper проверки пользователя.

## P2 — официальные issues и дополнительные продукты VK

47. [Schema vs documentation, issue #209](https://github.com/VKCOM/vk-api-schema/issues/209) — подтверждает необходимость не доверять одному представлению документации.
48. [Wrong video.addToAlbum response, issue #220](https://github.com/VKCOM/vk-api-schema/issues/220) — пример расхождения response-типа.
49. [Community token error 27, issue #242](https://github.com/VKCOM/vk-api-schema/issues/242) — свежий пример ограничений group auth.
50. [VK Mini Apps API](https://github.com/VKCOM/vk-mini-apps-api) — отдельный контекст community token; не заменяет user token для нашего CLI.
51. [VK ID Android SDK](https://github.com/VKCOM/vkid-android-sdk) — актуальный мобильный OAuth/PKCE-контекст.
52. [VK ID iOS SDK](https://github.com/VKCOM/vkid-ios-sdk) — актуальный iOS OAuth/PKCE-контекст.

## S — перекрёстная проверка, не источник истины

- [vk-io generated method types](https://github.com/negezor/vk-io/blob/master/packages/vk-io/src/api/schemas/methods.ts) — сверка имён и response-типов.
- [stek29/vk video wrapper](https://github.com/stek29/vk/blob/master/vkapi/video.go) — независимая проверка разделения normal/extended responses.

Эти сторонние ссылки не учитываются в числе 52 основных источников и не используются для выбора разрешений или безопасности.

## Решения, принятые по результатам проверки

- только user token для текущего VK-видео контура;
- token import вместо хранения логина/пароля;
- скрытый ввод и локальный ignored-файл;
- POST body вместо токена в query string;
- временная проверка до перезаписи существующего токена;
- `groups.get(filter=moder)` для модераторов, редакторов и администраторов;
- отрицательный owner ID сообщества;
- `owner_id_video_id` как канонический remote ID;
- полная offset-пагинация;
- `need_system=1` с отдельной маркировкой системных альбомов;
- `type=short_video` как прямой признак короткого видео;
- повтор только временных ошибок;
- сохранение сырого ответа в metadata;
- никаких write-методов до реального снимка, ChangePlan, preview, approval и rollback.
