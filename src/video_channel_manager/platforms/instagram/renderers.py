from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from video_channel_manager.editorial.content import (
    DECORATIVE_MARKERS,
    EditorialContentRecord,
    contains_banned_circle,
)
from video_channel_manager.editorial.rendering import (
    ContentSurface,
    PlatformName,
    RenderIssue,
    RenderedContent,
    count_urls,
    layout_issues,
)

_HASHTAG_RE = re.compile(r"^#[^\s#]+$", re.UNICODE)
_EMPHASIS_RE = re.compile(r"(?P<marker>[*_])(?P<body>[^*_]+)(?P=marker)")
_INTERNAL_MOBILE_READABILITY_WARNING = 1800

_CLICKBAIT_PHRASES = (
    "вы не поверите",
    "шокирующая правда",
    "это изменит вашу жизнь",
    "скрытая тайна",
    "которую от вас прятали",
    "все богословы ошибаются",
)
_FAITH_ENGAGEMENT_PHRASES = (
    "напиши аминь",
    "напишите аминь",
    "поставь лайк, если веришь",
    "поставьте лайк, если верите",
    "лайк если веришь",
    "лайк, если веришь",
    "репост если веришь",
    "репост, если веришь",
)


def _plain(value: str) -> str:
    result = value.strip()
    for marker in DECORATIVE_MARKERS:
        if result.startswith(marker):
            result = result[len(marker) :].lstrip()
            break
    previous = None
    while previous != result:
        previous = result
        result = _EMPHASIS_RE.sub(lambda match: match.group("body"), result)
    return result.strip()


def _metadata(record: EditorialContentRecord) -> Mapping[str, object]:
    raw = record.rendering_metadata.get("instagram")
    return raw if isinstance(raw, Mapping) else {}


def _optional_text(metadata: Mapping[str, object], key: str, issues: list[RenderIssue]) -> str:
    raw = metadata.get(key)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        issues.append(
            RenderIssue(
                code=f"instagram_{key}_type",
                severity="error",
                message=f"rendering_metadata.instagram.{key} must be a string.",
            )
        )
        return ""
    return raw.strip()


def _hashtags(metadata: Mapping[str, object], issues: list[RenderIssue]) -> tuple[str, ...]:
    raw = metadata.get("hashtags")
    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        issues.append(
            RenderIssue(
                code="instagram_hashtags_type",
                severity="error",
                message="rendering_metadata.instagram.hashtags must be a list of hashtag strings.",
            )
        )
        return ()
    values: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            issues.append(
                RenderIssue(
                    code="instagram_hashtags_type",
                    severity="error",
                    message="rendering_metadata.instagram.hashtags must contain only strings.",
                )
            )
            continue
        value = item.strip()
        if value:
            values.append(value)
    return tuple(values)


