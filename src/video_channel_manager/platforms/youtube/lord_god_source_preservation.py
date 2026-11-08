"""Fail-closed source-preservation guard for Lord God YouTube descriptions.

A new editorial description must not silently erase the old video's actual
chapters, translation/source credits or non-retired external references.

A verified playlist must be retained even when its URL is canonicalized.
Unverified, unrelated, or incorrectly attributed links require manual review;
this guard does not itself authorize any source or rights claim.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

LORD_GOD_OWNER_CHANNEL = "UCeSJsC6go2c9pdJCuUI1BYA"
# Exactly one registered community may be canonicalized. This does not
# authorize deletion of VK media URLs, posts, query links or other communities.
_OLD_OWNER_VK_COMMUNITY_URLS = {
    "https://vk.com/the_lord_god_is_my_strength",
    "http://vk.com/the_lord_god_is_my_strength",
}
_CANONICAL_OWNER_VK_COMMUNITY = "https://vk.ru/the_lord_god_is_my_strength"

_URL_RE = re.compile(r"https?://[^\s<>]+", re.I)
_CHAPTER_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s+\S", re.M)
_CREDIT_RE = re.compile(
    r"(?:"
    r"перевод(?:чик(?:и|ом)?)?\s*[:—-]|"
    r"перевод\s+(?:выполнил[аи]?|выполнен|осуществил[аи]?|с\s+испанского\s+взят)|"
    r"источник\s+(?:записи|видео|проповеди)|"
    r"за\s+сохранность\s+перевода|"
    r"правообладател[ьи]|авторск(?:ие|их)\s+прав|"
    r"copyright|©|permission\s+(?:to|from)|"
    r"license\s*[:—-]"
    r")",
    re.I,
)


def _links(text: str) -> set[str]:
    return {m.group(0).rstrip(".,);!?") for m in _URL_RE.finditer(text)}


def _owner_playlist_id(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        return None
    if parsed.path.rstrip("/") != "/playlist":
        return None
    values = parse_qs(parsed.query).get("list", [])
    return values[0] if len(values) == 1 and values[0] else None


def _obsolete_owner_navigation_or_contact(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    if host in {"youtube.com", "m.youtube.com"}:
        owner_path = f"/channel/{LORD_GOD_OWNER_CHANNEL}"
        owner_navigation_paths = {
            owner_path,
            f"{owner_path}/playlists",
            f"{owner_path}/videos",
        }
        if path in owner_navigation_paths and "shelf_id" in parse_qs(parsed.query):
            return True
    if host == "t.me" and path == "/fedormilovanov":
        return True
    if host == "facebook.com" and path == "/fedor.milovanov":
        return True
    if host == "vk.com" and path == "/curtmf":
        return True
    if host in {"donatepay.ru", "new.donatepay.ru"}:
        return True
    return False


def source_preservation_issues(before: str, after: str) -> list[str]:
    """Identify lost source evidence before a *single-video* Lord God write.

    Strict by design: a link that is not proven obsolete must remain in the
    candidate, or the video stays on HOLD for owner/source review. Nothing is
    added automatically.
    """
    if not isinstance(before, str) or not isinstance(after, str):
        return ["source_preservation_not_text"]

    issues: list[str] = []
    before_lines = [line.strip() for line in before.splitlines() if line.strip()]
    after_lines = {line.strip() for line in after.splitlines() if line.strip()}

    if any(_CHAPTER_RE.match(line) and line not in after_lines for line in before_lines):
        issues.append("original_chapters_not_preserved")

    if any(_CREDIT_RE.search(line) and line not in after_lines for line in before_lines):
        issues.append("original_translation_or_source_credit_not_preserved")

    after_urls = _links(after)
    after_playlist_ids = {_owner_playlist_id(url) for url in after_urls}
    for url in sorted(_links(before)):
        if url in _OLD_OWNER_VK_COMMUNITY_URLS and _CANONICAL_OWNER_VK_COMMUNITY in after_urls:
            continue
        if _obsolete_owner_navigation_or_contact(url):
            continue
        playlist_id = _owner_playlist_id(url)
        if playlist_id is not None:
            if playlist_id not in after_playlist_ids:
                issues.append("original_playlist_link_not_preserved")
        elif url not in after_urls:
            issues.append("original_source_or_related_link_not_preserved")

    return sorted(set(issues))
