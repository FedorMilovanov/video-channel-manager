from __future__ import annotations

import re
from typing import Any

from video_channel_manager.platforms.vk.editorial_cleanup import FOOTER_PATTERNS

_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё-]+", re.UNICODE)
_FACT_RE = re.compile(
    r"\b(?:1[0-9]{3}|20[0-9]{2})\b|впервые|написал|написано|создан|родил|умер|гибел|"
    r"биограф|публикац|журнал|сборник|музей|архив|исследовател|историческ|псих|"
    r"самоубий|религи|вер[ауы]\b",
    re.IGNORECASE,
)
_SENSITIVE_RE = re.compile(
    r"самоубий|суицид|смерт|псих|грех|невери|Иисус|Христ|Бог\b|религи",
    re.IGNORECASE,
)
_TRIGGER_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dates", re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")),
    ("authorship_or_creation", re.compile(r"впервые|написал|написано|создан", re.IGNORECASE)),
    ("biography_or_death", re.compile(r"родил|умер|гибел|биограф|смерт", re.IGNORECASE)),
    (
        "publication_or_history",
        re.compile(r"публикац|журнал|сборник|музей|архив|исследовател|историческ", re.IGNORECASE),
    ),
    ("psychology_or_self_harm", re.compile(r"псих|самоубий|суицид", re.IGNORECASE)),
    (
        "religion_or_theology",
        re.compile(r"грех|невери|Иисус|Христ|Бог\b|религи|вер[ауы]\b", re.IGNORECASE),
    ),
)


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def reviewable_description_text(value: str) -> str:
    """Return only surfaces that may contain editorial claims.

    URLs, hashtags, known footer lines, decorative rules, and blank technical
    lines are excluded. This prevents tags such as ``#БессмертныйПолк`` from
    being treated as a claim about death or self-harm.
    """

    output: list[str] = []
    normalized = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.splitlines():
        stripped = line.strip()
        if not stripped:
            output.append("")
            continue
        if any(pattern.match(line) for pattern in FOOTER_PATTERNS):
            continue
        if re.fullmatch(r"[━─═—-]{10,}", stripped):
            continue
        cleaned = _URL_RE.sub("", line)
        cleaned = _HASHTAG_RE.sub("", cleaned)
        cleaned = _compact(cleaned)
        if cleaned:
            output.append(cleaned)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip()


def _paragraphs(value: str) -> list[str]:
    return [paragraph for raw in re.split(r"\n\s*\n+", value) if (paragraph := _compact(raw))]


def _expanded_term(value: str, match: re.Match[str]) -> str:
    start, end = match.span()
    while start > 0 and (value[start - 1].isalnum() or value[start - 1] in "_-"):
        start -= 1
    while end < len(value) and (value[end].isalnum() or value[end] in "_-"):
        end += 1
    return value[start:end]


def _unique_matches(pattern: re.Pattern[str], value: str) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(value):
        term = _expanded_term(value, match)
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            matches.append(term)
    return matches


def _localized_evidence(pattern: re.Pattern[str], value: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for paragraph in _paragraphs(value):
        terms = _unique_matches(pattern, paragraph)
        if not terms:
            continue
        excerpt = paragraph if len(paragraph) <= 700 else f"{paragraph[:699].rstrip()}…"
        evidence.append({"matched_terms": terms, "excerpt": excerpt})
    return evidence


def _trigger_families(value: str) -> list[str]:
    return [name for name, pattern in _TRIGGER_FAMILIES if pattern.search(value)]


def build_vk_deferred_editorial_findings(
    remote_id: str,
    description: str,
    *,
    include_technical_surfaces: bool = False,
) -> list[dict[str, Any]]:
    """Return deterministic review markers with exact local evidence.

    A marker means only that a passage should be checked. It is not a claim that
    the passage is wrong and it never authorizes an automatic correction.
    """

    review_text = str(description or "") if include_technical_surfaces else reviewable_description_text(description)
    findings: list[dict[str, Any]] = []
    factual_evidence = _localized_evidence(_FACT_RE, review_text)
    if factual_evidence:
        findings.append(
            {
                "kind": "factual_editorial_review",
                "target_video_id": remote_id,
                "message": "Technical cleanup preserves the factual body; claims require sourced review.",
                "trigger_families": _trigger_families(review_text),
                "matched_terms": _unique_matches(_FACT_RE, review_text),
                "evidence": factual_evidence,
            }
        )

    sensitive_evidence = _localized_evidence(_SENSITIVE_RE, review_text)
    if sensitive_evidence:
        findings.append(
            {
                "kind": "sensitive_claim_review",
                "target_video_id": remote_id,
                "message": "Sensitive religious, medical, death, or self-harm claims require manual review.",
                "trigger_families": _trigger_families(review_text),
                "matched_terms": _unique_matches(_SENSITIVE_RE, review_text),
                "evidence": sensitive_evidence,
            }
        )
    return findings


__all__ = [
    "build_vk_deferred_editorial_findings",
    "reviewable_description_text",
]
