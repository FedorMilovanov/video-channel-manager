"""Read-only structural integrity checks for source-locked poetry quote Shorts.

A PASS means the supplied text is internally consistent, NOT that the witness
is an authentic edition, the cited research is independent, the audio was
heard, or the YouTube comments were published. No provider imports or writes.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from video_channel_manager.editorial._project_profiles import (
    LEGENDARY_POET_AUTHOR_PLAYLISTS,
    PROJECT_LINK_PROFILES,
)

_ACUTE = "\u0301"
_VOWELS = frozenset("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
_LINKS = PROJECT_LINK_PROFILES["legendary-poet"]
_EDITION_STATES = frozenset(("complete", "draft", "fragment"))
_PROOF_TYPES = frozenset(("critical_edition", "manuscript", "first_edition", "archive"))


@dataclass(frozen=True)
class QuoteIssue:
    code: str
    detail: str


def _without_stress(value: str) -> str:
    """Remove ONLY optional combining acute accents, not letters or punctuation."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFD", value).replace(_ACUTE, ""))


def _lines(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value or not all(isinstance(line, str) and line.strip() for line in value):
        return None
    return [unicodedata.normalize("NFC", line.strip()) for line in value]


def _web_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def _compact(value: str) -> str:
    return " ".join(value.split())


def validate_poetry_quote_packet(
    packet: Mapping[str, object],
    *,
    require_audio_review: bool = False,
) -> list[QuoteIssue]:
    """Check one selected edition, exact contiguous excerpt, TTS accents and two-comment copy.

    The review stage may use audio_review.status='unverified'. A final release
    preflight must pass require_audio_review=True and independently inspect the
    actual recording; a metadata declaration never proves audio quality.
    """
    errors: list[QuoteIssue] = []

    def fail(code: str, detail: str) -> None:
        errors.append(QuoteIssue(code, detail))

    if packet.get("schema_version") != 1:
        fail("schema_version", "Required schema_version=1.")
    if packet.get("project_key") != "legendary-poet":
        fail("project_identity", "Only project_key=legendary-poet is supported.")

    poet = packet.get("poet")
    work = packet.get("work")
    if not isinstance(poet, str) or not poet.strip() or not isinstance(work, str) or not work.strip():
        fail("work_identity", "Explicit poet and work are required.")
        poet = ""

    edition = packet.get("edition")
    if not isinstance(edition, Mapping):
        edition = {}
        fail("edition", "Edition record is required.")
    for field in ("citation", "version", "author", "work"):
        if not isinstance(edition.get(field), str) or not edition[field].strip():
            fail("edition_identity", f"Missing edition.{field}.")
    if edition.get("author") != poet or edition.get("work") != work:
        fail("edition_mismatch", "Exact author/work must match the selected edition.")
    edition_url = edition.get("url")
    if not _web_url(edition_url):
        fail("edition_url", "An HTTPS edition URL is required.")
    edition_state = edition.get("state")
    if edition_state not in _EDITION_STATES:
        fail("edition_state", "Edition state must be complete, draft or fragment.")

    sources = packet.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        fail("sources", "At least two individually identified source records are required.")
        sources = []
    valid_urls: list[str] = []
    classes: list[str] = []
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            fail("source_record", f"Source #{index + 1} is not an object.")
            continue
        url, cls, citation = source.get("url"), source.get("class"), source.get("citation")
        if not _web_url(url) or not isinstance(citation, str) or not citation.strip():
            fail("source_record", f"Source #{index + 1} requires an HTTPS URL and citation.")
        else:
            valid_urls.append(url)
        if not isinstance(cls, str) or not cls.strip():
            fail("source_class", f"Source #{index + 1} requires an evidence class.")
        else:
            classes.append(cls)
    if len(set(valid_urls)) < 2:
        fail("source_independence", "Two distinct source URLs are required; editorial independence must also be reviewed.")
    if edition_url not in valid_urls or not _PROOF_TYPES.intersection(classes):
        fail("source_witness", "Selected edition URL and an archival/critical source class must be registered.")

    text = _lines(packet.get("edition_lines"))
    excerpt = _lines(packet.get("excerpt_lines"))
    tts = _lines(packet.get("tts_lines"))
    full_comment_lines = _lines(packet.get("full_comment_lines"))
    if text is None or excerpt is None:
        fail("poem_lines", "edition_lines and excerpt_lines must be non-empty arrays of non-blank lines.")
    start = packet.get("excerpt_start_line")
    if type(start) is not int or start < 1:
        fail("excerpt_start", "1-based excerpt_start_line is required.")
    elif text is not None and excerpt is not None:
        if text[start - 1 : start - 1 + len(excerpt)] != excerpt:
            fail("excerpt_not_contiguous", "Quoted lines must exactly match one continuous passage of the chosen edition.")
    if text is None or full_comment_lines is None or full_comment_lines != text:
        fail("full_text_mismatch", "The full poem for the pinned comment must exactly equal edition_lines.")
    if tts is None or excerpt is None or len(tts) != len(excerpt):
        fail("tts_line_count", "tts_lines must match the quoted line count.")
    elif [_without_stress(line) for line in tts] != excerpt:
        fail("tts_text_drift", "TTS may add stress marks, but may not change a single letter or punctuation mark.")

    notes = packet.get("pronunciation_notes", [])
    if not isinstance(notes, list):
        fail("pronunciation_notes", "pronunciation_notes must be an array.")
        notes = []
    note_stressed: set[str] = set()
    for index, note in enumerate(notes):
        if not isinstance(note, Mapping):
            fail("pronunciation_note", f"Pronunciation note #{index + 1} is not an object.")
            continue
        token, marked, sense = note.get("token"), note.get("stressed"), note.get("sense")
        if not all(isinstance(v, str) and v.strip() for v in (token, marked, sense)):
            fail("pronunciation_note", f"Note #{index + 1} needs token, stressed and sense.")
            continue
        decomposed = unicodedata.normalize("NFD", marked)
        positions = [i for i, char in enumerate(decomposed) if char == _ACUTE]
        if (
            len(positions) != 1
            or positions[0] == 0
            or decomposed[positions[0] - 1] not in _VOWELS
            or _without_stress(marked) != token
        ):
            fail("stress_mark", f"Invalid stress note for {token!r}.")
        note_stressed.add(unicodedata.normalize("NFC", marked))
        if tts is not None and not any(marked in line for line in tts):
            fail("stress_not_in_tts", f"Marked pronunciation {marked!r} not found in TTS.")

    if tts is not None:
        for line in tts:
            # Every actually marked word must be accounted for by an editorial note.
            for word in re.findall(r"[\w\u0301]+", line):
                if _ACUTE in unicodedata.normalize("NFD", word) and word not in note_stressed:
                    fail("unreviewed_stress", f"No pronunciation note for the stressed token {word!r}.")

    author_playlist = packet.get("author_playlist")
    if author_playlist is not None:
        if not isinstance(author_playlist, str) or author_playlist not in _LINKS:
            fail("unknown_playlist", "Author playlist is not in the registered public link profile.")
        elif LEGENDARY_POET_AUTHOR_PLAYLISTS.get(poet) != author_playlist:
            fail("author_playlist_mismatch", "Playlist belongs to another author or the poet has no registered playlist.")
    for url in packet.get("other_playlists", []) if isinstance(packet.get("other_playlists", []), list) else []:
        if not isinstance(url, str) or url not in _LINKS or "/playlist?list=" not in url:
            fail("unknown_playlist", "Unregistered playlist in other_playlists.")
    if not isinstance(packet.get("other_playlists", []), list):
        fail("playlist_schema", "other_playlists must be an array.")

    mode = packet.get("format_mode")
    if mode not in ("standard", "short_two_comments"):
        fail("format_mode", "Use standard or short_two_comments.")
    if mode == "short_two_comments":
        desc, pin, history = (
            packet.get("short_description"),
            packet.get("pinned_comment"),
            packet.get("history_comment"),
        )
        if not isinstance(desc, str) or not 60 <= len(desc.strip()) <= 900:
            fail("short_description", "Short description must be substantive and compact (60–900 chars).")
        if not isinstance(pin, str) or not pin.strip():
            fail("pin_required", "Pinned comment with the full selected text is required.")
        elif text is not None and _compact("\n".join(text)) not in _compact(pin):
            fail("pin_text_missing", "Pinned comment does not contain the entire exact edition text.")
        elif edition_state != "complete" and "сохранивш" not in pin.casefold():
            fail("draft_disclosure", "Draft/fragment pin must say it is the surviving text, not a finalized poem.")
        if not isinstance(history, str) or len(history.strip()) < 200 or history == pin:
            fail("history_comment", "Distinct, substantial historical commentary is required.")
        if isinstance(history, str) and text is not None and _compact("\n".join(text)) in _compact(history):
            fail("duplicated_poem", "Do not repeat the full poem in the history comment.")

    review = packet.get("audio_review", {})
    if not isinstance(review, Mapping):
        review = {}
        fail("audio_review", "audio_review must be a record.")
    status = review.get("status", "unverified")
    if status not in ("unverified", "reviewed"):
        fail("audio_review_status", "audio_review.status is unverified or reviewed.")
    if status == "reviewed":
        sha = review.get("sha256")
        reviewer = review.get("reviewer")
        if not isinstance(sha, str) or re.fullmatch(r"[0-9a-fA-F]{64}", sha) is None:
            fail("audio_receipt", "Reviewed audio must reference the exact SHA-256 of listened media.")
        if not isinstance(reviewer, str) or not reviewer.strip():
            fail("audio_reviewer", "Identify who actually reviewed the audio.")
    if require_audio_review and status != "reviewed":
        fail("audio_unverified", "Final release preflight requires a human-reviewed audio receipt.")
    return errors
