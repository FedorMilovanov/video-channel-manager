from __future__ import annotations

import pytest

from video_channel_manager.resi_handoff import (
    ResiHandoffSpec,
    canonical_source_identity,
    default_title_for_url,
    format_timestamp,
    parse_timestamp,
    render_powershell_handoff,
    windows_safe_name,
)

URL = "https://resi.media/GiHDtf/example/Manifest.mpd?src=emb"
REALISTIC_URL = "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd?src=emb"


def test_abner_trim_math_accepts_operator_friendly_minute_timestamp() -> None:
    assert parse_timestamp("50:12") == 3012
    assert parse_timestamp("1:49:52") == 6592
    assert format_timestamp(6592 - 3012) == "00:59:40"


def test_minute_only_timestamp_may_exceed_59_minutes() -> None:
    assert parse_timestamp("90:00") == 5400
    assert format_timestamp(5400) == "01:30:00"


def test_millisecond_timestamp_round_trip() -> None:
    assert parse_timestamp("00:01.250") == 1.25
    assert parse_timestamp("00:00:01.250") == 1.25
    assert format_timestamp(1.25) == "00:00:01.250"


@pytest.mark.parametrize("value", ["1:60", "00:60:00", "bad", "1:02:03.1234"])
def test_rejects_invalid_timestamps(value: str) -> None:
    with pytest.raises(ValueError, match="invalid timestamp"):
        parse_timestamp(value)


def test_windows_safe_name_preserves_cyrillic_and_removes_invalid_characters() -> None:
    assert windows_safe_name("Абнер: Израиль?") == "Абнер- Израиль-"
    assert windows_safe_name("CON") == "_CON"
    assert windows_safe_name("AUX.notes") == "_AUX.notes"
    assert len(windows_safe_name("x" * 300)) == 140


def test_rejects_non_mpd_url() -> None:
    with pytest.raises(ValueError, match="DASH .mpd"):
        ResiHandoffSpec("https://example.com/video.mp4", "Video")


def test_source_identity_ignores_resi_transient_query_but_preserves_generic_dash_query() -> None:
    assert canonical_source_identity(REALISTIC_URL) == (
        "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd"
    )
    assert default_title_for_url(REALISTIC_URL) == "Resi 9aa9ac24-fb79-4ca9-95ef-a3253afdf63f"
    assert ResiHandoffSpec(REALISTIC_URL).safe_title == "Resi 9aa9ac24-fb79-4ca9-95ef-a3253afdf63f"
    assert (
        ResiHandoffSpec(REALISTIC_URL).source_fingerprint
        == ResiHandoffSpec(REALISTIC_URL.replace("?src=emb", "?token=rotated")).source_fingerprint
    )

    generic_a = "https://media.example/video/Manifest.mpd?variant=a"
    generic_b = "https://media.example/video/Manifest.mpd?variant=b"
    assert canonical_source_identity(generic_a).endswith("Manifest.mpd?variant=a")
    assert (
        ResiHandoffSpec(generic_a).source_fingerprint
        != ResiHandoffSpec(generic_b).source_fingerprint
    )


def test_requires_both_trim_bounds() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        ResiHandoffSpec(URL, "Service", start="10:00")


def test_rejects_reversed_trim_bounds() -> None:
    with pytest.raises(ValueError, match="later than start"):
        ResiHandoffSpec(URL, "Service", start="20:00", end="10:00")


def test_render_is_self_contained_provenance_bound_and_not_chat_escaped() -> None:
    script = render_powershell_handoff(
        ResiHandoffSpec(
            URL,
            "Как Христианам Понимать Израиль - Абнер Чау",
            "50:12",
            "1:49:52",
        )
    )

    assert script.startswith("param(\n")
    assert '[string]$RepositoryRoot = "C:\\Users\\Fedor\\Projects\\video-channel-manager"' in script
    assert '$ErrorActionPreference = "Stop"' in script
    assert "$Repo = $RepositoryRoot" in script
    assert "$OperatorOutput =" in script
    assert "$Master =" in script
    assert "$SourceReceipt =" in script
    assert "$Result =" in script
    assert "$Clip =" in script
    assert "$Downloads" not in script
    assert "$Work" not in script
    assert "bestvideo+bestaudio/best" in script
    assert "--retries 10 --fragment-retries 10" in script
    assert "--retries infinite" not in script
    assert "Verified master is reusable; skipping remote format inspection and download." in script
    assert "$TrimStart = '00:50:12'" in script
    assert "$TrimEnd = '01:49:52'" in script
    assert "$TrimDuration = '00:59:40'" in script
    assert "$ExpectedDurationSeconds = 3580.000" in script
    assert "h264_nvenc" in script
    assert '"-cq", "21"' in script
    assert "libx264" in script
    assert '"-c:a", "copy"' in script
    assert "source_fingerprint" in script
    assert "master_sha256" in script
    assert "clip_sha256" in script
    assert "Existing master has no source receipt" in script
    assert "Master QC failed: no video stream" in script
    assert "Master QC failed: no audio stream" in script
    assert "$MasterProbe.format.bit_rate" in script
    assert "RESULT READY" in script
    assert "\\:" not in script
    assert "\\_" not in script


def test_render_download_only_keeps_hashes_and_receipts_master() -> None:
    script = render_powershell_handoff(ResiHandoffSpec(URL))

    assert "MASTER READY" in script
    assert "MASTER SHA256" in script
    assert "RESULT READY" in script
    assert "video-manager.resi-source-receipt" in script
    assert 'mode = "download_only"' in script
    assert "$Clip" not in script
    assert "operator-output" in script


def test_powershell_single_quote_is_escaped() -> None:
    script = render_powershell_handoff(ResiHandoffSpec(URL, "Pastor's Message"))
    assert "$Title = 'Pastor''s Message'" in script
