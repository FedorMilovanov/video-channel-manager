# Реестр источников и сверки

Пакет проверки для статьи «Рабство свободы» (сайт). Всё, что здесь записано, можно повторить
независимо: указаны корпуса, локаторы и точные фрагменты.

## 1. Как проверялось

### 1.1 Писание

Корпус: `bibleonline/rst`, каталог `parsed66/*.dat`, формат `#глава:стих#текст`, Синодальный перевод.
Корпус закреплён по коммиту `00ae4ffbd7a4ac1fb70ebb941109439316e4f5c9` (HEAD на 2026-11-11):

```
git clone https://github.com/bibleonline/rst.git
git -C rst checkout 00ae4ffbd7a4ac1fb70ebb941109439316e4f5c9
```

Проверка идёт в два разных режима, и их нельзя смешивать.

**Режим А — машинная сверка 22 блочных цитат.** Каждая цитата, оформленная блоком с подписью
`> (Книга гл:ст)`, сравнивается с соответствующим диапазоном стихов автоматически. Обе стороны
нормализуются: снимаются HTML-разметка (`<i>`, `&mdash;`), знаки ударения U+0301, пунктуация и регистр,
`ё` приводится к `е`, схлопываются пробелы. Совпадение — по вхождению нормализованной строки в
нормализованный текст стихов; многоточия делят цитату на проверяемые сегменты. Это **не** побайтовое
сравнение: совпадение доказывает, что слова и их порядок те же, но не доказывает совпадение пунктуации,
разбивки на стихи и типографики. Результат на финальном HEAD: `ok 22 fail 0`.

**Режим Б — ручная сверка цитат внутри абзацев.** Короткие вставки в кавычках (Ин. 8:34–36; Рим. 8:7;
1 Кор. 2:14; Еф. 6:4; Кол. 3:21; Мф. 11:28–30; Флп. 2:12–13 и др.) машинной проверкой не покрыты:
граница цитаты внутри предложения определяется вручную. Они сверены чтением против распечатанного
текста тех же стихов из того же корпуса. Это менее надёжно, чем режим А, и так и обозначено.

Всего мест Писания в статье — 41 (22 блочных + 19 внутри абзацев).

### 1.2 Первоисточники

Корпус: `BenjaminPoole/Ecumenical-Christian-Library-Obsidian-Vault`, коммит
`d16898fa04838f1060219e25865b4df8709b2655` (blobless-клон):

```
git clone --filter=blob:none --no-checkout https://github.com/BenjaminPoole/Ecumenical-Christian-Library-Obsidian-Vault.git
git -C … show "HEAD:<путь>"      # чтение конкретного файла
```

Английские тексты читались дословно; русские переводы в статье — собственные, выполнены с этих
английских текстов (Лютер — перевод Генри Коула 1823 г.; Эдвардс — издание Works, vol. 1; Августин —
перевод в составе ECL).

Статус цитат авторов разный, и это надо держать в голове:

| Тип | Что именно подтверждено | Пример |
|---|---|---|
| Прямая сверка по оцифровке | английский текст совпадает с файлом корпуса дословно | Эдвардс, Pt I §4; Лютер, Sect. XXV; Августин, XXII.30 |
| Перевод с английского | русский текст — перевод с проверенного английского; оригинал на языке автора не сверялся | все русские цитаты Лютера, Эдвардса, Уэсли, Сперджена |
| Цитирование через оппонента | текст известен только в передаче другого автора | определение Эразма — по Лютеру, Sect. XLI |

Оригинал `De libero arbitrio` Эразма (латинский текст по LB IX или ASD) не проверялся: в доступных
корпусах его нет. Поэтому определение свободной воли в статье **не** является независимо подтверждённой
цитатой по изданию Эразма — это цитата Эразма в передаче Лютера, и в статье, и здесь это сказано прямо.

### 1.3 Чего проверить не удалось

