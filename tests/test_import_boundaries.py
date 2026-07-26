from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_IMPORT_STATEMENTS = (
    "import scripts.audit_youtube_comments",
    "import scripts.apply_youtube_comment_plan",
    "import video_channel_manager.platforms.youtube.comments",
    "import video_channel_manager.platforms.youtube.renderers",
    "import video_channel_manager.editorial.content",
    "import video_channel_manager.editorial.preview",
    "from video_channel_manager.editorial import preview_payload",
    "from video_channel_manager.platforms.youtube import YouTubeCommentRenderer",
    "from video_channel_manager.platforms.vk import VKCommentRenderer",
)


@pytest.mark.parametrize("statement", _IMPORT_STATEMENTS)
def test_operational_imports_work_in_a_clean_interpreter(statement: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert completed.returncode == 0, (
        f"Fresh interpreter import failed for {statement!r}.\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
