"""Fail-closed presentation gate for Lord God YouTube description releases.

Only invoked for exact Lord God owner-channel description copy plans.
Deliberately does NOT import The Legendary Poet's project links, playlist
ordering or fixed longform word counts. Uses the common YouTube rendering
validator for syntax while implementing this project's content constraints.
"""

from __future__ import annotations

import re
from typing import Any

from video_channel_manager.editorial.youtube_copy import (
    BOLD_SPAN_RE,
    ITALIC_SPAN_RE,
    validate_youtube_description,
)
from video_channel_manager.platforms.youtube.copy_plan import validate_copy_plan
from video_channel_manager.platforms.youtube.lord_god_source_preservation import (
    LORD_GOD_OWNER_CHANNEL,
    source_preservation_issues,
)


_RETIRED_CONTENT: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("obsolete_shelf_navigation", re.compile(r"(?:[?&]shelf_id=)", re.I)),
    (
        "retired_personal_contact",
        re.compile(r"t\.me/fedormilovanov|facebook\.com/fedor\.milovanov|vk\.com/curtmf", re.I),
    ),
    (
        "retired_translator_recruitment",
        re.compile(
            r"некоторые проповеди получается перевести|"
            r"всегда есть нужда в переводах|"
            r"помочь\s+с\s+переводами|"
            r"навыками переводчика",
            re.I,
        ),
    ),
    (
        "retired_fundraising_or_payment",
        re.compile(
            r"(?:new\.)?donatepay\.ru|"
            r"^\s*Сбербанк\s*:\s*[\d ]{8,}|"
            r"^\s*Яндекс\s+кошел[её]к\s*:\s*[\d ]+|"
            r"app5727453_-60805374|"
            r"если\s+кто\s+хочет\s+поддержать\s+служение\s+"
            r"распространения\s+и\s+переводов|"
            r"поддержать\s+служение\s+финансово",
            re.I | re.M,
        ),
    ),
    (
        "cross_project_identity",
        re.compile(r"thelegendarypoet\.ru|milovicake\.ru|t\.me/thelegendarypoet", re.I),
    ),
)


def presentation_issues(description: str) -> list[str]:
    """Return deterministic issue codes; never changes the source copy."""
    if not isinstance(description, str):
        return ["description_not_text"]
    issues = [
        f"youtube_{finding.code}"
        for finding in validate_youtube_description(description)
        if finding.severity == "error"
    ]
    if len(description) > 5000:
        issues.append("description_over_5000_characters")
    if len(description) >= 350:
        # The two raw nonempty Studio lines are consumed by repost/share
        # previews. A plain first *paragraph* alone is not sufficient:
        # a later bold heading on line two can leak literal markup.
        preview_lines = [line.strip() for line in description.splitlines() if line.strip()]
        if len(preview_lines) < 2 or any(
            len(line) < 15 or re.search(r"https?://|[*_`]", line, re.I) or line[0] in "#>-•‣◦⁃" or line.startswith("<")
            for line in preview_lines[:2]
        ):
            issues.append("share_preview_first_two_lines_not_plain")
        # Normal-length sermons and lectures must have selective *bold* and
        # _italic_. Shorts/very short clips may intentionally remain plain.
        if BOLD_SPAN_RE.search(description) is None:
            issues.append("missing_youtube_bold")
        if ITALIC_SPAN_RE.search(description) is None:
            issues.append("missing_youtube_italic")
    if re.search(r"\*\*[^*\n]+\*\*", description):
        issues.append("markdown_double_asterisks")
    for code, pattern in _RETIRED_CONTENT:
        if pattern.search(description):
            issues.append(code)
    return sorted(set(issues))


def require_lord_god_youtube_presentation(plan: dict[str, Any]) -> None:
    """Reject invalid Lord God plans BEFORE obtaining OAuth or making API calls."""
    if plan.get("target_channel_id") != LORD_GOD_OWNER_CHANNEL:
        return
    validate_copy_plan(plan)
    if (
        plan.get("project_key") != "lord-god-strength"
        or plan.get("link_profile") != "lord-god-strength"
        or len(plan["operations"]) != 1
    ):
        raise ValueError("Lord God presentation gate: wrong project identity or multi-video plan")
    operation = plan["operations"][0]
    if operation.get("channel_id") != LORD_GOD_OWNER_CHANNEL:
        raise ValueError("Lord God presentation gate: operation owner mismatch")
    problems = presentation_issues(str(operation.get("after_description", "")))
    problems.extend(source_preservation_issues(operation["before_description"], operation["after_description"]))
    if problems:
        raise ValueError(
            "Lord God YouTube description is NOT cleanly formatted or retains obsolete content: " + ", ".join(problems)
        )