| Что | Почему | Как обозначено в статье |
|---|---|---|
| *De libero arbitrio* Эразма по критическому изданию (LB IX / Allen) | текст Эразма в доступных корпусах отсутствует | определение Эразма цитируется **по Лютеру** (Sect. XLI), который приводит его как слова Эразма; оригинал Эразма не сверялся — в статье это сказано |
| Печатные лексиконы (BDB, HALOT) постранично | доступны только оцифрованные статьи | ссылка дана на статью BDB/Strong через biblehub (глагол כָּהָה, номер 3543), без выдуманных страниц |
| Нумерация страниц изданий Лютера и Эдвардса | в оцифровках страниц нет | локаторы даны по разделам (Sect. XXV, Pt I §4), а не по страницам |

Ни одна страница, ISBN и точная греческая/еврейская глосса в статье не выдуманы: где точность
недостижима, формулировка осторожнее источника, а не смелее.

## 2. Писание

Синодальный перевод; цитаты в статье даны в этой форме.

| Ссылка | Фрагмент, использованный в статье | Статус |
|---|---|---|
| Ин. 8:31–32 | «если пребудете в слове Моем, то вы истинно Мои ученики, и познаете истину, и истина сделает вас свободными» | сверено |
| Ин. 8:33 | «мы — семя Авраамово и не были рабами никому никогда; как же Ты говоришь: „сделаетесь свободными“?» | сверено |
| Ин. 8:34 | «всякий, делающий грех, есть раб греха» | сверено |
| Ин. 8:35 | «Но раб не пребывает в доме вечно; сын пребывает вечно» | сверено |
| Ин. 8:36 | «если Сын освободит вас, то истинно свободны будете» | сверено |
| Ин. 8:44, 47 | «ваш отец диавол»; «Кто от Бога, тот слушает слова Божии» | сверено |
| Рим. 6:12–14 | «да не царствует грех в смертном вашем теле… грех не должен над вами господствовать» | сверено |
| Рим. 6:16 | «кому вы отдаете себя в рабы для послушания, того вы и рабы…» | сверено |
| Рим. 6:17 | «от сердца стали послушны тому образу учения» | сверено |
| Рим. 6:18 | «Освободившись же от греха, вы стали рабами праведности» | сверено |
| Рим. 6:20 | «когда вы были рабами греха, тогда были свободны от праведности» | сверено |
| Рим. 6:21–23 | «конец их — смерть»; «плод ваш есть святость, а конец — жизнь вечная»; «возмездие за грех — смерть» | сверено |
| Рим. 8:7 | «плотские помышления суть вражда против Бога; ибо закону Божию не покоряются, да и не могут» | сверено |
| Рим. 8:15 | «приняли Духа усыновления» | сверено |
| 1 Кор. 2:14 | «Душевный человек не принимает того, что от Духа Божия… и не может разуметь» | сверено |
| 1 Кор. 9:19 | «будучи свободен от всех, я всем поработил себя» | сверено |
| Гал. 5:1 | «Стойте в свободе, которую даровал нам Христос, и не подвергайтесь опять игу рабства» | сверено |
| Гал. 5:13 | «К свободе призваны вы, братия, только бы свобода ваша не была поводом к угождению плоти» | сверено |
| 2 Пет. 2:19 | «Обещают им свободу, будучи сами рабы тления; ибо кто кем побежден, тот тому и раб» | сверено |
| Пс. 2:1–3 | «Расторгнем узы их, и свергнем с себя оковы их» | сверено |
| Исх. 14:11–12 | «оставь нас, пусть мы работаем Египтянам… лучше быть нам в рабстве у Египтян, нежели умереть в пустыне» | сверено |
| Прит. 5:22–23 | «Беззаконного уловляют собственные беззакония его… он умирает без наставления» | сверено |
| Прит. 13:24 | «Кто жалеет розги своей, тот ненавидит сына» | сверено |
| Прит. 29:15 | «Розга и обличение дают мудрость; но отрок, оставленный в небрежении, делает стыд своей матери» | сверено |
| Мф. 7:13–14 | «Входите тесными вратами… тесны врата и узок путь, ведущие в жизнь» | сверено |
| Мф. 11:28–30 | «Придите ко Мне, все труждающиеся и обремененные… иго Мое благо, и бремя Мое легко» | сверено |
| Лк. 15:17–20 | «придя же в себя»; «побежав, пал ему на шею и целовал его» | сверено |
| Лк. 15:25–32 | старший сын: «я столько лет служу тебе и никогда не преступал приказания твоего» | сверено |
| Евр. 12:5–11 | «Господь, кого любит, того наказывает»; «те наказывали нас по своему произволу» | сверено |
| Еф. 6:1–4 | «Дети, повинуйтесь своим родителям в Господе»; «не раздражайте детей ваших» | сверено |
| Кол. 3:20–21 | «Дети, будьте послушны родителям вашим во всем»; «дабы они не унывали» | сверено |
| 1 Цар. 2:22–25 | «для чего вы делаете такие дела?»; «вы развращаете народ Господень»; «Но они не слушали голоса отца своего» | сверено |
| 1 Цар. 2:29 | «для чего ты предпочитаешь Мне сыновей своих» | сверено |
| 1 Цар. 3:13 | «он знал, как сыновья его нечествуют, и не обуздывал их» | сверено (см. §4 о лексике) |
| 3 Цар. 1:5–6 | «я буду царем»; «Отец же никогда не стеснял его вопросом: для чего ты это делаешь?» | сверено |
| 3 Цар. 2:24–25 | приговор Адонии | сверено |
| Мал. 1:6 | «Сын чтит отца, и раб — господина своего; если Я — отец, то где почтение ко Мне?» | сверено |
| Ин. 6:44 | «Никто не может прийти ко Мне, если не привлечет его Отец» | сверено |
| Ин. 1:12–13 | «ни от крови, ни от хотения плоти… но от Бога родились» | сверено |
| Ин. 15:15 | «Я назвал вас друзьями» | сверено |
| Флп. 2:7 | «уничижил Себя Самого, приняв образ раба» | сверено |
| Флп. 2:12–13 | «Бог производит в вас и хотение и действие по Своему благоволению» | сверено |
| Еф. 2:1–3 | «вас, мертвых по преступлениям и грехам вашим» | сверено |
| Деян. 16:14 | «Господь отверз сердце ее внимать» | сверено |
| 2 Тим. 2:25–26 | «не даст ли им Бог покаяния… чтобы они освободились от сети диавола» | сверено |
| Иез. 36:26–27 | «дам вам сердце новое»; «Вложу внутрь вас дух Мой» | сверено |
| 1 Ин. 5:3 | «заповеди Его не тяжки» | сверено |

