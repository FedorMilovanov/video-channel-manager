# Очередь дозакрытия: ноль только по доказательствам

**24 November read-only checkpoint — Jude release complete, NO REPLAY.** Exact ID `lordchrist-telegraph-jude-1-5-20261105` is `published/verified` in protected state (ledger blob `6939e93f5cd905feee70f7f38014180056e5158f`, state HEAD `1534cf8e9dcea55d68a5bb550d139b2830cad1e3`). [Run 45214387883](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/45214387883) succeeded on `406d26b178f039509d28baef2d49a4d545bc0078`, attempt 1, including both durable receipts; published 23 November 19:39 MSK. Independent GET: [Telegraph](https://telegra.ph/Odin-Gospod-dva-chteniya-Iisus-ili-Gospod-v-Iud-15-11-23) and [Telegram #1632](https://t.me/lordchrist/1632) HTTP 200, exact public message and article link. Approved article/cover SHA-256, title, normalized body text, 48 top-level nodes, all 13 link targets (multiset) and image URLs matched; raw provider node JSON differs, so do not claim byte-identical markup. Old run `43098273140` still reports queued/no conclusion, zero jobs; its exact historical workflow checks current main before both send stages. It is NOT confirmed canceled; retain the GitHub inconsistency as separate infrastructure evidence, do not rerun, cancel again, force-cancel or republish. Preserve both receipts and immutable ID. The earlier pending/HOLD narrative below is historical and does not reopen this completed publication.

**Sections below retain their original historical checkpoint.**

Контрольная точка: 22.11.2026 около 09:00 UTC. Сначала — безопасные дневные публикации и
редакционные/повторные риски, затем остальные конвейеры по порядку. **Локальный код, точный
артефакт, независимая приёмка, разрешение на исполнение и подтверждённая публикация — разные
состояния.** Не засчитывать intent, зелёный тест или старую квитанцию как текущий provider readback.

Более поздние owner-reported/read-only checkpoints 22.11 UTC / 23.11 МСК и точные ограничения — в
[`current-state.md`](current-state.md) и ссылках на issues ниже. Это снимки, а не новое разрешение.

## Сверка объёма

Свежий `gh issue list --state open` вернул **17 различных открытых issues**:

- LordChrist/контент: **#1009, #810, #930, #940**;
- Чарнок: **#997**;
- платформы и rollout: **#662, #774, #782, #903, #1036, #795, #869, #789, #778, #792, #790, #809**.

Отдельно видны по крайней мере выпуск Иуды, дата `charnock-history-02` и оставшаяся независимая
приёмка 18 quote-v6; не складываем их механически с issues: часть обязательств — подпункты или
перекрываются. Прежняя сумма «18 задач» не обоснована. Это не исчерпывающий подсчёт всех ручных
обязательств. Зонтичные E2 `#789` и E3 `#903` **не** дублируются в счёте с D8/D4; E1 `#997`
не дублируется с B2. Есть также два открытых PR по quote-v6 #1049/#1051, не приравнивать их
к утверждённым текстам или разрешению отправки.

## Порядок

### 1. Иуда — дневное окно, один объект, один запуск

Нет записи в свежепрочитанном ledger, но это не доказывает отсутствия результата у провайдера.
Детали и ограничения — [`2026-11-21-release-calendar.md`](2026-11-21-release-calendar.md).
Старый ручной run `43098273140` остаётся `queued` без jobs, его inputs неизвестны; действия и
дубликаты нужно установить без повторной отправки. 22.11 одна обычная отмена с разрешения владельца
вернула `Cannot cancel a workflow run that is completed`, но GET всё ещё показывал `queued` и
`conclusion=null`: это не подтверждённая отмена. Не повторять отмену и не применять force-cancel;
нужна [сверка GitHub](2026-11-22-jude-actions-reconciliation.md). В одном закреплённом Telegraph
аккаунте два прохода по 20 страницам не нашли подходящих заголовков; это не глобальная проверка.
GitHub variables недоступны через текущий токен (403). После разрешения неоднозначности владелец
должен проверить переменные, а исполнитель — exact target/state/current-main и отдельные гейты.
Если всё выполнено — один дневной прогон и публичный readback; при `may_exist` только сверка.
**Ночью не выпускать.** Read-only отчёт не предлагает дату Иуды при неразрешённом старом запуске.
Отдельный staged guard из слитого PR #1082 блокирует четыре этапа для точного ID/blob; он присутствовал
в `main@ce701b440223e3cfc5ca9017af25aa1d439ed5db` с успешным exact-main CI #45060934538. Ни guard,
ни отчёт не проверяют GitHub live, все внешние writers или занятость дня и не останавливают старые
SHA. Снятие HOLD потребует отдельной рассмотренной сверки, не повторной отмены.

### 2. #1009 — QUIZ: ликвидировать обходы, затем независимая приёмка

- Исторический Series03: 2 опубликованных/verified (#1617, #1623), 8 pending/impossible на
  checkpoint state `bca3c01f…`; v1 и его ledger не переписываются, повторы запрещены. 22.11
  публичный виджет #1617 показал опрос, а виджет #1623 ответил «Post not found»; это не квитанция
  удаления и не доказательство причины ([read-only checkpoint](https://github.com/FedorMilovanov/video-channel-manager/issues/1009#issuecomment-7084480991)).
- PR #1079 слит с provider-free guard и тестами против исторических ID, переименования release,
  generic initialization/skip/prepare/send и прямого native `sendPoll` на точный @lordchrist
  target. Workflow допускает только validate. Проверять точный текущий main и его CI перед
  действием. Канальная блокировка не распространяется
  на обычные сообщения и другие каналы, но исторические ID запрещены независимо от канала и формата.
  Guard не способен распознать QUIZ, замаскированный как обычное сообщение, или произвольный
  внешний клиент.
- Исторические данные читаемы; `may_exist` не превращается в фиктивное `not_dispatched`.
  Подписи в локальном JSON не доказывают настоящего review. Текущая реализация намеренно не
  авторизует новые @lordchrist native quizzes; для снятия HOLD понадобится отдельный проверяемый
  механизм и решение владельца, а не просто заполненные имена/URL.
- 8 source-bound кандидатов остаются черновиками: **0/8 независимых человеческих приёмок**.
  Не закрывать #1009 без содержательной редакционной приёмки и отдельного решения о rollout.

### 3. #997 / B2 / D9 — Чарнок: квитанция прежде новой даты

**Актуализация 25.11:** [PR #1111](https://github.com/FedorMilovanov/video-channel-manager/pull/1111) / [PR #1113](https://github.com/FedorMilovanov/video-channel-manager/pull/1113) merged; Telegraph 11–13 исправлены, V3 проверен 7/7 по действующему защищённому реестру. [Итог технической приёмки](https://github.com/FedorMilovanov/video-channel-manager/issues/997#issuecomment-7139054845). Остаток — не новая техническая миграция, а действительные права/редакторская приёмка, точный release digest и разрешение исполнения, семь фактических проверенных Telegram deliveries. №09 терминален; №13 SEND HOLD. №06–08 schedule-only, резервный ручной запуск №10–12 в точный день. [V3 runbook](charnock-recovery-calendar-v3-20261124.md). Историческое описание ниже не является актуальной оценкой технической готовности или разрешением на публикацию.

№09 уже имеет terminal reissue #1630 (20.11); повтор запрещён. Для 06–08 даты в отдельном
черновике не утверждены. Существующие слоты 10–12 нельзя считать работоспособными: все восемь
исторических blob и payload bindings расходятся с текущей очередью. №13 остаётся на HOLD.
Для №10–12 [отдельно установлено](https://github.com/FedorMilovanov/video-channel-manager/issues/997#issuecomment-7084081762),
что ledger media-base и QC media-base дают разные cover URLs при одинаковых байтах; обновление
article SHA само по себе не доказывает совпадение live page tree и не снимает блокировку.
[PR #1092](https://github.com/FedorMilovanov/video-channel-manager/pull/1092) добавил сравнение
heading ID относительно рассмотренного образца; синтетические тесты не являются свежим provider
readback и не превращают исторические QC runs в проверки по новому алгоритму.

В PR #1079 исправлен **только read-only планировщик**: терминальная вложенная квитанция,
неоднозначные эффекты, отсутствие ledger, drift и интервалы до/после занятых дат. PR слит;
состояние main и его CI подтверждены в контрольной точке ниже. Активный манифест, исходные
receipts и переменные этим PR не менялись. Нужна отдельная рецензируемая миграция
«неизменная первоначальная квитанция + проверенная исправленная редакция существующей страницы»,
согласование расписания, право/редакторская приёмка и поштучная исполнительная авторизация.
Подробнее — календарь. №04/05 не увеличивать; не выпускать пачкой.

### 4. #930 → #940 — точные media-артефакты и человеческое прослушивание

- **#930 Piper/MacArthur:** не смешивать V25H/V25J/V25K или отдельную 4-Shorts очередь.
  Более поздний issue readback сообщает: V25K full YouTube `ZLJYgU6UhvQ` был public/succeeded,
  четыре Shorts и MP3-ссылка `@lordchrist/1621` прочитаны; это историческая запись issue, не
  свежий provider GET. V25J `m6q0clAaaNA` — private согласно тому же readback. Английский
  EN18 mix в V25K прошёл локальные технические проверки, но полный человеческий listening и
  правообладание не доказаны. VK был NOT_DISPATCHED с code 9 и карантином учётной записи.
  Доступа к владельческим локальным MP4 здесь нет. Не изображать отсутствие публикаций и не
  разрешать новые отправки по факту старой публикации.
- **#940 SHORTOREZ:** последняя owner-local версия — `REVIEW_VERTICAL_STATIC_SHOT_9x16`, шесть
  файлов с технической проверкой; выбор статичного кадра и частичное обрезание лица раскрыты.
  Независимое прослушивание границ, права и решение по каждой площадке остаются открытыми.
  Локальная папка и данные не доступны в этом контейнере; не заменять их синтетическими media.

### 5. Последовательно: #774 → #782 → #903 → #795

- **#774:** исторический checkpoint 10.11 — производный счёт 154/164 PUBLIC. [Независимый
  read-only postflight 22.11](https://github.com/FedorMilovanov/video-channel-manager/issues/774#issuecomment-7084046551)
  подтвердил шесть точных переходов в Published: производно 160/164 + четыре отложенных, но это
  не полный свежий 164-row recensus; четыре старых scheduled ID через этот UI заново не доказаны.
  Исключить Heroes III, черновики и девять старых частных HOLD-копий сохранить; quarantined aliases
  не использовать, подтверждённые шесть объектов не создавать повторно.
- **#782:** все 7/7 title/factual changes, включая две атрибуционные опечатки, уже опубликованы
  и проверены на checkpoint 06.11; не повторять и не откатывать. У Блока `8g_4EVWFb1g` тогда был
  owner comment `UgyUMAfJqC8hdzxSnfF4AaABAg` — сохранить, не дублировать. У Есенина
  `Lf0h4yXPVng` тогда был только draft; нынешний полный inventory неизвестен. По делегированному
  редакционному решению подготовлен [источниковедческий кандидат](https://github.com/FedorMilovanov/video-channel-manager/issues/782#issuecomment-7078589769),
  но YouTube-комментарий не отправлен и закреп не проверен.
  **Решение владельца — ждать; не публиковать кандидата Есенина до нового решения.**
  Нужны свежие owner inventory, exact-operation guards, поддержанный authenticated transport и отдельный pin/readback в UI;
  `audio_unverified`. Исторический owner comment и API POST не доказывают текущий закреп.
- **#903:** 178-видео очередь 10 языков. На checkpoint 12.11 проверены 195/1780 metadata
  slots, не подтверждены 1585; это не текущий recensus. `NZISwKGIzGI` имел 10 verified
  caption tracks. Старый `may_exist` для `WizaG8S085g::en-US` после quotaExceeded был разрешён
  двумя owner-readback 12.11 как `reconciled_absent_after_403` (issue 14.11); это не текущее
  доказательство отсутствия и не разрешение на повтор. Восстановленный owner OAuth и успешный
  GET inventory не доказывают текущий остаток квоты, увеличенный grant или доступность
  `captions.insert`; [quota decision не подтверждено](https://github.com/FedorMilovanov/video-channel-manager/issues/903#issuecomment-7086336601).
  Требуются свежие readback и квота. Подробности: [квота и мультиязычный rollout](youtube-api-quota-and-viewer-language-2026-11-13.md).
- **#795:** owner-API аудит YouTube с сохранением глав/кредитов и сверкой VK остаётся открытым.
  [Owner GET inventory 22.11](https://github.com/FedorMilovanov/video-channel-manager/issues/795#issuecomment-7085551248)
  после OAuth consent получил 186/186 Poet, 152/152 Milovi и 1 881/1 887 Lord God video objects;
  в прочитанных uploads-playlist объектах не было будущего `publishAt`. Шесть отсутствующих Lord God
  объектов отдельно обозначены как deleted playlist tombstones, 18 повторных playlist-entry occurrences
  не доказывают дубли медиа. Это не полный аудит drafts вне uploads playlist и не разрешение на запись.
  На checkpoint 21.11 из 66 строк V5: 31 локальный draft (30 RU-only, 1 bilingual), 3 source-drift
  HOLD, 32 bilingual ещё не переписаны; это не редакционное/правовое одобрение и не новые PUT.
  У `7rfAeCHdz-s` отдельный HOLD из-за расхождения года в ASR/названии; не переименовывать.
  Отсутствующее поле `snippet.tags` в owner GET — неполный read, не доказательство удаления;
  до полного baseline запись закрыта. Проверять отложенный drift локализаций и аудиоязыка.
  Историческое восстановление Q&A54 Q02 уже имеет 19/19 независимый readback после HOLD;
  повторять PUT нельзя. Подробности: [description wave](lord-god-youtube-description-wave.md).

Для каждой строки сначала выяснить, что уже подтверждено текущим issue/state и какие конкретные
средства доступны, затем ограниченный read-only audit или кодовый PR; закрытие только по всем
требуемым доказательствам, не по числу тестов.

### 6. #789 → #778 → #792 → #790 → #809 → #662 → #869 → #1036 → #810

- **#789, Legendary Poet Instagram:** сверить `container_unknown` по точному target/ключу до
  продолжения. На checkpoint 15.11 создание container завершилось timeout без известного ID и
  без `media_publish`; новый ключ или URL не устраняют неопределённость. Исторические успешные
  Reels не переотправлять; замечания об авторах проверять по точным ID.
- **#778, Legendary Poet Instagram:** на [checkpoint 15.11](https://github.com/FedorMilovanov/video-channel-manager/issues/778#issuecomment-6897336352)
  тело существующего Reel `18125909824868306` уже называло Блока; оставался ошибочный hashtag
  `#АлександрПушкин`. Не откатывать ручную правку и не создавать Reel заново. После свежего
  полного caption readback нужна отдельно одобренная правка на месте через owner UI и readback;
  старый полный caption-план устарел, Graph endpoint не доказан для правки caption.
- **#792, Milovi VK:** на [checkpoint 21.11](https://github.com/FedorMilovanov/video-channel-manager/issues/792#issuecomment-7051382962)
  прочитаны 27/27 отложенных wall posts: 19 отдельных Clip-вложений, включая все 18 ранее не
  попавших на стену старых Clips и CDEK; ещё 8 постов без видео. Восемь прочих ordinary video
  уже загружены и требуют разбора вариантов/дублей, а не повторной загрузки. Часть слотов уже
  наступила: это не свежий postflight. Отдельно сохранять 12 исторических restricted Clips.
  У шести запланированных Clips `acodec=None` означает **звук неизвестен**, не доказанную тишину;
  нужны playback/stream readback, не автоматическая отмена, перепубликация или правка по одному
  metadata-признаку ([аудио-сверка](https://github.com/FedorMilovanov/video-channel-manager/issues/792#issuecomment-7052639277)).
  [Поздний независимый UI checkpoint 22.11](https://github.com/FedorMilovanov/video-channel-manager/issues/792#issuecomment-7084519026)
  сверил 25/25 текущих postponed wall ID и дат без коллизий; это не свежая полная сверка всех
  25 вложений. Community wall key не доказывает video/admin read; quarantined aliases не использовать.
- **#790, Milovi Instagram:** сохранять один writer и не повторять старые неясные/неуспешные
  ключи. [Owner-local SQLite reconciliation 23.11 МСК](https://github.com/FedorMilovanov/video-channel-manager/issues/790#issuecomment-7085944239):
  4 original-audio `published` с media ID, 7 `terminal_failure`, 1 `container_created` / `upload_unknown`,
  8 без соответствующей original-audio строки; это не полная текущая provider-сверка. Отдельный
  14.11 HTTPS key имеет container `18341870875261465`, но без media ID: успешный Reel не доказан.
  Попытка read-only GET восьми старых containers заблокирована security layer; обходить нельзя.
  Шесть будущих media прошли owner-local hash/codec, но лицензия soundtrack независимо не проверена.
  [Ранний owner checkpoint](https://github.com/FedorMilovanov/video-channel-manager/issues/790#issuecomment-7086329857)
  указал wrapper `1a0ddbeb8f5c3c57e0f1fd95c99120950a995580d480cb4b0b70634e3d1d13ec`;
  позднее он стал backup, а не текущей установленной версией. Ответы public-root GET через proxy не
  доказывают Meta ingestion или причину всех `1363008`.
  Repo-изменение [#1093](https://github.com/FedorMilovanov/video-channel-manager/pull/1093)
  слито как `a78bf4e6c46bba5f3831bf9cdf514c6d940e3168`; exact head
  `9946067ca830d0cd7684d4b8d84d78e7299117a6` прошёл CI, дерево совпадает с merge.
  Сам результат repo не доказывает deployment. [Поздний отчёт владельца 23.11 01:01 UTC](https://github.com/FedorMilovanov/video-channel-manager/issues/790#issuecomment-7088810705)
  отдельно сообщает о clean detached runtime на тогдашнем `main@b312ce3afaa922282b66ddf513dce24fd94d80d6`,
  35 прошедших test modules и установленном wrapper SHA-256
  `d6f98412a81e3d34540e9e052b8cb53ce02fe924f3763d3dcb927752228ff91b`.
  Один task оставался Enabled/Ready на 23.11 19:00 МСК; `-DryRun` exact source `OXC3BjtlU1g`
  дал `NO POST`. Это owner-reported evidence, не самостоятельная проверка ПК и не Reel receipt.
  Фиксированный pin не доказывает текущий `main` после его движения; перед новой операцией отдельно
  сверить baseline и состояние владельца, не меняя task и не создавая второго writer. Без работающего
  ПК/локального proxy доставка не гарантирована. Ни auto-switch HTTPS, ни новые hosting, retry,
  изменение task или второй writer из этих наблюдений не следуют.
- **#809, Milovi Telegram:** на 22.11 все 15 video окон истекли без verified ledger receipt;
  ранний Paris-Brest подавляет оригинал 17.11, окно Croissant 21.11 без verified ledger receipt,
  Stohrer 25.11 pending. Это не полная внешняя история и не доказательство отсутствия отправки.
  Публичный виджет исторического #28 ответил «Post not found», #29 показывает ту же статью с
  иной подписью; связь не доказана ([checkpoint](https://github.com/FedorMilovanov/video-channel-manager/issues/809#issuecomment-7084149926)).
  Независимый scheduled [run 45073384973](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/45073384973)
  23.11 00:48 МСК пропустил dispatch и завершился failure из-за защитного аудита 15 истёкших окон;
  это не полный внешний Telegram census и не повод перезапускать или догонять.
  Никаких backfill или замены исторического ID. PR #1088 слит и прошёл exact-main CI, но не
  обеспечивает on-time scheduler или фактическую доставку. Новая дата требует точного медиа, прав,
  сверки дублей и отдельной авторизации.
- **#662, VK:** открыты code-9 circuit и карантин прежнего user token. Отдельный ключ Lord God
  ранее подтверждён только для wall; восстановление — по официальному supported path и свежему
  ограниченному read, без ретраев старых `default`/`legendary-poet` и обхода flood.
- **#869, Lord God Instagram:** аккаунт и отдельные Reels ранее проверены; необходимы свежие
  receipts, права, состояние и контроль единственного owner-local writer для остальных выпусков.
- **#1036, Legendary Poet Telegram:** общий бот и target уже проверяли read-only 18–19.11;
  не создавать новый. [Точный Git blob MP3](https://github.com/FedorMilovanov/video-channel-manager/issues/1036#issuecomment-7083322026)
  проверен по размеру и SHA-256 `10cc0f069970a75b49d33a95cf7bf514fc25be3f1069ddf2a5437e2ea090c3e8`;
  [полный локальный decode](https://github.com/FedorMilovanov/video-channel-manager/issues/1036#issuecomment-7087633303)
  прошёл без ошибок, 9 011 270 stereo frames — 187,734792 с. Это не listening; ID3 и неслитый
  site ledger называют разные Suno ID, связь которых не установлена (не доказательство разных записей).
  Права, deployed HTTP, Windows bundle и отдельная кандидатная обложка не подтверждены. Частичный public
  scan не доказал отсутствие дубля; профиль записи выключен. Нужны свежая сверка происхождения,
  редакционная и правовая приёмка, release/ledger и отдельное разрешение; `sendAudio` здесь не выполнялся.
- **#810, LordChrist Shorts:** свежий owner AuditPackage, exact media и права, отсутствие дублей,
  новые даты и один проверенный canary; исторические слоты не догонять и второй writer не заводить.

Не повторять неясный эффект и не подменять владельческие или платформенные действия.

### 7. B3 и #1044 residual

`charnock-history-02` не имеет даты — нужно решение владельца, отдельно от #997 и без
автоназначения. #1044 закрыт **только по code scope** PR #1078: 18 pending quote-v6 не имеют
активации; независимые source/translation/rights reviews и отдельное решение о выпуске остаются.

## Контрольная точка интеграции PR #1079

- [PR #1079](https://github.com/FedorMilovanov/video-channel-manager/pull/1079) прошёл CI
  на head `b0467bee516a4d5eb4e69a058081f5e4b470ac49` и слит в main как
  `52386ea86067657e6d17b8cfad8b56ce9842021c`. На этом main
  [CI](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/45006997361)
  прошёл для Python 3.11–3.13 и Windows/Linux PowerShell; coverage-пороги не снижались.
- После CI автоматически выполнились [read-only quote-v4 preflight](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/45007265009),
  включая provider GET, и [Shorts workflow](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/45007265031)
  в режиме инициализации: шаг `sendVideo` пропущен. При проверке до и после protected-state
  HEAD оставался `bca3c01f2455516b2756494452cda7e8cd366098`. Это моментальный checkpoint,
  а не гарантия более позднего состояния и не разрешение на следующую отправку.

## Исторически завершённое, без повторов

- 13 Charnock pages переизданы **в существующих URL** с последовательными ограниченными
  текстовыми readbacks 21–22.11 UTC; заголовки позже сверены по сохранённым аннотациям,
  не при новой полной проверке серии. Это не сверка всех ссылок, медиа и разметки. `history-01` был исправлен и PUBLIC_VERIFIED
  17.11. Не выполнять ещё одну правку по старому контракту.
- Inplace workflow выведены из эксплуатации PR #1077. Старые контракты после QC — история.
- Открытие PR, CI, слияние и live-rollout различать; данная ветка сама по себе не меняет main,
  protected state или провайдеров.
