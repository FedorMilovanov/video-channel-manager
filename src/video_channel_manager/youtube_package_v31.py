"""Structural lint for owner-reviewed Legendary Poet five-block YouTube copy.

Only a local authoring aid. It never validates historical claims, approves copy,
or performs YouTube provider operations. Legacy descriptions are not in scope.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from video_channel_manager.editorial._project_profiles import LEGENDARY_POET_AUTHOR_PLAYLISTS, PROJECT_LINK_PROFILES

_PROJECT_LINKS = PROJECT_LINK_PROFILES["legendary-poet"]
_SINGING_POETS = "https://www.youtube.com/playlist?list=PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8"
_SOCIAL = (
    "*VK:* https://vk.ru/thelegendarypoet",
    "*Телеграм:* https://t.me/thelegendarypoet",
    "*Рутуб:* https://rutube.ru/channel/74579453/",
    "*Сайт:* https://thelegendarypoet.ru/",
)
_LINK_RE = re.compile(r"https?://[^\s<>]+")
_FENCE_RE = re.compile(r"(?ms)^```[ \t]*\r?\n(.*?)\r?\n```[ \t]*$")
_MARKER_RE = re.compile(r"(?:PASTE|INSERT|REPLACE|YOUR)(?:[-_][A-Z0-9]+){1,8}", re.I)
_EMPHASIS_RE = re.compile(r"(?<!\w)([*_])([^\n*_]+)\1(?!\w)")
# YouTube watch pages may display literal markers if punctuation touches the closing marker.
# This applies to new copy packages only; legacy published text is never rewritten.
_UNRENDERABLE_EMPHASIS_RE = re.compile(r"(?<!\w)([*_])([^\n*_]+)\1([,.:;!?])")
_HASHTAG_RE = re.compile(r"(?<!\w)#[A-Za-zА-Яа-яЁё0-9_]+")


@dataclass(frozen=True)
class CopyIssue:
    block: str
    code: str
    message: str


def _normal_lines(value: str) -> list[str]:
    return value.replace("\r\n", "\n").strip().split("\n")


def _check_links(text: str, block: str, errors: list[CopyIssue]) -> None:
    for raw in _LINK_RE.findall(text):
        link = raw.rstrip(".,;!?")
        if link not in _PROJECT_LINKS:
            code = "unknown_playlist" if "/playlist?list=" in link else "unknown_public_link"
            errors.append(CopyIssue(block, code, f"Нет в каноническом реестре: {link}"))
        if "cabinet.vkvideo.ru" in link or "gospod-bog.ru" in link or "t.me/lordchrist" in link:
            errors.append(CopyIssue(block, "foreign_or_admin_url", f"Чужой/служебный URL: {link}"))
    if _MARKER_RE.search(text) or "REPLACE_ME" in text:
        errors.append(CopyIssue(block, "unresolved_marker", "Остался технический маркер-заглушка."))
    if re.search(r"\[[^\]\n]+\]\(https?://", text):
        errors.append(CopyIssue(block, "markdown_link", "YouTube требует открытые URL, не [текст](URL)."))


def _check_two_playlists(lines: Sequence[str], block: str, errors: list[CopyIssue]) -> None:
    if len(lines) < 2:
        errors.append(CopyIssue(block, "missing_playlists", "Нужны два первых плейлиста."))
        return
    prefix = "Плейлист «"
    first = lines[0]
    if not first.startswith(prefix) or "»: https://www.youtube.com/playlist?list=" not in first:
        errors.append(CopyIssue(block, "author_playlist", "Первая строка — авторский плейлист с открытым URL."))
    second = f"Плейлист «Поющие Поэты»: {_SINGING_POETS}"
    if lines[1] != second:
        errors.append(CopyIssue(block, "singers_playlist", "Вторая строка — точный плейлист «Поющие Поэты»."))
    if "Поющие Поэты" in first or "Эксперименты AI" in first:
        errors.append(CopyIssue(block, "not_author_playlist", "Первая ссылка должна вести на авторский плейлист."))
    match = re.fullmatch(r"Плейлист «([^»]+)»: (https://www[.]youtube[.]com/playlist[?]list=[^\\s]+)", first)
    if match:
        poet, url = match.groups()
        expected = LEGENDARY_POET_AUTHOR_PLAYLISTS.get(poet)
        if expected is None:
            errors.append(CopyIssue(block, "unknown_author", f"Нет авторского плейлиста в реестре: {poet}"))
        elif expected != url:
            errors.append(CopyIssue(block, "author_playlist_mismatch", f"Плейлист {poet} не соответствует реестру."))


def _check_public_emphasis_punctuation(body: str, block: str, errors: list[CopyIssue]) -> None:
    """Fail the new-copy gate for punctuation that prevents YouTube watch-page styling.

    Do not auto-move punctuation: a syntactically external colon can be valid prose,
    but a copy-only package needs a manual typography resolution before release.
    URLs are masked so underscores in opaque playlist IDs are never parsed as italics.
    """
    without_urls = _LINK_RE.sub("", body)
    for match in _UNRENDERABLE_EMPHASIS_RE.finditer(without_urls):
        sample = match.group(0)
        errors.append(
            CopyIssue(
                block,
                "emphasis_public_render",
                f"YouTube может показать буквальные маркеры в {sample!r}: проверьте границу фразы и знак.",
            )
        )


def validate_five_block_package(source: str) -> list[CopyIssue]:
    """Validate mechanics of *new* owner manual package v3.1, not literary truth."""
    errors: list[CopyIssue] = []
    source = source.replace("\r\n", "\n")
    fences = list(_FENCE_RE.finditer(source))
    extra = _FENCE_RE.sub("", source).strip()
    if len(fences) != 5 or extra:
        return [CopyIssue("package", "five_blocks", "Требуются ровно пять голых ``` блоков без внешнего текста.")]
    titles, description, shorts, pin, tags = (f.group(1).strip() for f in fences)
    blocks = (("titles", titles), ("description", description), ("shorts", shorts), ("pin", pin), ("tags", tags))
    for name, body in blocks:
        _check_links(body, name, errors)
    title_lines = _normal_lines(titles)
    if len(title_lines) != 5 or len(set(title_lines)) != 5:
        errors.append(CopyIssue("titles", "title_count", "Нужно пять различных названий по одному на строке."))
    for title in title_lines:
        if len(title) > 70 or not title:
            errors.append(CopyIssue("titles", "title_length", "Каждое название должно содержать 1–70 символов."))
        bad_separator = any(token in title for token in ("|", "+", "&", "**", "__"))
        if bad_separator or re.search(r"\b(?:Suno|AI|нейросеть)\b", title, re.I):
            errors.append(CopyIssue("titles", "title_style", "Нарушен стиль названия v3.1."))
        if "⚡" in title and title.count("⚡") != title.count(" ⚡ "):
            errors.append(CopyIssue("titles", "lightning_spaces", "Разделитель ⚡ должен окружаться пробелами."))
        if title.count("⚡") > 2:
            errors.append(CopyIssue("titles", "lightning_count", "Максимум два ⚡ в названии."))

    if not 3500 <= len(description) <= 4600:
        errors.append(CopyIssue("description", "description_length", "Description: 3500–4600 символов."))
    desc_lines = _normal_lines(description)
    _check_two_playlists(desc_lines, "description", errors)
    if desc_lines[2:3] != [""] or desc_lines[3:7] != list(_SOCIAL) or desc_lines[7:8] != [""]:
        errors.append(CopyIssue("description", "social_order", "Четыре соцссылки — в порядке v3.1."))
    sections = [p.strip() for p in description.split("\n\n") if p.strip()]
    paragraphs = sections[2:-1] if len(sections) >= 4 else []
    if not 6 <= len(paragraphs) <= 8:
        errors.append(CopyIssue("description", "paragraph_count", "Нужно 6–8 литературных абзацев после ссылок."))
    if any(not 300 <= len(p) <= 700 for p in paragraphs):
        errors.append(CopyIssue("description", "paragraph_length", "Каждый литературный абзац: 300–700 символов."))
    if paragraphs and ("*" in paragraphs[0] or "_" in paragraphs[0]):
        errors.append(CopyIssue("description", "first_literary_paragraph", "Первый абзац — без маркеров."))
    last_block = sections[-1] if sections else ""
    hashes = _HASHTAG_RE.findall(last_block)
    if not 8 <= len(hashes) <= 10 or not all(w.startswith("#") for w in last_block.split()):
        errors.append(CopyIssue("description", "hashtag_count", "Последний блок — 8–10 тематических хештегов."))
    body_after_social = "\n\n".join(paragraphs)
    emph = _EMPHASIS_RE.findall(body_after_social)
    bold = sum(marker == "*" for marker, _ in emph)
    italic = sum(marker == "_" for marker, _ in emph)
    if not 3 <= bold <= 4 or not 2 <= italic <= 3 or "**" in description or "__" in description:
        errors.append(CopyIssue("description", "emphasis", "Нужно 3–4 *жирных* и 2–3 _курсива_."))
    _check_public_emphasis_punctuation(description, "description", errors)
    _check_public_emphasis_punctuation(pin, "pin", errors)

    if not 500 <= len(shorts) <= 600:
        errors.append(CopyIssue("shorts", "short_length", "SHORTS: 500–600 символов."))
    shorts_without_urls = _LINK_RE.sub("", shorts)
    if "*" in shorts_without_urls or "_" in shorts_without_urls or any(link in shorts for link in _SOCIAL):
        errors.append(CopyIssue("shorts", "short_format", "SHORTS — без выделений и социальных ссылок."))
    short_lines = _normal_lines(shorts)
    short_playlists = [line for line in short_lines if line.startswith("Плейлист «")]
    if short_playlists != desc_lines[:2]:
        errors.append(CopyIssue("shorts", "short_playlist_mismatch", "Плейлисты SHORTS должны совпадать с авторским и общим плейлистами Description."))
    short_hashes = _HASHTAG_RE.findall(short_lines[-1] if short_lines else "")
    if not 3 <= len(short_hashes) <= 5:
        errors.append(CopyIssue("shorts", "short_hashtags", "SHORTS: 3–5 хештегов в конце."))

    if not 500 <= len(pin) <= 900:
        errors.append(CopyIssue("pin", "pin_length", "ЗАКРЕП: 500–900 символов."))
    pin_lines = _normal_lines(pin)
    if not pin_lines or not pin_lines[0].startswith("*«") or "»* — " not in pin_lines[0]:
        errors.append(CopyIssue("pin", "pin_header", "Закреп начинается с *«Названия»* — Автор, год."))
    if _HASHTAG_RE.search(pin):
        errors.append(CopyIssue("pin", "pin_hashtags", "В закрепе нельзя использовать хештеги."))
    if len([line for line in pin_lines if line.startswith("_") and line.endswith("_")]) not in (1, 2):
        errors.append(CopyIssue("pin", "pin_poem_lines", "Нужно 1–2 отдельные _точные строки стихотворения_."))
    pin_playlists = [line for line in pin_lines if line.startswith("Плейлист «")]
    if pin_playlists != desc_lines[:2]:
        errors.append(CopyIssue("pin", "pin_playlist_mismatch", "Закреп должен ссылаться на те же проверенные авторский и общий плейлисты."))
    if pin_lines[-2:] != pin_playlists:
        errors.append(CopyIssue("pin", "pin_playlist_position", "Два плейлиста должны завершать закреп."))

    if "\n" in tags or not tags.startswith("ТЕГИ: ") or len(tags) > 480:
        errors.append(CopyIssue("tags", "tag_line", "ТЕГИ: — одна строка, максимум 480 символов."))
    entries = tags.removeprefix("ТЕГИ: ").split(",")
    if not 15 <= len(entries) <= 25 or any(not entry or entry != entry.strip() for entry in entries):
        errors.append(CopyIssue("tags", "tag_count_or_space", "15–25 тегов, запятые без пробелов."))
    return errors