## 3. Первоисточники: точные локаторы и фрагменты

### 3.1 Мартин Лютер, *De servo arbitrio* (1525), пер. Генри Коула (1823)

Все фрагменты — из ECL: `05 Reformers (1500–1600)/Martin Luther/The Bondage of the Will/…`.

**L1. Sect. XXV — необходимость неизменяемости, а не принуждения.**

> But, by *necessity,* I do not mean *compulsion;* but (as they term it) the *necessity of immutability,*
> not of *compulsion;* that is, a man void of the Spirit of God, does not evil against his will as by
> violence… but he does it spontaneously, and with a desirous willingness. And this willingness and
> desire of doing evil he cannot, by his own power, leave off, restrain, or change; but it goes on still
> desiring and craving. …This is what we mean by the necessity of immutability: — that the will cannot
> change itself, nor give itself another bent; but rather the more it is resisted, the more it is
> irritated to crave.

Файл: `Luther BW 29 Section XXV.md`. Купюры: два пропуска, оба отмечены «…». Статус: сверено дословно.
Русский перевод в статье — собственный.

**L2. Sect. XXV — скот между двумя всадниками.**

> Thus the human will is, as it were, a beast between the two. If God sit thereon, it wills and goes
> where God will… If Satan sit thereon, it wills and goes as Satan will. Nor is it in the power of its
> own will to choose, to which rider it will run, nor which it will seek; but the riders themselves
> contend, which shall have and hold it.

