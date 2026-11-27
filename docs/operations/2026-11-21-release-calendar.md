# @lordchrist: календарь, квитанции и невыполненные проверки

**27 November read-only reconciliation — Reformation, NO REPLAY.** Protected state ledger blob `6939e93f5cd905feee70f7f38014180056e5158f` contains the legacy ID `lordchrist-telegraph-history-reformation-1517-01`, Telegram [#1593](https://t.me/lordchrist/1593), 1 November, and the [existing Telegraph page](https://telegra.ph/REFORMACIYA-EVANGELIE-PISANIE-I-SPORY-XVI-VEKA-04-11-02), revision 04. Current queue ID `lordchrist-telegraph-charnock-history-02` refers to the same named article family, exact Git blob `b3f4f310157488f716bf38990f7b7da77589f5c8`; 64/80 blocks match the archived polished draft literally. Do not schedule this alias as a fresh article, change the historical receipt, or infer current public visibility from the ledger. Public page/widget probes were unavailable on this checkpoint. The staged no-replay guard rejects both IDs and known exact article blobs at all four stages, without affecting preview or unrelated articles. Edited/external copies are not covered by an exact-blob guard. A future correction of the existing page would be separate, never a new page or Telegram send.

**24 November read-only checkpoint — Jude release complete, NO REPLAY.** Exact ID `lordchrist-telegraph-jude-1-5-20261105` is `published/verified` in protected state (ledger blob `6939e93f5cd905feee70f7f38014180056e5158f`, state HEAD `1534cf8e9dcea55d68a5bb550d139b2830cad1e3`). [Run 45214387883](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/45214387883) succeeded on `406d26b178f039509d28baef2d49a4d545bc0078`, attempt 1, including both durable receipts; published 23 November 19:39 MSK. Independent GET: [Telegraph](https://telegra.ph/Odin-Gospod-dva-chteniya-Iisus-ili-Gospod-v-Iud-15-11-23) and [Telegram #1632](https://t.me/lordchrist/1632) HTTP 200, exact public message and article link. Approved article/cover SHA-256, title, normalized body text, 48 top-level nodes, all 13 link targets (multiset) and image URLs matched; raw provider node JSON differs, so do not claim byte-identical markup. Old run `43098273140` still reports queued/no conclusion, zero jobs; its exact historical workflow checks current main before both send stages. It is NOT confirmed canceled; retain the GitHub inconsistency as separate infrastructure evidence, do not rerun, cancel again, force-cancel or republish. Preserve both receipts and immutable ID. The earlier pending/HOLD narrative below is historical and does not reopen this completed publication.

**Sections below retain their original historical checkpoint.**

Контрольная точка: **22.11.2026 около 09:00 UTC**. Документ и даты — не разрешение на
публикацию. Ledger прочитан из `state/lordchrist-telegram`, HEAD
`bca3c01f2455516b2756494452cda7e8cd366098` (последний коммит 20.11). Это чтение GitHub,
а не новый публичный readback Telegram/Telegraph. Перед действием заново проверить состояние,
текущий main, очередь и занятые даты. Не более одной статьи в день, без ночных выпусков.

## 1. Иуда: ближайшее дневное окно, но не автоматический повтор

`lordchrist-telegraph-jude-1-5-20261105` был назначен на воскресенье 15.11; действовавший
cron воскресенье не покрывал, а тот слот предполагал ручной запуск. Свежий ledger **не содержит
записи** об Иуде. Это не доказывает само по себе отсутствия страницы или сообщения у провайдера:
перед выпуском нужна отдельная проверка отсутствия/совпадения и точного целевого объекта.

Установлен дополнительный неопределённый фактор: старый ручной запуск Telegraph
[43098273140](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/43098273140),
созданный 11.11 с SHA `ba435ff17e726c803674c79273eb0ac07f2478bd`, всё ещё reported `queued`;
GET jobs вернул 0 jobs. Входные `action`, `publication_id` и итог не установлены. Его старый
workflow содержал проверку текущего main до публичной мутации, а этот SHA уже не текущий;
это **не** доказательство завершения запуска или его первоначальной цели.

**22.11 около 14:06 МСК:** владелец разрешил одну обычную отмену после повторной проверки.
`gh run cancel 43098273140` завершился с ошибкой `Cannot cancel a workflow run that is completed`,
а последующий GET по-прежнему вернул `queued`, `conclusion=null`, 0 jobs и 0 artifacts;
check suite также остаётся `queued`. Это противоречивые данные, **не подтверждённая отмена**.
Не повторять запрос и не применять force-cancel; нужна сверка состояния у GitHub / GitHub Support.
Подробный [пакет фактов и пределы доказательств](2026-11-22-jude-actions-reconciliation.md)
позволяет эскалировать проблему без передачи токенов. Перед новым запуском заново проверить
состояние, отсутствие дубля и отдельные гейты; неизвестный эффект не превращать в `confirmed_absent`.

Когда эти проверки и отдельная авторизация выполнены, требуемый результат — **одна статья,
один запуск, затем публичный readback** в ближайшее дневное окно. Никакой ночной отправки.
Если для статьи уже существует целевая страница, использовать её, не создавать новую; не
считать пустой ledger основанием для повторного создания. Состояние release-переменных сейчас
неизвестно: GitHub Actions variables вернули 403. Не включать их вслепую. Для проверки владельцем
нужны точные значения:

- `LORDCHRIST_TELEGRAPH_POSTING_ENABLED=true`;
- `LORDCHRIST_TELEGRAPH_APPROVED_PUBLICATION_ID=lordchrist-telegraph-jude-1-5-20261105`;
- `LORDCHRIST_TELEGRAPH_APPROVED_ARTICLE_BLOB_SHA=dd15da234a74eb474963d275c6a9bccfcadb9985`.

Их совпадение — лишь часть требуемых условий, а не замена проверки current-main/CI, редакционных
прав и прочего execution gate. После возможного запуска нужно подтвердить состояние каждого
шага и публичный результат. При `may_exist`/неясном результате — сверка, не повтор.

Отдельная [read-only проверка заголовков одного Telegraph-аккаунта](lordchrist-jude-telegraph-readonly.md)
предусматривает две полные сверки, привязку аккаунта к ранее подтверждённой странице и отсутствие
публикационных методов. Её запуск возможен только после слияния и CI на текущем main. Даже ноль
совпадений не доказывает отсутствие страницы в другом аккаунте, другого заголовка, скрытого поста
или неизвестного эффекта старого run; отчёт не читает release variables и не снимает HOLD.

## 2. Чарнок: что уже сделано и что не готово к исполнению

**Актуализация 25.11 (заменяет оперативные выводы исторического среза ниже):** [PR #1113](https://github.com/FedorMilovanov/video-channel-manager/pull/1113) merged, V3 calendar/source binding implemented and verified 7/7 on the protected ledger. [Техническая приёмка #997](https://github.com/FedorMilovanov/video-channel-manager/issues/997#issuecomment-7139054845). Согласованные владельцем даты 12:05 МСК: №11 — 27.11, №12 — 01.12, №13 — 04.12 (резерв/HOLD), №06 — 08.12, №07 — 11.12, №08 — 15.12, №10 — 18.12. №09 терминален, повтор запрещён. №06–08 только плановые попытки; ручной резерв только №10–12, строго в свой день и после выполнения всех допусков. Все семь release approvals null на контрольном срезе; recovery выключен, отдельные права/редакторская приёмка и авторизация нужны. Исторические несоответствия ниже объясняют прежнюю блокировку, но не означают, что V3 не реализован. [Действующий runbook V3](charnock-recovery-calendar-v3-20261124.md).

**Исторический срез до V3 (не исполнительная власть):**

- **№09 уже перевыпущен:** nested `scheduled_reissue.state=verified`, `provider_effect=verified`,
  дата 20.11, новое сообщение **1630**, оригинальное удалённое сообщение 1599. Не назначать новую
  дату и не отправлять повторно. Это terminal receipt на указанном ledger checkpoint, не свежий
  публичный GET от 22.11.
- **№06–08:** original receipts есть; nested reissue отсутствует на checkpoint, но это ещё не
  доказательство текущего отсутствия нового сообщения у провайдера. Даты 08.12 / 11.12 / 15.12
  находятся только в неутверждённом черновике. Никакого автоматического догоняющего выпуска.
- **№10–12:** старые слоты 24.11, 27.11, 01.12 остаются в действующем манифесте. Не обещать, что
  cron опубликует их: после исправлений страниц исходная привязка больше не совпадает с очередью.
- **№13:** слот 04.12, но Telegram-перевыпуск остаётся на **HOLD** до независимой приёмки цитат,
  нового точного утверждения и отдельной исполнительной авторизации. Исправление страницы не
  снимало HOLD.
- Исторический поштучный QC-readback 13 страниц проверял нормализованный видимый текст,
  а не все узлы, ссылки и медиа. Заголовки в сохранённых аннотациях 13/13 совпали при
  последующей сверке старых записей, не при новой полной проверке 13 страниц; подробности —
  в [журнале QC](../audits/2026-11-21-charnock-qc-reissue-execution-log.md). Страница 04
  занимала 65 450 B, 05 — 65 563 B; их не увеличивать. Потолок 65 536 B относится к
  отправляемому payload, а не обязательно к нормализованному ответу провайдера.

### Расхождение источников — нельзя исправить только датами

Действующий `charnock-reschedule-2026.json` хранит **исторические** Git blobs 06–13, а текущая
очередь после QC ссылается на другие blobs. Проверка текущих локальных файлов и очереди без
провайдера дала следующие префиксы:

| № | blob в манифесте | blob текущей очереди |
|---|---|---|
| 06 | `95ae61f30dbd` | `59030afd7419` |
| 07 | `8673f8d47938` | `1a439d78cb6d` |
| 08 | `278c87293a06` | `9fd43b56d53d` |
| 09 | `bbf90eb3062e` | `5b39c769c81a` |
| 10 | `1173a305bb19` | `cb1819866d98` |
| 11 | `cd64ba6071f0` | `d42392bb593d` |
| 12 | `095de9e09ccf` | `e7ea215bcea9` |
| 13 | `cc9b20e98cb8` | `eedc00889bb2` |

На checkpoint `main@947035bcc2fde9d7a302c265c94e4ffd0fc30de4` и
`state@bca3c01f2455516b2756494452cda7e8cd366098` локальный provider-free preview с гипотетическим
12:05 МСК в каждый из прежних дней для №10–12 поштучно остановился на несовпадении утверждённого
blob **до** intent и обращения к провайдеру. Подробности и полные blob — в
[issue #997](https://github.com/FedorMilovanov/video-channel-manager/issues/997#issuecomment-7078609772).
Это не реальные будущие запуски, не live readback и не гарантия поведения при смене main/state.
Workflow числился active, но текущие release variables через эту интеграцию не прочитаны (403).

Дополнительно `build_telegraph_payload` локально использовал **настоящий `github_sha` оригинальной
квитанции каждого пункта** для media-base URL: текущий payload SHA-256 не совпал с историческим
`source_article_sha256` во всех восьми случаях. Это воспроизводимая локальная проверка сборки,
не live-проверка содержания публичных страниц. Существующий executor требует совпадения даты,
blob очереди, исходной квитанции **и** payload с историческим манифестом. Простая замена дат
или одного SHA его не исправит; переписывать старую квитанцию для обхода несовпадения нельзя.

Нужна отдельно рассмотренная миграция, которая сохраняет неизменную оригинальную идентичность
(удалённый ID, URL и исходный SHA), отдельно связывает проверенную исправленную редакцию с её
новым blob/payload, доказывает содержимое **существующей** страницы и предотвращает повтор при
`verified` или `may_exist`. Для конкретного перевыпуска затем нужны независимая редакционная
приёмка, согласованные даты и отдельная авторизация владельца. До этого существующие
fail-closed проверки должны оставаться включёнными. №09 из миграции на повтор исключён.

## 3. Инструмент наблюдения и неактивный черновик

`charnock-reschedule-2026-proposal-20261121.json` — только черновик: дата №09 в нём возвращена
к исторической и совпадает с действующим манифестом. 06–08 имеют лишь предлагаемые даты;
10–13 не изменены. **Нельзя копировать черновик поверх действующего манифеста**, снимать поле
`proposal_status`, менять recovery-переменные или включать workflow только из-за согласования дат.
Нужны описанные выше проверки и отдельно согласованная миграция источников/очереди/манифеста.

`scripts/lordchrist_telegraph_backlog.py` строит только read-only отчёт. Он различает
оригинальный удалённый ID, matching terminal reissue, отсутствие исходной квитанции,
неоднозначное состояние и рассинхронизацию даты/blob; при отсутствии ledger не предлагает ни
одной даты. В этой ревизии дата reissue берётся из `sent_at_moscow`, а не из времени проверки
или старого расписания; также резервируется фактическая дата исходного, позднее удалённого
сообщения. Если дата отправки неизвестна либо эффект записи неоднозначен, все черновики дат
подавляются до сверки; сам terminal receipt остаётся запретом повтора. Квитанции вне текущей
очереди показываются отдельно, их подтверждённые даты учитываются, но эти записи не становятся
кандидатами на повтор. Интервал учитывает занятые даты по обе стороны и по умолчанию — не менее
двух дней. До 14:00 МСК отчёт может предложить текущий день как *возможное дневное* окно; сам
отчёт ничего не отправляет и не разрешает ночную публикацию. Локальный Git ref может быть
устаревшим.

Для Иуды установлен отдельный **report-only** блокер: старый queued run имеет неизвестную цель,
поэтому даже `--priority` не предлагает дату до отдельной сверки. Для `charnock-history-02`
черновик даты также не предлагается до решения владельца. Эти метки не читают GitHub и сами не
управляют издателем. Отдельно в этой ревизии staged publisher блокирует все четыре этапа для
точного ID и blob Иуды; он не ограничивает старый SHA, внешние writers или изменённые копии и
не проверяет занятость дня. После merge и CI снимать оба ограничения только через рассмотрение
доказательств, не считать их заменой provider reconciliation.

На указанном checkpoint отчёт показывает 9 записей очереди с подтверждёнными/историческими
квитанциями, одного просроченного Иуду, один пункт без даты (`charnock-history-02`) и 7 оставшихся
записей в календаре Чарнока; у всех 7 расходится blob. Дополнительно в ledger есть legacy receipt
`lordchrist-telegraph-history-reformation-1517-01` / Telegram **1593** от 01.11 вне текущей
очереди: не терять и не переиздавать. В этой ревизии ни Иуде, ни history-02 даты не предлагаются
до соответствующей сверки/решения. Публичная доступность и права на повтор отчётом не подтверждаются.
