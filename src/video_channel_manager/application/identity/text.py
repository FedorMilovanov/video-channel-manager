from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from video_channel_manager.application.identity.digest import evidence_digest
from video_channel_manager.application.identity.models import CanonicalTextEvidence, TextPurpose


_RULESET_VERSION = "wave-8b-v1"
_HORIZONTAL_SPACE_RE = re.compile(r"[^\S\r\n]+")
_ALL_SPACE_RE = re.compile(r"\s+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_BRAND_RE = re.compile(
    r"(?<!\w)(?:@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts)(?!\w)",
    re.IGNORECASE,
)
_VERSION_RE = re.compile(r"(?<!\w)version(?!\w)", re.IGNORECASE)


def _apply(
    value: str,
    transformations: list[str],
    name: str,
    transform: Callable[[str], str],
) -> str:
    updated = transform(value)
    if updated != value:
        transformations.append(name)
    return updated


def _punctuation_to_spaces(value: str) -> str:
    return "".join(character if unicodedata.category(character)[0] in {"L", "N"} else " " for character in value)


def _variation_separators(value: str) -> str:
    pieces: list[str] = []
    separator_pending = False
    for character in value:
        if unicodedata.category(character)[0] in {"L", "N"}:
            if separator_pending and pieces:
                pieces.append("-")
            pieces.append(character)
            separator_pending = False
        else:
            separator_pending = True
    return "".join(pieces).strip("-")


def _normalize_description(value: str, transformations: list[str]) -> str:
    normalized = _apply(value, transformations, "unicode_nfkc", lambda item: unicodedata.normalize("NFKC", item))
    normalized = _apply(
        normalized,
        transformations,
        "line_endings_lf",
        lambda item: item.replace("\r\n", "\n").replace("\r", "\n"),
    )
    lines = normalized.split("\n")
    trimmed_lines = [line.rstrip() for line in lines]
    if trimmed_lines != lines:
        transformations.append("trim_line_trailing_whitespace")
    normalized = "\n".join(trimmed_lines)
    normalized = _apply(normalized, transformations, "trim_outer_whitespace", str.strip)
    normalized = _apply(
        normalized,
        transformations,
        "collapse_blank_lines",
        lambda item: _BLANK_LINES_RE.sub("\n\n", item),
    )
    return normalized


def canonicalize_text(value: str, purpose: TextPurpose) -> CanonicalTextEvidence:
    transformations: list[str] = []
    if purpose == TextPurpose.DESCRIPTION:
        canonical = _normalize_description(value, transformations)
    elif purpose == TextPurpose.DISPLAY_TITLE:
        canonical = _apply(value, transformations, "unicode_nfkc", lambda item: unicodedata.normalize("NFKC", item))
        canonical = _apply(canonical, transformations, "collapse_whitespace", lambda item: _ALL_SPACE_RE.sub(" ", item))
        canonical = _apply(canonical, transformations, "trim_outer_whitespace", str.strip)
    elif purpose == TextPurpose.VARIATION:
        canonical = _apply(value, transformations, "unicode_nfkc", lambda item: unicodedata.normalize("NFKC", item))
        canonical = _apply(canonical, transformations, "casefold", str.casefold)
        canonical = _apply(canonical, transformations, "fold_yo", lambda item: item.replace("ё", "е"))
        canonical = _apply(
            canonical,
            transformations,
            "normalize_version_label",
            lambda item: _VERSION_RE.sub("версия", item),
        )
        canonical = _apply(canonical, transformations, "separators_to_hyphens", _variation_separators)
    else:
        canonical = _apply(value, transformations, "unicode_nfkc", lambda item: unicodedata.normalize("NFKC", item))
        canonical = _apply(canonical, transformations, "casefold", str.casefold)
        canonical = _apply(canonical, transformations, "fold_yo", lambda item: item.replace("ё", "е"))
        if purpose == TextPurpose.IDENTITY_TITLE:
            canonical = _apply(
                canonical,
                transformations,
                "remove_known_brand_markers",
                lambda item: _BRAND_RE.sub(" ", item),
            )
            canonical = _apply(
                canonical,
                transformations,
                "normalize_version_label",
                lambda item: _VERSION_RE.sub("версия", item),
            )
        canonical = _apply(canonical, transformations, "punctuation_to_spaces", _punctuation_to_spaces)
        canonical = _apply(canonical, transformations, "collapse_whitespace", lambda item: _ALL_SPACE_RE.sub(" ", item))
        canonical = _apply(canonical, transformations, "trim_outer_whitespace", str.strip)

    payload = {
        "ruleset_version": _RULESET_VERSION,
        "purpose": purpose.value,
        "original": value,
        "canonical": canonical,
        "transformations": transformations,
    }
    return CanonicalTextEvidence(
        purpose=purpose,
        original=value,
        canonical=canonical,
        transformations=transformations,
        digest=evidence_digest(payload),
    )


def canonicalize_identity_title(value: str) -> CanonicalTextEvidence:
    return canonicalize_text(value, TextPurpose.IDENTITY_TITLE)


def canonicalize_display_title(value: str) -> CanonicalTextEvidence:
    return canonicalize_text(value, TextPurpose.DISPLAY_TITLE)


def canonicalize_description(value: str) -> CanonicalTextEvidence:
    return canonicalize_text(value, TextPurpose.DESCRIPTION)


def canonicalize_collection_title(value: str) -> CanonicalTextEvidence:
    return canonicalize_text(value, TextPurpose.COLLECTION_TITLE)


def canonicalize_variation(value: str) -> CanonicalTextEvidence:
    return canonicalize_text(value, TextPurpose.VARIATION)