Тот же файл. Статус: сверено.

**L3. Sect. XXV — «царственная свобода».**

> But if the “stronger than he” come and overcome him, and take us as His spoils, then, through the
> Spirit, we are His servants and captives (which is the royal liberty) that we may desire and do,
> willingly, what He wills.

Тот же файл. Статус: сверено.

**L4. Sect. XXVI — область «ниже себя».**

> …we may, nevertheless, with a good conscience teach, that it be used so far as to allow man a
> “Free-will,” not in respect of those which are above him, but in respect only of those things which
> are below him… but that, God-ward, or in things which pertain unto salvation or damnation, he has no
> “Free-will,” but is a captive, slave, and servant, either to the will of God, or to the will of Satan.

Файл: `Luther BW 30 Section XXVI.md`. Статус: сверено.

**L5. Sect. L — «пустой термин».**

> For when it is granted and established, that “Free-will,” having once lost its liberty, is
> compulsively bound to the service of sin, and cannot will any thing good: I, from these words, can
> understand nothing else than that “Free-will” is a mere empty term, whose reality is lost. And a lost
> liberty, according to my grammar, is no liberty at all. And to give the name of liberty to that which
> has no liberty, is to give it an empty term.

Файл: `Luther BW 54 Section L.md`. Статус: сверено.

**L6. Sect. XLI — определение Эразма, приведённое Лютером.**

> “Moreover I consider Free-will in this light: that it is a power in the human will, by which, a man
> may apply himself to those things which lead unto eternal salvation, or turn away from the same.”

Файл: `Luther BW 43 Section XLI.md` (в статье цитируется как «Эразм, по Лютеру»).
**Ограничение:** текст Эразма по критическому изданию не сверялся; это цитата Эразма в передаче
Лютера. Формулировка совпадает с той, которую передают исследовательские работы, но статус —
«цитируется по Лютеру».

**L7. Sect. XLVII / L — три мнения, которые Диатриба ему приписывает.** Лютер перечисляет три мнения, которые Эразм ему
приписывает, и отвечает, что все три для него — одно. Используется в статье для показа, что спор
шёл не о «малости» свободы, а о её бытии. Файлы: `Luther BW 51 Section XLVII.md`, `BW 54 Section L.md`.

### 3.2 Джонатан Эдвардс, *Freedom of the Will* (1754)

ECL: `07 Revival (1700–1800)/Jonathan Edwards/Volume 1/03 Freedom of the Will/…`.

**E1. Pt I §4 — нравственная неспособность.**

> *Moral* Inability consists not in any of these things; but either in the want of inclination; or the
> strength of a contrary inclination; or the want of sufficient motives in view… Or both these may be
> resolved into one; and it may be said in one word, that moral Inability consists in the opposition or
> want of inclination.

Файл: `Freedom of the Will - 06 Pt 1 Sec 4 Natural and Moral Necessity.md`. Статус: сверено.

**E2. Pt I §4 — «не способность, а желание».**

> …in these things, to ascribe a non-performance to the want of power or ability, is not just; because
> the thing wanting is not a being *able*, but a being *willing*. There are faculties of mind, and a
> capacity of nature, and every thing else, sufficient, but a disposition: nothing is wanting but a will.

Тот же файл. Статус: сверено.

**E3. Pt I §4 — важное самоограничение Эдвардса.**

> But it must be observed concerning moral Inability… that the word *Inability* is used in a sense very
> diverse from its original import… It cannot be truly said, according to the ordinary use of language,
> that… a drunkard, let his appetite be never so strong, cannot keep the cup from his mouth.

