from __future__ import annotations

import re

from video_channel_manager.editorial import youtube_copy as legacy

CopyFinding = legacy.CopyFinding
CopyFix = legacy.CopyFix


def _review_punctuation_finding(match: re.Match[str]) -> CopyFinding:
    """Classify punctuation scope conservatively.

    Punctuation immediately after emphasis is often intentionally outside the
    emphasized title, date, name, or term. Moving it inside is a typography
    decision, not a deterministic correction. Only metadata-label colons and a
    duplicate full stop after ?/!/… are safe to change automatically.
    """

    span = match.group("span")
    punctuation = match.group("punct")
    inner = legacy._emphasis_inner(span)
    excerpt = legacy._excerpt(match.group(0))

    if punctuation == ":" and legacy._is_metadata_label(inner):
        return CopyFinding(
            "metadata_label_colon",
            "error",
            "Двоеточие является частью подписи ссылки и должно находиться внутри выделения.",
            excerpt=excerpt,
        )

    if punctuation == "." and inner.endswith(legacy._TERMINAL_PUNCTUATION):
        return CopyFinding(
            "duplicate_terminal_punctuation",
            "error",
            "После выделенной фразы уже есть ?/!/…; внешнюю точку нужно удалить.",
            excerpt=excerpt,
        )

    return CopyFinding(
        "punctuation_scope_review",
        "warning",
        (
            "Знак после закрывающего маркера может относиться ко всему предложению, а не к выделенной фразе. "
            "Автоматически переносить его внутрь нельзя."
        ),
        excerpt=excerpt,
    )


def validate_youtube_description(description: str) -> list[CopyFinding]:
    """Run the legacy checks, replacing unsafe punctuation assumptions."""

    findings = [
        finding
        for finding in legacy.validate_youtube_description(description)
        if finding.code
        not in {
            "punctuation_outside_emphasis",
            "colon_after_emphasis_review",
            "punctuation_after_terminal_review",
            "duplicate_terminal_punctuation",
        }
    ]
    text_without_non_markers = legacy._without_non_markers(description)
    findings.extend(
        _review_punctuation_finding(match) for match in legacy.PUNCT_OUTSIDE_RE.finditer(text_without_non_markers)
    )
    return findings


def autofix_youtube_description(description: str) -> tuple[str, list[CopyFix]]:
    """Apply only wording-preserving fixes with unambiguous punctuation scope."""

    updated = description
    fixes: list[CopyFix] = []

    first_match = legacy.FIRST_PARAGRAPH_RE.match(updated)
    if first_match is not None:
        first = first_match.group("first")
        separator = first_match.group("separator")
        clean_first = legacy._strip_emphasis_markers(first)
        if clean_first != first:
            fixes.append(CopyFix("share_preview_emphasis", first, clean_first))
            updated = f"{clean_first}{separator}{updated[first_match.end() :]}"

    def trim_bold(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner == inner.strip():
            return match.group(0)
        after = f"*{inner.strip()}*"
        fixes.append(CopyFix("bold_edge_space", match.group(0), after))
        return after

    def trim_italic(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner == inner.strip():
            return match.group(0)
        after = f"_{inner.strip()}_"
        fixes.append(CopyFix("italic_edge_space", match.group(0), after))
        return after

    masked, replacements = legacy._mask_non_markers(updated)
    masked = legacy.BOLD_SPAN_RE.sub(trim_bold, masked)
    masked = legacy.ITALIC_SPAN_RE.sub(trim_italic, masked)
    updated = legacy._restore_masks(masked, replacements)

    def fix_safe_punctuation(match: re.Match[str]) -> str:
        span = match.group("span")
        punctuation = match.group("punct")
        inner = legacy._emphasis_inner(span)
        before = match.group(0)

        if punctuation == ":" and legacy._is_metadata_label(inner):
            after = legacy._with_punctuation_inside(span, punctuation)
            code = "metadata_label_colon"
        elif punctuation == "." and inner.endswith(legacy._TERMINAL_PUNCTUATION):
            after = span
            code = "duplicate_terminal_punctuation"
        else:
            return before

        if after != before:
            fixes.append(CopyFix(code, before, after))
        return after

    updated = legacy.PUNCT_OUTSIDE_RE.sub(fix_safe_punctuation, updated)

    def normalize_blank_lines(match: re.Match[str]) -> str:
        before = match.group(0)
        after = "\n\n"
        fixes.append(CopyFix("multiple_blank_lines", before, after))
        return after

    updated = legacy.MULTI_BLANK_RE.sub(normalize_blank_lines, updated)
    return updated, fixes


__all__ = [
    "CopyFinding",
    "CopyFix",
    "autofix_youtube_description",
    "validate_youtube_description",
]
