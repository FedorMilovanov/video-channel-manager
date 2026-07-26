from __future__ import annotations

import subprocess
import sys
from textwrap import dedent


def _run_fresh_python(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", dedent(source)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_youtube_comments_can_import_before_editorial_preview() -> None:
    result = _run_fresh_python(
        """
        from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter
        from video_channel_manager.editorial import preview_payload, renderer_for

        assert YouTubeCommentWriter.__name__ == "YouTubeCommentWriter"
        assert callable(preview_payload)
        assert callable(renderer_for)
        """
    )
    assert result.returncode == 0, result.stderr


def test_youtube_renderers_and_preview_import_in_fresh_process() -> None:
    result = _run_fresh_python(
        """
        from video_channel_manager.platforms.youtube.renderers import (
            YouTubeCommentRenderer,
            YouTubeDescriptionRenderer,
        )
        from video_channel_manager.editorial.preview import preview_payload

        assert YouTubeCommentRenderer.__name__ == "YouTubeCommentRenderer"
        assert YouTubeDescriptionRenderer.__name__ == "YouTubeDescriptionRenderer"
        assert callable(preview_payload)
        """
    )
    assert result.returncode == 0, result.stderr