Тот же файл. Используется, чтобы не приписывать Эдвардсу грубую формулу «не можешь — значит не
виноват/виноват»: он сам говорит, что «не могу» здесь сказано неточно.

**E4. Pt I §15 — определение свободы.**

> Liberty, as I have explained it, is the power, opportunity, or advantage that any one has to do as he
> pleases, or conducting himself, in any respect, according to his pleasure; without considering how his
> pleasure comes to be as it is.

Файл: `Freedom of the Will - 46 Sec 15 Remarks on Morality Essays.md`. Статус: сверено; в статье
купюра внутри фразы (обозначена).

**E5. Pt I §15 — продолжение о «высшей» свободе.**

> If any imagine they desire, and that they conceive of, a higher and greater liberty than this, they are
> deceived, and delude themselves with confused ambiguous words, instead of ideas.

Тот же файл. Статус: сверено.

**E6. Pt III §4 — заповедь обращена к самой воле.**

> The Will *itself*, and not only those *actions* which are the effects of the Will, is the proper object
> of Precept or Command.

Файл: `Freedom of the Will - 26 Pt 3 Sec 4 Obligation Despite Inability.md`. Статус: сверено.

**E7. Pt III §4 — регресс самодетерминации.**

> …if there be any act, or exertion of the soul, prior to all free acts of choice in the case, directing
> and determining what the acts of the Will shall be; that act of the soul cannot properly be subject to
> any Command or Precept, in any respect whatsoever… And thus the *Arminian* notion of the freedom of the
> Will consisting in the soul’s determining its own acts of Will, instead of being essential to moral
> agency… is utterly inconsistent with it.

Тот же файл. Статус: сверено; купюра обозначена.

**E8. Pt III §4 — воля не может переменить себя.**

> The inclination is unable to change itself; and that for this plain reason, that it is unable to
> incline to change itself.

Тот же файл. Статус: сверено.

**E9. Pt I §2 — воля определяется мотивом (пересказ, не цитата).** Используется как философский тезис
Эдвардса с указанием раздела; в статье помечено, что это философия, а не текст Писания.
Файл: `Freedom of the Will - 04 Pt 1 Sec 2 Determination of the Will.md`.

**E10. Pt II §1, §3–4, §7 — критика «безразличия» и беспричинного выбора.** Пересказ с указанием
разделов; файлы `09 Pt 2 Sec 1 Self-Determining Power.md`, `11 Pt 2 Sec 3 Events without a Cause.md`,
`12 Pt 2 Sec 4 Volition without a Cause.md`, `15 Pt 2 Sec 7 Liberty of Indifference.md`.

### 3.3 Джон Уэсли, «О воспитании детей» (проповедь 95)

ECL: `07 Revival (1700–1800)/John Wesley/Sermons/WS 095 On the Education of Children.md`, §15.

**W1.**

> The harm is, that it strengthens their will more and more, till it will neither bow to God nor man. To
> humour children is, as far as in us lies, to make their disease incurable. A wise parent, on the other
> hand, should begin to break their will the first moment it appears… The will of the parent is to a
> little child in the place of the will of God. Therefore studiously teach them to submit to this while
> they are children, that they may be ready to submit to his will when they are men.

Статус: сверено. Контекст: §15 трактует «self-will» как «первоначальное идолослужение»; речь о
своеволии, а не о личности ребёнка. Купюры в статье обозначены.

**W2.** §1 — Уэсли сам ссылается на Илия как на пример мягкости (в финальной редакции статьи этот
фрагмент не цитируется — сокращён объём главы; сохранён в реестре как свидетельство контекста):

> …those who are in other respects good men have often too much easiness of temper; so that they go no
> farther in restraining their children from evil, than an old Eli did, when he said gently, “Nay, my
> sons, the report I hear of you is not good.”

