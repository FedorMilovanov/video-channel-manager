"""Approved preview-only RichMessage renderer for the existing LordChrist #1619.

This module performs no provider writes. Native inline callback buttons replace
visible footnote definitions, keeping the main body free of glossary tails.
Publishing is deliberately separate: do not edit #1619 until its bot's polling
handler is deployed and proven on a private test message.
"""

from __future__ import annotations

import html
from typing import Any

from video_channel_manager.lordchrist_peasants1525_inplace import PAGE_URL

POST_MESSAGE_ID = 1619
REQUIRED_BOT_ID = 8716602202
REQUIRED_CHAT_ID = -1001295216957
CALLBACK_PREFIX = "lc1525:"
TERM_KEYS = ("swabia", "articles", "dependency", "memmingen")
ARTICLE_CTA = "📖 Читать полную историческую статью →"


def _button(label: str, key: str) -> str:
    if key not in TERM_KEYS:
        raise ValueError(f"Unknown glossary term: {key}")
    return (
        f'<tg-button type="callback_data" style="link" data="{CALLBACK_PREFIX}{key}">{html.escape(label)}</tg-button>'
    )


def _replace_exact(text: str, match: str, replacement: str) -> str:
    if text.count(match) != 1:
        raise ValueError(f"Editorial term occurrence changed: {match}")
    return text.replace(match, replacement, 1)


def render(spec: Any) -> dict[str, Any]:
    """Return a compact-oriented, paragraphs-only RichMessage payload.

    RichMessage bubble width and link-preview display are controlled by the
    client; this renderer does not claim to force classic-message width or an
    Instant View thumbnail card.
    """
    if len(spec.lead_paragraphs) != 2 or len(spec.expandable_points) != 4:
        raise ValueError("Original historical post structure changed")

    lead1 = html.escape(spec.lead_paragraphs[0])
    lead2 = html.escape(spec.lead_paragraphs[1])
    lead1 = _replace_exact(
        lead1,
        "Крестьяне Швабии",
        "Крестьяне " + _button("Швабии", "swabia"),
    )
    lead1 = _replace_exact(
        lead1,
        "составили «Двенадцать статей»:",
        "составили " + _button("«Двенадцать статей»", "articles") + ":",
    )

    digest = []
    for i, point in enumerate(spec.expandable_points):
        content = html.escape(point.body)
        if i == 1:
            content = _replace_exact(
                content,
                "личной зависимости",
                _button("личной зависимости", "dependency"),
            )
        if i == 2:
            content = _replace_exact(
                content,
                "архив Меммингена",
                "архив " + _button("Меммингена", "memmingen"),
            )
        digest.append("• <b>" + html.escape(point.lead) + "</b> " + content)

    parts = [
        "<p><b>" + html.escape(spec.headline) + "</b></p>",
        "<p>" + lead1 + "</p>",
        "<p>" + lead2 + "</p>",
        "<blockquote>" + html.escape(spec.quote_text) + "</blockquote>",
        "<p>— <i>" + html.escape(spec.quote_attribution) + "</i></p>",
        (
            "<blockquote expandable><b>"
            + html.escape(spec.expandable_header)
            + "</b><br><br>"
            + "<br><br>".join(digest)
            + "</blockquote>"
        ),
        '<p><a href="' + html.escape(PAGE_URL, quote=True) + '">' + html.escape(ARTICLE_CTA) + "</a></p>",
    ]
    markup = "".join(parts)
    if markup.count("<tg-button ") != 4:
        raise ValueError("Only four historical term buttons are permitted")
    if "<tg-reference" in markup or "pastor" in markup or "luther" in markup:
        raise ValueError("Visible glossary tail or trivial term callback found")
    for key in TERM_KEYS:
        if markup.count('data="' + CALLBACK_PREFIX + key + '"') != 1:
            raise ValueError(f"Missing/duplicate button: {key}")
    if markup.count("<p>") != 5 or markup.count("<blockquote") != 2:
        raise ValueError("Unapproved paragraph geometry")
    if not markup.endswith("</a></p>") or markup.count(PAGE_URL) != 1:
        raise ValueError("Full article must be linked exactly once at bottom")
    if len(markup.encode("utf-8")) > 32768:
        raise ValueError("RichMessage too large")
    return {"html": markup, "skip_entity_detection": True}
