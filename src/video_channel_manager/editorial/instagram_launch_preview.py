from __future__ import annotations

from video_channel_manager.exchange.instagram_content import (
    InstagramLaunchPack,
    InstagramLaunchPreviewArtifact,
    InstagramLaunchPreviewCounts,
    InstagramLaunchPreviewIssue,
    InstagramLaunchPreviewItem,
)
from video_channel_manager.platforms.instagram.renderers import render_instagram_caption


def build_instagram_launch_preview(
    pack: InstagramLaunchPack,
    *,
    source_pack_sha256: str,
) -> InstagramLaunchPreviewArtifact:
    """Render one exact launch pack without provider access or mutation."""

    items: list[InstagramLaunchPreviewItem] = []
    warning_count = 0
    error_count = 0
    valid_count = 0

    for candidate in pack.candidates:
        text, issues = render_instagram_caption(
            project_key=pack.project_key,
            topic_line=candidate.topic_line,
            body=candidate.caption_body,
            provenance_line=candidate.provenance_line or "",
            cta=candidate.cta,
            hashtags=candidate.hashtags,
            ai_audio_disclosure_required=candidate.ai_audio_disclosure_required,
        )
        rendered_issues = tuple(
            InstagramLaunchPreviewIssue(
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                line_number=issue.line_number,
            )
            for issue in issues
        )
        errors = sum(1 for issue in rendered_issues if issue.severity == "error")
        warnings = sum(1 for issue in rendered_issues if issue.severity == "warning")
        error_count += errors
        warning_count += warnings
        if errors == 0:
            valid_count += 1

        items.append(
            InstagramLaunchPreviewItem(
                candidate_id=candidate.candidate_id,
                surface=candidate.surface,
                rendered_caption=text,
                character_count=len(text),
                hashtag_count=len(candidate.hashtags),
                blocking_unknowns=candidate.blocking_unknowns,
                issues=rendered_issues,
            )
        )

    total = len(items)
    return InstagramLaunchPreviewArtifact(
        project_key=pack.project_key,
        source_pack_sha256=source_pack_sha256,
        items=tuple(items),
        counts=InstagramLaunchPreviewCounts(
            total=total,
            valid=valid_count,
            blocked=total - valid_count,
            warnings=warning_count,
            errors=error_count,
        ),
    )


__all__ = ["build_instagram_launch_preview"]
