"""Deterministic fixtures for the Telegram rich renderer golden tests.

All fixtures are ``RichArticleDocument`` instances of the merged provider-
neutral domain contract. They exercise headings, lists (bullet/ordered/task),
inline formatting, block quotes, pre blocks, tables, formulas, footnotes,
Unicode emoji (which proves UTF-16 entity offsets), and the verified media
patterns: standalone media blocks, collage blocks, and slideshow blocks.
"""

from __future__ import annotations

from datetime import date

from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichBlockCaption,
    RichBlockCollage,
    RichBlockDetails,
    RichBlockDivider,
    RichBlockFooter,
    RichBlockHeading,
    RichBlockList,
    RichBlockMath,
    RichBlockMedia,
    RichBlockParagraph,
    RichBlockPreformatted,
    RichBlockQuote,
    RichBlockSlideshow,
    RichBlockTable,
    RichListItem,
    RichMediaRef,
    RichTableCell,
    RichTextBold,
    RichTextCode,
    RichTextCustomEmoji,
    RichTextItalic,
    RichTextMarked,
    RichTextMath,
    RichTextReferenceLink,
    RichTextSpoiler,
    RichTextStrikethrough,
    RichTextSubscript,
    RichTextSuperscript,
    RichTextUnderline,
    RichTextUrl,
    RichArticleMetadata,
)

MEDIA_URI = "https://media.example.org"


def media_photo(media_id: str, alt_text: str | None = None) -> RichMediaRef:
    return RichMediaRef(media_id=media_id, kind="photo", uri=f"{MEDIA_URI}/{media_id}.jpg", alt_text=alt_text)


def caption(text: str, credit: str | None = None) -> RichBlockCaption:
    return RichBlockCaption(text=text, credit=credit)


def doc(
    document_id: str,
    title: str,
    blocks: tuple[object, ...],
    media: tuple[RichMediaRef, ...] = (),
    *,
    tags: tuple[str, ...] = (),
) -> RichArticleDocument:
    return RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id=document_id,
        project_key="svodka",
        metadata=RichArticleMetadata(
            title=title,
            language="ru",
            summary="Сводка для детерминированного рендеринга.",
            author="Редакция",
            tags=tags,
            created_at=date(2026, 8, 10),
        ),
        blocks=tuple(block for block in blocks if block is not None),
        media=media,
    )


def scientific_article() -> RichArticleDocument:
    return doc(
        "science-quantum-entanglement-2026",
        "Квантовая запутанность: новый рубеж",
        (
            RichBlockParagraph(
                block_id="p-intro",
                text=(
                    "🔬 В 2026 году коллаборация проверила ",
                    RichTextBold(text="спутанность"),
                    " на дистанции 120 км; погрешность — ",
                    RichTextCode(text="λ = 2,1 нм"),
                    ", результат ",
                    RichTextUrl(text="опубликован", url="https://arxiv.org/abs/2606.00001"),
                    ".",
                ),
            ),
            RichBlockHeading(block_id="h-method", text="Методология", size=2),
            RichBlockParagraph(
                block_id="p-method",
                text=(
                    "Эксперимент использовал ",
                    RichTextItalic(text="четыре детектора"),
                    " и ",
                    RichTextUnderline(text="два независимых канала"),
                    ". Контрольные прогоны помечены ",
                    RichTextSpoiler(text="секретно"),
                    ", а старые гипотезы ",
                    RichTextStrikethrough(text="опровергнуты"),
                    ". 📊",
                ),
            ),
            RichBlockPreformatted(
                block_id="pre-python",
                text="def correlate(photons):\n    return sum(photons) / len(photons)",
                language="python",
            ),
            RichBlockQuote(
                block_id="q-bell",
                blocks=(
                    RichBlockParagraph(
                        block_id="q-bell-p",
                        text=(
                            "Корреляция сама по себе ещё не означает причинности, "
                            "но здесь разрыв неравенства Белла превышает 12 сигм."
                        ),
                    ),
                ),
            ),
            RichBlockParagraph(
                block_id="p-outro",
                text="Выводы требуют воспроизводимости на второй площадке.",
            ),
            RichBlockFooter(
                block_id="f-sources",
                text=(
                    "Источники: ",
                    RichTextUrl(text="arXiv", url="https://arxiv.org/abs/2606.00001"),
                    ", ",
                    RichTextUrl(text="Журнал экспериментальной физики", url="https://example.org/jep/2026/07"),
                ),
            ),
        ),
        tags=("наука", "физика"),
    )


