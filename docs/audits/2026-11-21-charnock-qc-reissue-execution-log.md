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