Статус: сверено. Показывает, что Уэсли читал 1 Цар. так же, как исходная статья, — но с оговоркой,
что это его чтение, а не лексика текста.

**Ограничение:** у Уэсли есть утверждения, которые мы **не** переносим в норму (например, он учит
говорить детям, что они «подобны диаволу» в гордости и похотях, §18). В статье это прямо оговорено.

### 3.4 Августин, *De civitate Dei*, XXII.30

ECL: `02 Church Fathers (c. 95 – 749)/Augustine of Hippo/City of God, Book XXII.md`, глава 30.

**A1.**

> Neither are we to suppose that because sin shall have no power to delight them, free will must be
> withdrawn. It will, on the contrary, be all the more truly free, because set free from delight in
> sinning to take unfailing delight in not sinning. For the first freedom of will which man received
> when he was created upright consisted in an ability not to sin, but also in an ability to sin; whereas
> this last freedom of will shall be superior, inasmuch as it shall not be able to sin.

**A2 — аргумент, которого не было в Telegram-версии.**

> Are we to say that God Himself is not free because He cannot sin? In that city, then, there shall be
> free will, one in all the citizens, and indivisible in each…

Статус: сверено дословно.

### 3.5 Чарльз Сперджен, проповедь № 915 «Sinners Bound with the Cords of Sin» (1870), на Прит. 5:22

ECL: `08 Victorian (1800–1900)/Charles Spurgeon/Sermons/Volume 16 (1870)/Sermon 0915 Sinners Bound with the Cords of Sin.md`.

**S1.**

> Samson could burst asunder green withes and new ropes, but when at last his darling sin had bound him
> to his Delilah, that bond he could not snap, though it cost him his eyes. Make a man’s will a prisoner,
> and he is a captive indeed… a mind enslaved by sin builds its own dungeon, forges its own fetters, and
> rivets on its chains. It is slavery indeed when the iron enters into the soul.

Статус: сверено; купюра обозначена.

**S2.**

> …only suffer a sinner to do what he wills, and to give his lusts unbridled headway, and you have
> secured him boundless misery; only allow the seething caldron of his corruptions to boil at its own
> pleasure, and the man must inevitably become a vessel filled with sorrow.

Статус: сверено.

**S3** (используется в новой статье):

> …thou hast destroyed thyself, but thou canst not save thyself; thou hast woven the net, thou hast made
> it fast and firm, but thou canst not tear it in pieces. But there is One who can…

Статус: сверено.

## 4. Лексика оригиналов

### 4.1 1 Цар. 3:13 — כִּהָה (kihah)

Форма: Piel, perfect, 3 m. s., с предлогом בְּ: וְלֹא כִהָה בָּם — «и не укорил их / не обличил их».

Данные, на которых строится осторожная формулировка:

- **BDB**: I. כָּהָה — «be or grow dim, faint» (Qal: Втор. 34:7; Ис. 42:4; Зах. 11:17); **II. כָּהָה
  Piʿel — «rebuke»**, и отмечено, что эта форма встречается **только** в 1 Цар. 3:13 (hapax
  legomenon) с предлогом בְּ.
- **Strong/HALOT-производные глоссы**: darken, be dim, fail, faint, **restrain**, rebuke.
- **LXX**: «и не вразумлял (не обличал) их» — без идеи физического удержания.
- **Синодальный**: «не обуздывал их». **KJV**: «he restrained them not». **NASB**: «he did not rebuke
  them».

**Вывод для статьи:** значение — «укорять, обличать, останавливать словом»; «сильное, резкое
удержание» (формулировка Telegram-версии) лексикой не поддерживается. Слово редкое, поэтому в статье
сказано: «не укорил, не остановил», и отдельно отмечено, что за этой редкостью нельзя прятать
очевидное — Илий **говорил** с сыновьями (2:23–25), и обвинение не в молчании, а в том, что слово не
стало делом (ср. 2:29).