def historical_article() -> RichArticleDocument:
    return doc(
        "history-hastings-1066",
        "Битва при Гастингсе: 14 октября 1066 года",
        (
            RichBlockParagraph(
                block_id="p-intro",
                text="📜 Сражение при Гастингсе решило судьбу английского престола.",
            ),
            RichBlockHeading(block_id="h-chrono", text="Хронология", size=2),
            RichBlockList(
                block_id="l-chrono",
                items=(
                    RichListItem(
                        blocks=(
                            RichBlockParagraph(block_id="l-c-1", text="Утро: нормандская армия строится в три линии"),
                        )
                    ),
                    RichListItem(
                        blocks=(
                            RichBlockParagraph(
                                block_id="l-c-2",
                                text=("День: ", RichTextItalic(text="фаланга"), " держит вал до вечера"),
                            ),
                        ),
                    ),
                    RichListItem(
                        blocks=(
                            RichBlockParagraph(
                                block_id="l-c-3",
                                text=("Вечер: гибель Гарольда и ", RichTextBold(text="перелом"), " битвы"),
                            ),
                        ),
                    ),
                ),
            ),
            RichBlockQuote(
                block_id="q-chronicle",
                blocks=(
                    RichBlockParagraph(
                        block_id="q-chronicle-p",
                        text="Согласно хронике, знамя Гарольда пало вместе с королём.",
                    ),
                ),
            ),
            RichBlockParagraph(
                block_id="p-outro",
                text=(
                    "Историки спорят о численности армий; ",
                    RichTextUrl(text="обзор дискуссии", url="https://example.org/hastings/overview"),
                    ".",
                ),
            ),
        ),
        tags=("история",),
    )


def top10_list_article() -> RichArticleDocument:
    titles = (
        "К. С. Льюис — «Просто христианство»",
        "Г. К. Честертон — «Вечный человек»",
        "«Бог и наука» — сборник эссе",
        "Джош Макдауэлл — «Неоспоримые свидетельства»",
        None,  # replaced below with a formatted item
        "«Разум веры» — антология",
        "Э. Л. Таунз — «Библия и наука»",
        "«Убеждать разумно» — практикум апологета",
        None,  # replaced below with an italic item
        "«Возвращение к доводам» — сборник 2024 года",
    )
    items: list[RichListItem] = []
    for index, title in enumerate(titles, start=1):
        if index == 5:
            text = ("Ли Строубел — «", RichTextBold(text="Дело Христа"), "»")
        elif index == 9:
            text = (RichTextItalic(text="Ф. Шеффер — «Бог, Который есть»"),)
        else:
            assert title is not None
            text = title
        items.append(
            RichListItem(
                blocks=(RichBlockParagraph(block_id=f"t10-item-{index}", text=text),),
                label_type="1",
            )
        )
    return doc(
        "top10-apologetics-books",
        "Топ-10 книг по апологетике",
        (
            RichBlockParagraph(
                block_id="p-intro",
                text="Подборка составлена по читательским голосам 2025 года. ⭐",
            ),
            RichBlockList(block_id="l-top10", items=tuple(items)),
            RichBlockHeading(block_id="h-summary", text="Итог", size=3),
            RichBlockParagraph(
                block_id="p-summary",
                text=("Первую тройку возглавляют ", RichTextItalic(text="классические"), " работы."),
            ),
        ),
        tags=("книги",),
    )


