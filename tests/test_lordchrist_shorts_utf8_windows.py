from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from video_channel_manager.lordchrist_shorts import ffprobe_media


def test_ffprobe_media_decodes_json_as_utf8_even_with_windows_ansi_locale(
    monkeypatch: Any,
) -> None:
    filename = Path("Документальная запись «Свет Отрадный».mp4")
    payload = {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "tags": {"title": "Свет Отрадный"}},
        "streams": [{"codec_type": "video", "codec_name": "h264", "width": 720, "height": 1280}],
    }
    invoked = []

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        invoked.append((argv, kwargs))
        assert argv[0] == "ffprobe"
        assert argv[-1] == str(filename)
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload, ensure_ascii=False))

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert ffprobe_media(filename) == payload
    assert len(invoked) == 1
