from __future__ import annotations

import pytest

from video_channel_manager.resi_handoff import (
    ResiHandoffSpec,
    format_timestamp,
    parse_timestamp,
    render_powershell_handoff,
    windows_safe_name,
)

URL = "https://resi.media/GiHDtf/example/Manifest.mpd?src=emb"


def test_abner_trim_math() -> None:
    assert parse_timestamp("00:50:12") == 3012
    assert parse_timestamp("01:49:52") == 6592
    assert format_timestamp(6592 - 3012) == "00:59:40"


def test_millisecond_timestamp_round_trip() -> None:
    assert parse_timestamp("00:00:01.250") == 1.25
    assert format_timestamp(1.25) == "00:00:01.250"


def test_windows_safe_name_preserves_cyrillic_and_removes_invalid_characters() -> None:
    assert windows_safe_name("Абнер: Израиль?") == "Абнер- Израиль-"
    assert windows_safe_name("CON") == "_CON"


def test_rejects_non_mpd_url() -> None:
    with pytest.raises(ValueError, match="DASH .mpd"):
        ResiHandoffSpec("https://example.com/video.mp4", "Video")


def test_requires_both_trim_bounds() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        ResiHandoffSpec(URL, "Service", start="00:10:00")


def test_rejects_reversed_trim_bounds() -> None:
    with pytest.raises(ValueError, match="later than start"):
        ResiHandoffSpec(URL, "Service", start="00:20:00", end="00:10:00")


def test_render_is_self_contained_and_not_chat_escaped() -> None:
    script = render_powershell_handoff(
        ResiHandoffSpec(
            URL,
            "Как Христианам Понимать Израиль - Абнер Чау",
            "00:50:12",
            "01:49:52",
        )
    )

    assert '$ErrorActionPreference = "Stop"' in script
    assert "$Downloads =" in script
    assert "$Work =" in script
    assert "$Master =" in script
    assert "$Clip =" in script
    assert "bestvideo+bestaudio/best" in script
    assert "$TrimDuration = '00:59:40'" in script
    assert "$ExpectedDurationSeconds = 3580.000" in script
    assert "h264_nvenc" in script
    assert '"-cq", "21"' in script
    assert "libx264" in script
    assert '"-c:a", "copy"' in script
    assert "\\:" not in script
    assert "\\_" not in script


def test_render_download_only_keeps_and_hashes_master() -> None:
    script = render_powershell_handoff(ResiHandoffSpec(URL, "Full Service"))

    assert "MASTER READY" in script
    assert "$Clip" not in script
    assert "Get-FileHash" in script


def test_powershell_single_quote_is_escaped() -> None:
    script = render_powershell_handoff(ResiHandoffSpec(URL, "Pastor's Message"))
    assert "$Title = 'Pastor''s Message'" in script