def theological_reflection_article() -> RichArticleDocument:
    return doc(
        "theology-grace-reflection",
        "Размышление о благодати",
        (
            RichBlockParagraph(
                block_id="p-intro",
                text="🕊️ Благодать — это не заслуга, а дар, который меняет само желание сердца.",
            ),
            RichBlockQuote(
                block_id="q-eph",
                blocks=(
                    RichBlockParagraph(
                        block_id="q-eph-p",
                        text=(RichTextBold(text="Благодатью вы спасены через веру, и сие не от вас, Божий дар."),),
                    ),
                ),
            ),
            RichBlockParagraph(block_id="p-warn", text="Важно не превращать дар в повод для самоуверенности."),
            RichBlockQuote(
                block_id="q-faithful",
                blocks=(
                    RichBlockParagraph(
                        block_id="q-faithful-p",
                        text=(RichTextItalic(text="Не потому, что я достоин, а потому, что Он верен."),),
                    ),
                ),
            ),
            RichBlockHeading(block_id="h-steps", text="Три шага", size=2),
            RichBlockList(
                block_id="l-steps",
                items=(
                    RichListItem(blocks=(RichBlockParagraph(block_id="s-1", text="Признать нужду"),)),
                    RichListItem(blocks=(RichBlockParagraph(block_id="s-2", text="Принять дар с благодарностью"),)),
                    RichListItem(blocks=(RichBlockParagraph(block_id="s-3", text="Делиться им с ближними"),)),
                ),
            ),
            RichBlockParagraph(
                block_id="p-prayer",
                text=(
                    "Размышление завершается молитвой, которую можно прочесть ",
                    RichTextUrl(text="здесь", url="https://example.org/prayer"),
                    ".",
                ),
            ),
        ),
        tags=("духовное",),
    )


def inline_images_article() -> RichArticleDocument:
    return doc(
        "travel-optina-pilgrimage",
        "Паломничество в Оптину пустынь",
        (
            RichBlockParagraph(block_id="p-intro", text="Фотоотчёт об одной поездке. 🧭"),
            RichBlockMedia(
                block_id="m-vrat",
                media_id="photo-vrat",
                caption=caption("Врата обители, 6:40 утра"),
            ),
            RichBlockParagraph(block_id="p-vrat", text="Входные врата обители открываются рано утром."),
            RichBlockMedia(
                block_id="m-khram",
                media_id="photo-khram",
                caption=caption("Иконостас главного храма"),
            ),
            RichBlockHeading(block_id="h-khram", text="Главный храм", size=2),
            RichBlockParagraph(block_id="p-khram", text="Интерьер храма — отдельная история."),
            RichBlockMedia(block_id="m-skit", media_id="photo-skit"),
            RichBlockParagraph(block_id="p-skit", text="Дорога к скиту идёт через берёзовую рощу."),
        ),
        media=(
            media_photo("photo-vrat"),
            media_photo("photo-khram"),
            media_photo("photo-skit"),
        ),
        tags=("путешествия",),
    )


def collage_article() -> RichArticleDocument:
    return doc(
        "expo-light-shadow-report",
        "Фотоотчёт: выставка «Свет и тень»",
        (
            RichBlockParagraph(block_id="p-intro", text="Четыре кадра с вернисажа. 🎨"),
            RichBlockCollage(
                block_id="c-expo",
                blocks=(
                    RichBlockMedia(block_id="c-1", media_id="exp-01"),
                    RichBlockMedia(block_id="c-2", media_id="exp-02"),
                    RichBlockMedia(block_id="c-3", media_id="exp-03"),
                    RichBlockMedia(block_id="c-4", media_id="exp-04"),
                ),
                caption=caption("Вернисаж, общий план"),
            ),
            RichBlockParagraph(
                block_id="p-review",
                text=(
                    "Подробный обзор — по ссылке ",
                    RichTextUrl(text="в конце", url="https://example.org/expo/review"),
                    ".",
                ),
            ),
        ),
        media=(
            media_photo("exp-01"),
            media_photo("exp-02"),
            media_photo("exp-03"),
            media_photo("exp-04"),
        ),
        tags=("искусство",),
    )


def slideshow_article() -> RichArticleDocument:
    return doc(
        "karelia-landscapes-slideshow",
        "Пейзажи Карелии",
        (
            RichBlockParagraph(block_id="p-intro", text="Четыре остановки на маршруте. 🏞️"),
            RichBlockSlideshow(
                block_id="s-karelia",
                blocks=(
                    RichBlockMedia(block_id="s-1", media_id="kar-01", caption=caption("Ладожские шхеры на рассвете")),
                    RichBlockMedia(block_id="s-2", media_id="kar-02", caption=caption("Водопад Кивач")),
                    RichBlockMedia(block_id="s-3", media_id="kar-03", caption=caption("Озеро с каменным островом")),
                    RichBlockMedia(block_id="s-4", media_id="kar-04", caption=caption("Закат над лесом")),
                ),
            ),
            RichBlockParagraph(block_id="p-outro", text="Маршрут занял три дня."),
        ),
        media=(
            media_photo("kar-01"),
            media_photo("kar-02"),
            media_photo("kar-03"),
            media_photo("kar-04"),
        ),
        tags=("путешествия", "природа"),
    )


