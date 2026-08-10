"""Deterministic fixtures for the Telegram rich bridge tests.

The renderer fixtures are ``RichArticleDocument`` instances covering every
verified Bot API 10.2 block family: scientific/historical articles, lists,
quotes, tables, formulas, details, inline media, collage, and slideshow.
"""

from __future__ import annotations

from datetime import date

from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichArticleMetadata,
    RichArticleSource,
    RichBlockCaption,
    RichBlockCollage,
    RichBlockDetails,
    RichBlockDivider,
    RichBlockFooter,
    RichBlockHeading,
    RichBlockList,
    RichBlockMap,
    RichBlockMath,
    RichBlockMedia,
    RichBlockParagraph,
    RichBlockPreformatted,
    RichBlockPullQuote,
    RichBlockQuote,
    RichBlockSlideshow,
    RichBlockTable,
    RichListItem,
    RichMediaItem,
    RichResolvedFile,
    RichTableCell,
    RichTextBold,
    RichTextCode,
    RichTextItalic,
    RichTextMath,
    RichTextReferenceLink,
    RichTextSpoiler,
    RichTextStrikethrough,
    RichTextSubscript,
    RichTextSuperscript,
    RichTextUnderline,
    RichTextUrl,
)

MEDIA_URI = "https://media.example.org"


def media(media_id: str, kind: str = "photo", *, resolved: bool = True) -> RichMediaItem:
    return RichMediaItem(
        media_id=media_id,
        kind=kind,  # type: ignore[arg-type]
        uri=f"{MEDIA_URI}/{media_id}.jpg",
        alt_text=f"Альт для {media_id}",
        resolved=(
            RichResolvedFile(
                file_id=f"file-id-{media_id}",
                file_unique_id=f"unique-{media_id}",
                width=1280,
                height=720,
                duration=0,
                file_size=123456,
            )
            if resolved
            else None
        ),
    )


def caption(text: str, credit: str | None = None) -> RichBlockCaption:
    return RichBlockCaption(text=text, credit=credit)


def doc(
    document_id: str,
    title: str,
    blocks: tuple[object, ...],
    *,
    media: tuple[RichMediaItem, ...] = (),
    sources: tuple[RichArticleSource, ...] = (),
) -> RichArticleDocument:
    return RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id=document_id,
        project_key="svodka",
        metadata=RichArticleMetadata(
            title=title,
            language="ru",
            created_at=date(2026, 8, 10),
        ),
        blocks=tuple(block for block in blocks if block is not None),
        media=media,
        sources=sources,
    )


def scientific_article() -> RichArticleDocument:
    return doc(
        "science-quantum-entanglement-2026",
        "Квантовая запутанность: новый рубеж",
        (
            RichBlockHeading(block_id="h-title", text="Квантовая запутанность: новый рубеж", size=1),
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
                    ".",
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
                        text="Корреляция сама по себе ещё не означает причинности, но разрыв неравенства Белла превышает 12 сигм.",
                    ),
                ),
            ),
            RichBlockFooter(
                block_id="f-sources",
                text=("Источники: ", RichTextUrl(text="arXiv", url="https://arxiv.org/abs/2606.00001")),
            ),
        ),
        sources=(RichArticleSource(source_id="src-arxiv", label="arXiv", url="https://arxiv.org/abs/2606.00001"),),
    )


def historical_article() -> RichArticleDocument:
    return doc(
        "history-hastings-1066",
        "Битва при Гастингсе: 14 октября 1066 года",
        (
            RichBlockHeading(block_id="h-title", text="Битва при Гастингсе: 14 октября 1066 года", size=1),
            RichBlockParagraph(block_id="p-intro", text="📜 Сражение решило судьбу английского престола."),
            RichBlockHeading(block_id="h-chrono", text="Хронология", size=2),
            RichBlockList(
                block_id="l-chrono",
                items=(
                    RichListItem(
                        blocks=(
                            RichBlockParagraph(block_id="l-1", text="Утро: нормандская армия строится в три линии"),
                        )
                    ),
                    RichListItem(
                        blocks=(
                            RichBlockParagraph(
                                block_id="l-2", text=("День: ", RichTextItalic(text="фаланга"), " держит вал")
                            ),
                        )
                    ),
                ),
            ),
            RichBlockQuote(
                block_id="q-chronicle",
                blocks=(
                    RichBlockParagraph(block_id="q-1", text="Согласно хронике, знамя Гарольда пало вместе с королём."),
                ),
            ),
        ),
    )


def list_article() -> RichArticleDocument:
    return doc(
        "top10-apologetics-books",
        "Топ-10 книг по апологетике",
        (
            RichBlockHeading(block_id="h-title", text="Топ-10 книг по апологетике", size=1),
            RichBlockList(
                block_id="l-top10",
                items=tuple(
                    RichListItem(
                        blocks=(RichBlockParagraph(block_id=f"t10-{index}", text=title),),
                        label_type="1",
                    )
                    for index, title in enumerate(
                        (
                            "К. С. Льюис — «Просто христианство»",
                            "Г. К. Честертон — «Вечный человек»",
                            "«Бог и наука» — сборник эссе",
                            "Джош Макдауэлл — «Неоспоримые свидетельства»",
                        ),
                        start=1,
                    )
                ),
            ),
            RichBlockList(
                block_id="l-bullets",
                items=(
                    RichListItem(blocks=(RichBlockParagraph(block_id="b-1", text="Пункт один"),)),
                    RichListItem(blocks=(RichBlockParagraph(block_id="b-2", text="Пункт два"),)),
                ),
            ),
        ),
    )


