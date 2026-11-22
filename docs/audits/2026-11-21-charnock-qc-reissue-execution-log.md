# Журнал переиздания qc-редакций Чарнока (21.11.2026)

Все 13 бесед переизданы на **существующих** страницах Telegraph: тот же путь, тот же автор
(«Господь Бог», https://t.me/lordchrist), новый заголовок и новое тело из проверенного JSON.
Новых страниц не создавалось, Telegram не редактировался, публичные URL не менялись.

Механика: `.github/workflows/lordchrist-charnock-qc-reissue.yml` →
`scripts/charnock_telegraph_qc_reissue.py`, манифест
`content/telegram/lordchrist/telegraph-v1/charnock/charnock-qc-reissue-20261121.json`.
Каждый запуск: публичный GET, план, при execute — один `editPage`, публичный readback,
ровно одна квитанция в артефакте запуска.

## Результат

| Страница | Живой path | Запуск (режим) | Эффект | Проверка | Блоки | Байты | live sha256 (16) |
|---|---|---|---|---|---|---|---|
| 01b | `Podsvechnik-sovesti-i-zhertva-Avelya-pochemu-odnogo-znaniya-o-Boge-nedostatochno--ispravlennoe-izdanie-11-05` | 44963899308 (reconcile) | VERIFIED_REISSUE_RECONCILED | reconciled | 116 → 116 | 62100 → 61199 | `1b77d37c0a0c9fc6` |
| 02 | `Vseobshchee-soglasie-kak-CHarnok-obosnovyval-znanie-o-Boge-u-narodov--ispravlennoe-izdanie-11-05` | 44964131651 (execute) | VERIFIED_REISSUE | semantic | 122 → 122 | 63374 → 62084 | `ea77cb79464fa25b` |
| 03 | `Tri-vozrazheniya-ateista-predanie-zagovor-pravitelej-strah--ispravlennoe-izdanie-11-05` | 44964183329 (execute) | VERIFIED_REISSUE | semantic | 131 → 131 | 61880 → 59631 | `61ab4c1b5b063519` |
| 04 | `Mir-kak-zerkalo-kak-tvorenie-svidetelstvuet-o-Tvorce--ispravlennoe-izdanie-11-05` | 44964219158 (execute) | VERIFIED_REISSUE | semantic | 150 → 150 | 65334 → 64435 | `dc8d4e3d6043200a` |
| 05 | `Nikto-ne-sotvoril-sebya-ot-tvarnoj-nemoshchi-k-vechnoj-Pervoprichine-11-04` | 44964254253 (execute) | VERIFIED_REISSUE | semantic | 147 → 147 | 66075 → 64304 | `03a8dd2787b5a8bc` |
| 06 | `Lyutnya-mirozdaniya-kak-vrazhduyushchie-stihii-solnce-i-okean-sluzhat-odnomu-domu-11-05` | 44964304280 (execute) | VERIFIED_REISSUE | semantic | 137 → 137 | 64276 → 62577 | `d4634d84ddf40205` |
| 07 | `CHasy-bez-chasovshchika-poryadok-mira-kotoryj-ne-slozhilsya-sam-11-05` | 44964359178 (execute) | VERIFIED_REISSUE | semantic | 99 → 99 | 48156 → 47485 | `3f2c94c479a0b67e` |
| 08 | `Strela-ne-vybiraet-cel-instinkt-tvorenij-i-sohranenie-mira-11-05` | 44964392629 (execute) | VERIFIED_REISSUE | semantic | 85 → 85 | 40381 → 38701 | `e2c17f8c4cc21df6` |
| 09 | `Ne-nuzhno-vyhodit-iz-doma-telo-i-dusha-kak-svidetelstvo-o-Tvorce-11-05` | 44964441500 (execute) | VERIFIED_REISSUE | semantic | 95 → 95 | 42748 → 42134 | `da12c726e44dac07` |
| 10 | `Sudya-kotorogo-nelzya-vyklyuchit-sovest-i-zhazhda-beskonechnogo-11-05` | 44964500172 (execute) | VERIFIED_REISSUE | semantic | 97 → 97 | 45748 → 45190 | `d4c2285847a1bf59` |
| 11 | `Nebo-ne-molchit-sudy-chudesa-i-prorochestva-11-05` | 44964565846 (execute) | VERIFIED_REISSUE | semantic | 71 → 71 | 32072 → 31696 | `4b87dacf96705f97` |
| 12 | `Nelzya-dokazat-chto-Boga-net-shest-otvetov-somnevayushchemusya-11-05` | 44964624497 (execute) | VERIFIED_REISSUE | semantic | 55 → 55 | 27123 → 26696 | `e6c0376ca891eb93` |
| 13 | `Utverditsya-i-poklonitsya-chem-zakanchivaetsya-beseda-o-bytii-Boga-11-05` | 44964665502 (execute) | VERIFIED_REISSUE | semantic | 56 → 56 | 25353 → 25969 | `5cb7782912687375` |

Все запуски — `success`. Проверка `semantic` означает: число узлов совпало, каждый узел совпал
по тегу и видимому тексту, заголовок страницы совпал с проверенным; побайтовое совпадение JSON
не достигнуто, потому что Telegraph нормализует хранение узлов (атрибуты картинок и разметку
внутри blockquote). Для 01b отдельный read-only `reconcile` подтвердил то же самое независимо.

## Что подтверждено и что нет

- Подтверждено: провайдер принял правку, публичный GET сразу после неё вернул ожидаемые
  заголовок и текст, квитанция записана и выгружена артефактом запуска.
- Не подтверждено и не заявляется: что сообщения канала ведут на переизданные страницы —
  Telegram в этом цикле не трогали; что HTML-вид страницы совпадает с локальным превью.
- Квитанции лежат только в артефактах GitHub Actions (`charnock-qc-reissue-receipt-<page>-<run_id>`),
  в репозиторий они не коммитятся; этот журнал фиксирует их ключевые поля.
- Durable ledger `state/lordchrist-telegram` намеренно не изменялся: скрипт не пишет состояние,
  доказательство — квитанция и публичный readback.

## Как это проверялось перед записью

- `dry-run` для 01b, 02, 06, 13 напечатал план: прежний и новый заголовок, число блоков,
  байты до/после, первые расхождения. Для 03, 04, 05, 07–12 отдельные dry-run были
  отменены лимитом очереди GitHub (в группе concurrency допустим только один ожидающий
  запуск); их execute нёс те же проверки до POST — путь, автор, размер, свежий GET,
  владение страницей — и те же поля в результате.
- Ни один запуск не использовал `createPage`, ни один не трогал Telegram-бота.

## Ограничения, которые остаются

- 04 (64 435 B) и 05 (64 304 B) у потолка 65 536 B: любое добавление текста требует сокращения.
- Slug страниц прежний и не совпадает с новым заголовком — ожидаемо для editPage.
- Повторный `execute` для уже переизданной страницы откажется; проверка — только `reconcile`.


## Контрольный readback 21.11.2026 (read-only)

Отдельный проход `mode=reconcile` по всем 13 страницам: провайдер только читается, каждая
страница сравнивается с проверенным payload целиком — тег и видимый текст каждого узла,
число узлов, заголовок; пишется ровно одна квитанция на запуск.

| Страница | Запуск | Эффект | Блоки | Байты (live) | live sha256 (16) |
|---|---|---|---|---|---|
| 01b | 44967824927 | VERIFIED_REISSUE_RECONCILED | 116 | 62100 | `d6cadbaef171a841` |
| 02 | 44967861185 | VERIFIED_REISSUE_RECONCILED | 122 | 62993 | `d2fdb96db85eb03f` |
| 03 | 44967894527 | VERIFIED_REISSUE_RECONCILED | 131 | 60552 | `b2d04f092f8817e1` |
| 04 | 44967945037 | VERIFIED_REISSUE_RECONCILED | 150 | 65450 | `9cc73d804de1837d` |
| 05 | 44967986531 | VERIFIED_REISSUE_RECONCILED | 147 | 65563 | `b6de1c1bbed678c8` |
| 06 | 44968090520 | VERIFIED_REISSUE_RECONCILED | 137 | 63726 | `5962cbed6e60ff13` |
| 07 | 44968146122 | VERIFIED_REISSUE_RECONCILED | 99 | 48156 | `6a5db91e5ea2bfc5` |
| 08 | 44968341265 | VERIFIED_REISSUE_RECONCILED | 85 | 39402 | `2428c404eaf3cb37` |
| 09 | 44968390153 | VERIFIED_REISSUE_RECONCILED | 95 | 42875 | `dc2b19968e0e896d` |
| 10 | 44968429394 | VERIFIED_REISSUE_RECONCILED | 97 | 45776 | `7bdd9f5deb96b1c2` |
| 11 | 44968463944 | VERIFIED_REISSUE_RECONCILED | 71 | 32125 | `c0cd425273a27c4a` |
| 12 | 44968512925 | VERIFIED_REISSUE_RECONCILED | 55 | 27176 | `fbf27d3ca87af714` |
| 13 | 44968549197 | VERIFIED_REISSUE_RECONCILED | 56 | 26379 | `3d25d2d19916d6df` |

Все 13 запусков — `success`, все 13 — `VERIFIED_REISSUE_RECONCILED`: на живой странице стоит
именно тот текст, что лежит в проверенном JSON, ни одним узлом больше и ни одним меньше.

Примеры дословного чтения (то, что вернул публичный `getPage(...?return_content=true)`):

- **01b**, заголовок «Подсвечник совести и жертва Авеля: почему одного знания о Боге недостаточно»,
  первый видимый текст: «А без веры угодить Богу невозможно; ибо надобно, чтобы приходящий к Богу
  веровал, что Он есть, и ищущим Его воздаёт»; последний: «© Цитаты Чарнока — из книги
  «Беседы о существовании и атрибутах Бога» (Discourses upon the Existence and Attributes of God)».
- **10**, первый видимый текст: «Они показывают, что дело закона у них написано в сердцах, о чём
  свидетельствует совесть их и мысли их, то обвиняющие, то оправдывающие одна другую».
- **13**, заголовок «Утвердиться и поклониться: чем заканчивается беседа о бытии Бога».

Что этот проход **не** доказывает: как страница выглядит в браузере (наш readback — API-представление),
и что канал ведёт на неё (Telegram в этом цикле не трогали).

Замечание о размере: у 05 публичный `content` занимает 65 563 байта — больше нашего POST-потолка
65 536 B. Потолок ограничивает то, что мы отправляем (payload 05 — 64 304 B), а хранимое
представление Telegraph добавляет служебные атрибуты. Для будущих правок 05 это значит:
сначала сокращать текст, потом добавлять.