def render_instagram_caption(
    *,
    project_key: str,
    topic_line: str,
    body: str,
    question: str = "",
    provenance_line: str = "",
    cta: str = "",
    hashtags: Sequence[str] = (),
    ai_audio_disclosure_required: bool = False,
) -> tuple[str, tuple[RenderIssue, ...]]:
    """Render one provider-inert caption and deterministic Instagram diagnostics."""

    issues: list[RenderIssue] = []
    normalized_topic = _plain(topic_line)
    normalized_body = _plain(body)
    normalized_question = _plain(question)
    normalized_provenance = _plain(provenance_line)
    normalized_cta = _plain(cta)
    normalized_hashtags = tuple(item.strip() for item in hashtags if item.strip())

    if not normalized_topic:
        issues.append(
            RenderIssue(
                code="instagram_topic_missing",
                severity="error",
                message="Instagram caption requires a concrete first-line topic.",
            )
        )
    if not normalized_body:
        issues.append(
            RenderIssue(
                code="instagram_body_missing",
                severity="error",
                message="Instagram caption requires a source-led body.",
            )
        )

    if len(normalized_hashtags) > 6:
        issues.append(
            RenderIssue(
                code="instagram_hashtag_count",
                severity="error",
                message="Instagram house readability rule allows at most 6 hashtags.",
            )
        )
    elif len(normalized_hashtags) < 3:
        issues.append(
            RenderIssue(
                code="instagram_hashtag_count",
                severity="warning",
                message="Instagram house readability default is 3-6 tightly relevant hashtags.",
            )
        )

    folded_hashtags = tuple(item.casefold() for item in normalized_hashtags)
    if len(folded_hashtags) != len(set(folded_hashtags)):
        issues.append(
            RenderIssue(
                code="instagram_duplicate_hashtag",
                severity="error",
                message="Instagram hashtags must be unique ignoring case.",
            )
        )
    invalid_hashtags = tuple(item for item in normalized_hashtags if _HASHTAG_RE.fullmatch(item) is None)
    if invalid_hashtags:
        issues.append(
            RenderIssue(
                code="instagram_invalid_hashtag",
                severity="error",
                message=f"Invalid Instagram hashtag syntax: {', '.join(invalid_hashtags)}.",
            )
        )

    if ai_audio_disclosure_required and not normalized_provenance:
        issues.append(
            RenderIssue(
                code="instagram_ai_audio_disclosure_missing",
                severity="error",
                message="Realistic synthetic/generative audio requires a reviewed provenance disclosure line.",
            )
        )

    blocks = [
        normalized_topic,
        normalized_body,
        normalized_question,
        normalized_provenance,
        normalized_cta,
        " ".join(normalized_hashtags),
    ]
    text = "\n\n".join(block for block in blocks if block).strip()
    lowered = text.casefold()

    for phrase in _CLICKBAIT_PHRASES:
        if phrase in lowered:
            issues.append(
                RenderIssue(
                    code="instagram_clickbait_phrase",
                    severity="error",
                    message=f"Instagram source-led policy forbids clickbait phrase: {phrase}.",
                )
            )
    if project_key == "lord-god-strength":
        for phrase in _FAITH_ENGAGEMENT_PHRASES:
            if phrase in lowered:
                issues.append(
                    RenderIssue(
                        code="instagram_faith_engagement_bait",
                        severity="error",
                        message=f"Lord God content must not use engagement as a faith test: {phrase}.",
                    )
                )

    if contains_banned_circle(text):
        issues.append(
            RenderIssue(
                code="forbidden_circle_marker",
                severity="error",
                message="Colored circle markers are forbidden.",
            )
        )
    if count_urls(text):
        issues.append(
            RenderIssue(
                code="instagram_raw_url_in_caption",
                severity="error",
                message="Instagram captions use reviewed link intent/CTA; raw URLs are not inserted into caption copy.",
            )
        )
    if len(text) > _INTERNAL_MOBILE_READABILITY_WARNING:
        issues.append(
            RenderIssue(
                code="instagram_caption_long",
                severity="warning",
                message=(
                    f"Caption has {len(text)} characters; internal mobile-readability review starts above "
                    f"{_INTERNAL_MOBILE_READABILITY_WARNING}. This is not a claimed provider limit."
                ),
            )
        )
    issues.extend(layout_issues(text, max_line_length=160))
    return text, tuple(issues)


class _InstagramRenderer:
    platform: PlatformName = "instagram"
    surface: ContentSurface

    def render(self, record: EditorialContentRecord) -> RenderedContent:
        issues: list[RenderIssue] = []
        if not record.supports("instagram", self.surface):
            issues.append(
                RenderIssue(
                    code="platform_surface_not_suitable",
                    severity="error",
                    message=f"Content record does not allow instagram.{self.surface} rendering.",
                )
            )

        metadata = _metadata(record)
        provenance_line = _optional_text(metadata, "provenance_line", issues)
        cta = _optional_text(metadata, "cta", issues)
        hashtags = _hashtags(metadata, issues)
        raw_ai_required = metadata.get("ai_audio_disclosure_required", False)
        if not isinstance(raw_ai_required, bool):
            issues.append(
                RenderIssue(
                    code="instagram_ai_audio_disclosure_type",
                    severity="error",
                    message="rendering_metadata.instagram.ai_audio_disclosure_required must be boolean.",
                )
            )
            ai_required = False
        else:
            ai_required = raw_ai_required

        question = f"{record.question.lead} {record.question.text}".strip()
        text, caption_issues = render_instagram_caption(
            project_key=record.project_key,
            topic_line=record.fact.heading,
            body=record.fact.text,
            question=question,
            provenance_line=provenance_line,
            cta=cta,
            hashtags=hashtags,
            ai_audio_disclosure_required=ai_required,
        )
        issues.extend(caption_issues)
        return RenderedContent(
            platform=self.platform,
            surface=self.surface,
            text=text,
            character_count=len(text),
            link_count=count_urls(text),
            issues=tuple(issues),
        )


class InstagramReelCaptionRenderer(_InstagramRenderer):
    surface: ContentSurface = "reel"


class InstagramFeedCaptionRenderer(_InstagramRenderer):
    surface: ContentSurface = "feed"


class InstagramCarouselCaptionRenderer(_InstagramRenderer):
    surface: ContentSurface = "carousel"


__all__ = [
    "InstagramCarouselCaptionRenderer",
    "InstagramFeedCaptionRenderer",
    "InstagramReelCaptionRenderer",
    "render_instagram_caption",
]