Источники: статья BDB/Strong 3543 (biblehub.com/hebrew/3543.htm), лексические сводки
(biblehub.com/lexicon/1_samuel/3-13.htm), LXX 1 Цар. 3:13.

### 4.2 3 Цар. 1:6 — לֹא־עֲצָבוֹ (lo-atsavo)

Буквально: «не огорчал его (не причинял ему огорчения)». Синодальный: «никогда не стеснял его
вопросом: для чего ты это делаешь?»; KJV: «had not displeased him at any time in saying, Why hast thou
done so?».

**Вывод для статьи:** речь о том, что отец ни разу не пересёк волю сына и не спросил с него; точная
глосса («огорчал / перечил / обличал») на вывод не влияет, поэтому в статье нет опоры на одно
словарное значение.

### 4.3 Греческий (Ин. 8; Рим. 6)

- ὁ ποιῶν τὴν ἁμαρτίαν (8:34) — причастие настоящего времени: «делающий» как характеристика.
- δοῦλος (8:34–35) — «невольник», не «наёмный слуга».
- μένει εἰς τὸν αἰῶνα (8:35) — «пребывает в век»: постоянство статуса в доме.
- ἐλευθερώσει (8:36) — будущее от ἐλευθερόω, «освободит»: действие Сына, не усилие раба.
- ἀπὸ τῆς ἁμαρτίας ἐλευθερωθέντες (6:18) — «освободившись от греха» (аорист).
- ἐδουλώθητε τῇ δικαιοσύνῃ (6:18) — «порабощены праведности» (аорист, страдательный).
- ὑπηκούσατε δὲ ἐκ καρδίας (6:17) — «стали послушны от сердца».

Значения даны по общепринятым лексическим данным; постраничные ссылки на печатные лексиконы не
приводятся, чтобы не выдумывать страницы.

## 5. Внешняя сверка: статья сайта «Свобода во Христе»

Репозиторий `FedorMilovanov/gb-is-my-strength`, файл `src/content/articles/svoboda-vo-hriste.mdx`
(23 150 байт; в frontmatter `publishedAt: 2026-07-11`, `series: hard-texts`; репозиторий закреплён по коммиту `ccb1e6cfe8a1324fd988260577bd61337f3ca74d`). Читалась как внешний источник
сопоставления; не изменялась.

Ключевые места, с которыми разведена новая статья:

- «Коротко», п. 3: «мы свободны от *престола* греха, но не от его *присутствия*» — тема продолжающейся
  борьбы; в новой статье **не дублируется**, дана перекрёстная ссылка.
- Раздел `prestol-ne-prisutstvie` — там же.
- `net-svobody-bez-hozyaina` — совпадает с Рим. 6:16; новая статья опирается на этот текст, но ведёт
  его к вопросу о природе воли (Эдвардс, Лютер), а не к теме борьбы.
- `istochniki` — формат блока источников; в новой статье он сохранён как конвенция сайта.

## 6. Итог по цитатам

Счёт по финальной редакции `04-site-article.md` (проверяется командой `grep -c "^> ("`):

| Автор | Блочных цитат | Сверено дословно | Цитируется по посреднику |
|---|---|---|---|
| Писание (Синодальный) | 22 | 22 | — |
| Лютер, *De servo arbitrio* | 5 | 5 | — |
| Эразм (определение) | 1 | — | 1 (по Лютеру, Sect. XLI) |
| Эдвардс, *Freedom of the Will* | 7 | 7 | — |
| Уэсли, «О воспитании детей» | 2 | 2 | — |
| Августин, *De civ. Dei* XXII.30 | 2 | 2 | — |
| Сперджен, проповедь 915 | 2 | 2 | — |

Сверх блочных цитат в тексте есть короткие вставки Писания в кавычках (всего 41 место Писания, включая
блочные). Ни одна цитата не приведена «по памяти»: у каждой есть локатор и оцифровка, по которой её можно
проверить заново командами из §1.
