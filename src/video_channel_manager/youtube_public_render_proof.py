"""Pure read-only verifier for YouTube's public description display.

The caller supplies the actually observed DOM text and styled fragments; raw
Studio markers or a successful Save are insufficient evidence of rendering.
No provider access, browser controls, account tokens or writes belong here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Sequence

_URL_RE = re.compile(r"https?://[^\s<>]+")
_BOLD_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_ITALIC_RE = re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)")


def _norm(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split()).strip()


def _expected_spans(text: str, regex: re.Pattern[str]) -> list[str]:
    # Opaque URL IDs can contain underscores; URLs are never italic markers.
    masked = _URL_RE.sub("", text)
    return [_norm(m.group(1)) for m in regex.finditer(masked)]


def _literary_paragraphs(text: str) -> list[str]:
    without_markers = _ITALIC_RE.sub(lambda m: m.group(1), text)
    without_markers = _BOLD_RE.sub(lambda m: m.group(1), without_markers)
    return [_norm(p) for p in re.split(r"\n\s*\n", without_markers) if len(_norm(p)) >= 160 and "https://" not in p]


@dataclass(frozen=True, slots=True)
class PublicRenderProof:
    ok: bool
    bold_expected: int
    bold_verified: int
    italic_expected: int
    italic_verified: int
    missing_paragraphs: tuple[str, ...]
    missing_bold: tuple[str, ...]
    missing_italic: tuple[str, ...]
    problems: tuple[str, ...]


def verify_public_description(
    *,
    studio_expected: str,
    studio_observed: str,
    public_description_text: str,
    public_bold_fragments: Sequence[str],
    public_italic_fragments: Sequence[str],
) -> PublicRenderProof:
    """Fail closed unless Studio and every meaningful public block/render match."""
    issues: list[str] = []
    if studio_expected.strip() != studio_observed.strip():
        issues.append("studio_text_drift")
    bold = _expected_spans(studio_expected, _BOLD_RE)
    italic = _expected_spans(studio_expected, _ITALIC_RE)
    visible_b = {_norm(s) for s in public_bold_fragments}
    visible_i = {_norm(s) for s in public_italic_fragments}
    missing_b = tuple(s for s in bold if s not in visible_b)
    missing_i = tuple(s for s in italic if s not in visible_i)
    if missing_b:
        issues.append("bold_not_publicly_rendered")
    if missing_i:
        issues.append("italic_not_publicly_rendered")
    paragraphs = _literary_paragraphs(studio_expected)
    if not paragraphs:
        issues.append("no_meaningful_paragraphs_to_verify")
    norm_public = _norm(public_description_text)
    missing_p = tuple(p[:130] for p in paragraphs if p not in norm_public)
    if missing_p:
        issues.append("public_description_stale_or_incomplete")
    if not norm_public:
        issues.append("public_description_missing")
    return PublicRenderProof(
        ok=not issues,
        bold_expected=len(bold),
        bold_verified=len(bold) - len(missing_b),
        italic_expected=len(italic),
        italic_verified=len(italic) - len(missing_i),
        missing_paragraphs=missing_p,
        missing_bold=missing_b,
        missing_italic=missing_i,
        problems=tuple(issues),
    )