def quote_article() -> RichArticleDocument:
    return doc(
        "theology-grace-reflection",
        "Размышление о благодати",
        (
            RichBlockHeading(block_id="h-title", text="Размышление о благодати", size=1),
            RichBlockParagraph(block_id="p-intro", text="🕊️ Благодать — это дар."),
            RichBlockQuote(
                block_id="q-eph",
                credit="Еф. 2:8",
                blocks=(
                    RichBlockParagraph(
                        block_id="q-1",
                        text=(RichTextBold(text="Благодатью вы спасены через веру, и сие не от вас, Божий дар."),),
                    ),
                ),
            ),
            RichBlockPullQuote(
                block_id="q-pull",
                text="Не потому, что я достоин, а потому, что Он верен.",
                credit="Автор размышления",
            ),
        ),
    )


def table_article() -> RichArticleDocument:
    return doc(
        "table-metrics-demo",
        "Таблица метрик",
        (
            RichBlockHeading(block_id="h-title", text="Таблица метрик", size=1),
            RichBlockTable(
                block_id="t-1",
                caption="Результаты",
                cells=(
                    (RichTableCell(text="Метрика", is_header=True), RichTableCell(text="Значение", is_header=True)),
                    (RichTableCell(text="Скорость"), RichTableCell(text=(RichTextBold(text="42"), " мс"))),
                    (RichTableCell(text="Статус"), RichTableCell(text="готово")),
                ),
                is_bordered=True,
                is_striped=True,
            ),
        ),
    )


def formula_details_article() -> RichArticleDocument:
    return doc(
        "formula-details-demo",
        "Формулы и детали",
        (
            RichBlockHeading(block_id="h-title", text="Формулы и детали", size=1),
            RichBlockMath(block_id="m-1", expression="E = mc^2"),
            RichBlockParagraph(
                block_id="p-1",
                text=(
                    "Инлайн: ",
                    RichTextMath(expression="a^2 + b^2 = c^2"),
                    " и ",
                    RichTextSubscript(text="нижний"),
                    RichTextSuperscript(text="верхний"),
                    ".",
                ),
            ),
            RichBlockDetails(
                block_id="d-1",
                summary="Подробности",
                blocks=(RichBlockParagraph(block_id="d-1-p", text="Скрытый текст разворачивается."),),
            ),
            RichBlockDivider(block_id="div-1"),
        ),
    )


def inline_media_article() -> RichArticleDocument:
    return doc(
        "travel-optina-pilgrimage",
        "Паломничество в Оптину пустынь",
        (
            RichBlockHeading(block_id="h-title", text="Паломничество в Оптину пустынь", size=1),
            RichBlockParagraph(block_id="p-1", text="Фотоотчёт об одной поездке. 🧭"),
            RichBlockMedia(block_id="m-1", media_id="photo-vrat", caption=caption("Врата обители, 6:40 утра")),
            RichBlockParagraph(block_id="p-2", text="Входные врата обители открываются рано утром."),
            RichBlockMedia(block_id="m-2", media_id="photo-khram", caption=caption("Иконостас главного храма")),
            RichBlockMedia(block_id="m-3", media_id="photo-skit"),
        ),
        media=(media("photo-vrat"), media("photo-khram"), media("photo-skit")),
    )


def collage_article() -> RichArticleDocument:
    return doc(
        "expo-light-shadow-report",
        "Фотоотчёт: выставка «Свет и тень»",
        (
            RichBlockHeading(block_id="h-title", text="Фотоотчёт: выставка «Свет и тень»", size=1),
            RichBlockParagraph(block_id="p-1", text="Четыре кадра с вернисажа. 🎨"),
            RichBlockCollage(
                block_id="c-1",
                caption=caption("Вернисаж, общий план"),
                blocks=(
                    RichBlockMedia(block_id="c-1-m", media_id="exp-01"),
                    RichBlockMedia(block_id="c-2-m", media_id="exp-02"),
                    RichBlockMedia(block_id="c-3-m", media_id="exp-03"),
                ),
            ),
        ),
        media=(media("exp-01"), media("exp-02"), media("exp-03")),
    )


def slideshow_article() -> RichArticleDocument:
    return doc(
        "karelia-landscapes-slideshow",
        "Пейзажи Карелии",
        (
            RichBlockHeading(block_id="h-title", text="Пейзажи Карелии", size=1),
            RichBlockSlideshow(
                block_id="s-1",
                caption=caption("Маршрут"),
                blocks=(
                    RichBlockMedia(block_id="s-1-m", media_id="kar-01", caption=caption("Ладожские шхеры")),
                    RichBlockMedia(block_id="s-2-m", media_id="kar-02", caption=caption("Водопад Кивач")),
                ),
            ),
        ),
        media=(media("kar-01"), media("kar-02")),
    )


def map_details_article() -> RichArticleDocument:
    return doc(
        "map-demo-article",
        "Карта и детали",
        (
            RichBlockHeading(block_id="h-title", text="Карта и детали", size=1),
            RichBlockMap(
                block_id="map-1",
                location=(55.751244, 37.618423),
                zoom=14,
                width=640,
                height=480,
                caption=caption("Москва"),
            ),
            RichBlockParagraph(
                block_id="p-1",
                text=("Сноска ", RichTextReferenceLink(text="[1]", reference_name="src-1"), "."),
            ),
        ),
        sources=(RichArticleSource(source_id="src-1", label="Источник", url="https://example.org/src-1"),),
    )


ALL_RENDER_SCENARIOS: tuple[tuple[str, RichArticleDocument], ...] = (
    ("scientific", scientific_article()),
    ("historical", historical_article()),
    ("list", list_article()),
    ("quote", quote_article()),
    ("table", table_article()),
    ("formula-details", formula_details_article()),
    ("inline-media", inline_media_article()),
    ("collage", collage_article()),
    ("slideshow", slideshow_article()),
    ("map-details", map_details_article()),
)
