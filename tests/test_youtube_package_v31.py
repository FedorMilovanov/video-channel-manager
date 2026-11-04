"""Owner's v3.1 is a new manual package, never retroactive live copy enforcement."""

from __future__ import annotations

from video_channel_manager.youtube_package_v31 import validate_five_block_package

YESENIN = "https://www.youtube.com/playlist?list=PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q"
SINGING = "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8"


def make_package() -> str:
    titles = "\n".join(
        [
            "Есенин ⚡ СЕРДЦЕ ПРОДОЛЖАЕТ ПЕТЬ ⚡ Сергей Есенин",
            "Поэтический цикл ⚡ ЗНАКИ ВРЕМЕНИ ⚡ Сергей Есенин",
            "Есенин: страницы жизни ⚡ СТИХИ СКВОЗЬ ГОДЫ",
            "Тема природы ⚡ ОБРАЗ ЗИМЫ ⚡ Сергей Есенин",
            "«Открытая книга» ⚡ ПОЭЗИЯ И ВРЕМЯ ⚡ Сергей Есенин",
        ]
    )
    social = "\n".join(
        [
            "*VK:* https://vk.ru/thelegendarypoet",
            "*Телеграм:* https://t.me/thelegendarypoet",
            "*Рутуб:* https://rutube.ru/channel/74579453/",
            "*Сайт:* https://thelegendarypoet.ru/",
        ]
    )
    paragraphs = []
    for i in range(6):
        seed = f"Литературный абзац {i + 1}. Образы и композиция могут обсуждаться отдельно от фактов. "
        body = (seed * 8)[:525].rstrip()
        emph = [
            "",
            " *Чтение текста.*",
            " _Образ автора._",
            " *Стихотворный ритм.*",
            " _Форма стиха._",
            " *Заключительный образ.*",
        ][i]
        paragraphs.append((body + emph)[:570])
    desc = (
        f"Плейлист «Сергей Есенин»: {YESENIN}\nПлейлист «Поющие Поэты»: {SINGING}\n\n"
        + social
        + "\n\n"
        + "\n\n".join(paragraphs)
        + "\n\n#Есенин #Поэзия #РусскаяКлассика #Литература #История #Культура #СтихиЕсенина #Автор #Чтение"
    )
    shorts = (
        "Поэтические образы Сергея Есенина и речь русского стиха в формате.\n"
        + "Год и редакция стихотворения устанавливаются по первичным источникам, а не по названию ролика. " * 3
        + f"\nПлейлист «Сергей Есенин»: {YESENIN}\nПлейлист «Поющие Поэты»: {SINGING}\n"
        + "#СергейЕсенин #РусскаяПоэзия #Классика #Чтение"
    )
    pin = (
        "*«Поэтический цикл»* — Сергей Есенин, 1925\n\n"
        + "Этот закреп демонстрирует проверку структуры, а не готовый к публикации факт. " * 6
        + "\n_Строка оригинального стихотворения._\n_Другая точная строка._\n"
        + "Какой образ заметнее: природа или человеческая память?\n"
        + f"Плейлист «Сергей Есенин»: {YESENIN}\nПлейлист «Поющие Поэты»: {SINGING}"
    )
    tags = (
        "ТЕГИ: Есенин,Сергей Есенин,Русская Поэзия,Литература,Строка,Чтение,"
        "Культура,История,Природа,Рифма,Стихотворение,Классика,Лирика,Автор,Поэт,The Legendary Poet"
    )
    return "\n".join(f"```\n{block}\n```" for block in (titles, desc, shorts, pin, tags))


def test_valid_package_avoids_format_false_positive() -> None:
    pkg = make_package()
    errors = validate_five_block_package(pkg)
    assert not errors, [(error.block, error.code, error.message) for error in errors]


def test_detect_wrong_playlist_id_and_placeholder() -> None:
    pkg = make_package().replace("PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q", "PASTE-YESENIN-PLAYLIST-ID")
    issues = validate_five_block_package(pkg)
    assert "unknown_playlist" in {item.code for item in issues}
    assert "unresolved_marker" in {item.code for item in issues}


def test_detect_markdown_links_and_no_youtube_emphasis() -> None:
    pkg = (
        make_package()
        .replace("*VK:*", "**VK:**")
        .replace("https://vk.ru/thelegendarypoet", "[VK](https://vk.ru/thelegendarypoet)")
    )
    codes = {item.code for item in validate_five_block_package(pkg)}
    assert "markdown_link" in codes
    assert "social_order" in codes


def test_detect_bad_title_grammar_and_too_many_tags() -> None:
    pkg = make_package().replace("Есенин ⚡ СЕРДЦЕ", "Есенин⚡СЕРДЦЕ").replace("ТЕГИ: ", "ТЕГИ: неправильно, ")
    codes = {item.code for item in validate_five_block_package(pkg)}
    assert "lightning_spaces" in codes
    assert "tag_count_or_space" in codes


def test_new_format_is_not_inferred_from_legacy_description() -> None:
    assert [x.code for x in validate_five_block_package("Старое описание без пяти блоков.")] == ["five_blocks"]


def test_crlf_transport_is_supported() -> None:
    pkg = make_package().replace("\n", "\r\n")
    assert not validate_five_block_package(pkg)


def test_foreign_admin_link_fails_closed() -> None:
    pkg = make_package().replace(
        "https://thelegendarypoet.ru/", "https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet"
    )
    assert "foreign_or_admin_url" in {item.code for item in validate_five_block_package(pkg)}


def test_description_rejects_wrong_soclink_order_and_too_few_paragraphs() -> None:
    pkg = make_package().replace("*VK:* https://vk.ru/thelegendarypoet", "*VK:* https://vk.com/thelegendarypoet")
    pkg = pkg.replace("Литературный абзац 6.", "Литературный абзац 5.")
    assert "social_order" in {item.code for item in validate_five_block_package(pkg)}


def test_short_link_with_underscore_does_not_count_as_italic() -> None:
    pkg = make_package().replace("PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q", "PLy9lLJfoq3uYTrhcN1TDMUeks46Y-TT_M")
    assert "short_format" not in {item.code for item in validate_five_block_package(pkg)}


def test_missing_social_and_invalid_pin_are_rejected() -> None:
    pkg = make_package().replace("*Сайт:* https://thelegendarypoet.ru/", "*Сайт:* ")
    pkg = pkg.replace("*«Поэтический цикл»*", "«Поэтический цикл»")
    codes = {item.code for item in validate_five_block_package(pkg)}
    assert "social_order" in codes
    assert "pin_header" in codes


def test_no_facts_or_executors_in_copy_module() -> None:
    import inspect
    import video_channel_manager.youtube_package_v31 as module

    code = inspect.getsource(module)
    for forbidden in ("youtube_client", "update_video", "create_comment", "requests.post"):
        assert forbidden not in code