def fallback_mixed_article() -> RichArticleDocument:
    return doc(
        "fallback-mixed-review",
        "Обзор: рендеринг и падение в legacy HTML",
        (
            RichBlockParagraph(
                block_id="p-inline",
                text=(
                    "Текст с эмодзи ✅ и ",
                    RichTextBold(text="жирным"),
                    ", ",
                    RichTextItalic(text="курсивом"),
                    ", ",
                    RichTextUnderline(text="подчёркиванием"),
                    ", ",
                    RichTextStrikethrough(text="зачёркиванием"),
                    ", ",
                    RichTextSpoiler(text="спойлером"),
                    " и ",
                    RichTextMarked(text="выделением"),
                    ". Затем ",
                    RichTextCode(text="code()"),
                    ", ",
                    RichTextSubscript(text="нижний"),
                    ", ",
                    RichTextSuperscript(text="верхний"),
                    " индексы, формула ",
                    RichTextMath(expression="x^2"),
                    ", сноска ",
                    RichTextReferenceLink(text="[1]", reference_name="src1"),
                    " и ссылка ",
                    RichTextUrl(text="на источник", url="https://example.org/source"),
                    ", а также ",
                    RichTextCustomEmoji(custom_emoji_id="5368324170671202286", alternative_text="👍"),
                    ".",
                ),
            ),
            RichBlockHeading(block_id="h-structure", text="Структура", size=2),
            RichBlockList(
                block_id="l-bullets",
                items=(
                    RichListItem(blocks=(RichBlockParagraph(block_id="b-1", text="Абзацы сохраняются"),)),
                    RichListItem(blocks=(RichBlockParagraph(block_id="b-2", text="Списки получают маркеры"),)),
                ),
            ),
            RichBlockList(
                block_id="l-ordered",
                items=(
                    RichListItem(blocks=(RichBlockParagraph(block_id="o-1", text="Первый"),), label_type="1"),
                    RichListItem(blocks=(RichBlockParagraph(block_id="o-2", text="Второй"),), label_type="1"),
                    RichListItem(blocks=(RichBlockParagraph(block_id="o-3", text="Третий"),), label_type="1"),
                ),
            ),
            RichBlockQuote(
                block_id="q-fallback",
                blocks=(
                    RichBlockParagraph(
                        block_id="q-fallback-p",
                        text=(RichTextBold(text="Цитата внутри fallback-рендера."),),
                    ),
                ),
            ),
            RichBlockPreformatted(block_id="pre-bash", text="echo legacy-html", language="bash"),
            RichBlockDivider(block_id="d-1"),
            RichBlockMath(block_id="math-1", expression="E = mc^2"),
            RichBlockTable(
                block_id="t-1",
                cells=(
                    (RichTableCell(text="Метрика", is_header=True), RichTableCell(text="Значение", is_header=True)),
                    (RichTableCell(text="Скорость"), RichTableCell(text=(RichTextBold(text="42"), " мс"))),
                    (RichTableCell(text="Статус"), RichTableCell(text="готово")),
                ),
                caption="Таблица результатов",
            ),
            RichBlockDetails(
                block_id="det-1",
                summary="Подробности",
                blocks=(RichBlockParagraph(block_id="det-1-p", text="Скрытый текст разворачивается."),),
            ),
            RichBlockMedia(block_id="m-fallback", media_id="fb-01", caption=caption("Кадр для downgrade")),
            RichBlockParagraph(block_id="p-final", text="После медиа идёт финальный абзац."),
            RichBlockFooter(
                block_id="f-fallback",
                text=(
                    "Источники: ",
                    RichTextUrl(text="Документация Bot API", url="https://core.telegram.org/bots/api"),
                ),
            ),
        ),
        media=(media_photo("fb-01"),),
        tags=("рендеринг",),
    )


ALL_RICH_SCENARIOS: tuple[tuple[str, RichArticleDocument], ...] = (
    ("scientific-article", scientific_article()),
    ("historical-article", historical_article()),
    ("top10-list", top10_list_article()),
    ("theological-reflection", theological_reflection_article()),
    ("inline-images", inline_images_article()),
    ("collage", collage_article()),
    ("slideshow", slideshow_article()),
)

FALLBACK_MIXED: RichArticleDocument = fallback_mixed_article()
