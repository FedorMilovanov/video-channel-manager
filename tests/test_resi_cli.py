from __future__ import annotations

from typer.testing import CliRunner

from video_channel_manager.cli.app import app

URL = "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd?src=emb"


def test_primary_cli_generates_bom_handoff_with_human_timestamps(tmp_path) -> None:
    output = tmp_path / "resi-handoff.ps1"
    result = CliRunner().invoke(
        app,
        [
            "resi",
            "handoff",
            URL,
            "--start",
            "50:12",
            "--end",
            "1:49:52",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.is_file()
    assert output.read_bytes().startswith(b"\xef\xbb\xbf")
    script = output.read_text(encoding="utf-8-sig")
    assert "$Title = 'Resi 9aa9ac24-fb79-4ca9-95ef-a3253afdf63f'" in script
    assert "$TrimStart = '00:50:12'" in script
    assert "$TrimEnd = '01:49:52'" in script
    assert "$TrimDuration = '00:59:40'" in script
    assert "Provider effect: impossible" in result.output
