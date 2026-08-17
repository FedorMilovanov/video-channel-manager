Describe "Resi/DASH generated handoff" {
    It "is discoverable from the primary CLI and parses as PowerShell" {
        $Output = Join-Path $TestDrive "resi-handoff.ps1"
        $Url = "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd?src=emb"

        & video-manager resi handoff $Url --start "50:12" --end "1:49:52" --output $Output
        $LASTEXITCODE | Should -Be 0
        Test-Path -LiteralPath $Output -PathType Leaf | Should -BeTrue

        $Tokens = $null
        $ParseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $Output,
            [ref]$Tokens,
            [ref]$ParseErrors
        ) | Out-Null

        $ParseErrors.Count | Should -Be 0
        $Content = Get-Content -Raw -LiteralPath $Output
        $TrimStartPattern = [regex]::Escape('$TrimStart = ''00:50:12''')
        $TrimDurationPattern = [regex]::Escape('$TrimDuration = ''00:59:40''')
        $DownloadsPattern = [regex]::Escape('[string]$DownloadsRoot = "C:\Users\Fedor\Downloads"')
        $MasterPattern = [regex]::Escape('$Master = Join-Path $DownloadsRoot ($Title + " - FULL.mp4")')
        $Content | Should -Match $TrimStartPattern
        $Content | Should -Match $TrimDurationPattern
        $Content | Should -Match $DownloadsPattern
        $Content | Should -Match $MasterPattern
        $Content | Should -Not -Match "--retries infinite"
        $Content | Should -Match "video-manager\.resi-result"
    }

    It "executes download, exact trim, receipts, and offline-safe master reuse with provider-free PATH shims" {
        $Output = Join-Path $TestDrive "resi-executable-handoff.ps1"
        $Url = "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd?src=emb"
        $ToolDir = Join-Path $TestDrive "fake-tools"
        $StateDir = Join-Path $TestDrive "fake-state"
        $DownloadsRoot = Join-Path $TestDrive "Downloads"
        New-Item -ItemType Directory -Force -Path $ToolDir, $StateDir | Out-Null

        $FakeTool = Join-Path $ToolDir "fake-tools.py"
        @'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

state = Path(os.environ["RESI_FAKE_STATE"])
state.mkdir(parents=True, exist_ok=True)


def bump(name: str) -> None:
    path = state / f"{name}.count"
    current = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(current + 1), encoding="utf-8")


def main() -> int:
    tool = sys.argv[1]
    args = sys.argv[2:]

    if tool == "yt-dlp":
        if "-F" in args:
            bump("inspect")
            print("0 mp4 1920x1080 video only")
            print("1 m4a audio only")
            return 0
        output_index = args.index("-o") + 1
        output = Path(args[output_index])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-master-bytes")
        bump("download")
        return 0

    if tool == "ffprobe":
        target = Path(args[-1])
        duration = "7200.000" if target.name.endswith(" - FULL.mp4") else "3580.000"
        print(
            json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "h264",
                            "width": 1920,
                            "height": 1080,
                            "r_frame_rate": "30/1",
                            "bit_rate": "4000000",
                        },
                        {
                            "codec_type": "audio",
                            "codec_name": "aac",
                            "sample_rate": "48000",
                            "channels": 2,
                        },
                    ],
                    "format": {
                        "duration": duration,
                        "size": "1234",
                        "bit_rate": "4200000",
                    },
                }
            )
        )
        return 0

    if tool == "ffmpeg":
        if "-encoders" in args:
            print(" V..... libx264")
            return 0
        clip = Path(args[-1])
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"fake-clip-bytes")
        bump("trim")
        return 0

    raise SystemExit(f"unexpected fake tool: {tool}")


if __name__ == "__main__":
    raise SystemExit(main())
'@ | Set-Content -LiteralPath $FakeTool -Encoding UTF8

        $IsWindowsRunner = $env:OS -eq "Windows_NT"
        foreach ($Tool in @("yt-dlp", "ffprobe", "ffmpeg")) {
            if ($IsWindowsRunner) {
                $Wrapper = Join-Path $ToolDir ($Tool + ".cmd")
                @"
@echo off
python "%~dp0fake-tools.py" $Tool %*
exit /b %ERRORLEVEL%
"@ | Set-Content -LiteralPath $Wrapper -Encoding ASCII
            }
            else {
                $Wrapper = Join-Path $ToolDir $Tool
                @"
#!/usr/bin/env sh
exec python "`$(dirname "`$0")/fake-tools.py" $Tool "`$@"
"@ | Set-Content -LiteralPath $Wrapper -Encoding UTF8
                & chmod +x $Wrapper
                $LASTEXITCODE | Should -Be 0
            }
        }

        $OriginalPath = $env:PATH
        $OriginalFakeState = $env:RESI_FAKE_STATE
        $env:PATH = $ToolDir + [IO.Path]::PathSeparator + $OriginalPath
        $env:RESI_FAKE_STATE = $StateDir

        try {
            & video-manager resi handoff $Url --title "Fixture" --start "50:12" --end "1:49:52" --output $Output
            $LASTEXITCODE | Should -Be 0

            & $Output -RepositoryRoot $TestDrive -DownloadsRoot $DownloadsRoot

            $Outbox = Join-Path $TestDrive "operator-output"
            $Master = Join-Path $DownloadsRoot "Fixture - FULL.mp4"
            $ReceiptPath = Join-Path $Outbox "Fixture - FULL.source.json"
            $Clip = Join-Path $Outbox "Fixture.mp4"
            $ResultPath = Join-Path $Outbox "Fixture - result.json"

            Test-Path -LiteralPath $Master -PathType Leaf | Should -BeTrue
            Test-Path -LiteralPath (Join-Path $Outbox "Fixture - FULL.mp4") | Should -BeFalse
            Test-Path -LiteralPath $ReceiptPath -PathType Leaf | Should -BeTrue
            Test-Path -LiteralPath $Clip -PathType Leaf | Should -BeTrue
            Test-Path -LiteralPath $ResultPath -PathType Leaf | Should -BeTrue
            (Get-Content -Raw -LiteralPath (Join-Path $StateDir "inspect.count")) | Should -Be "1"
            (Get-Content -Raw -LiteralPath (Join-Path $StateDir "download.count")) | Should -Be "1"
            (Get-Content -Raw -LiteralPath (Join-Path $StateDir "trim.count")) | Should -Be "1"

            $Receipt = Get-Content -Raw -LiteralPath $ReceiptPath | ConvertFrom-Json
            $Result = Get-Content -Raw -LiteralPath $ResultPath | ConvertFrom-Json
            $Receipt.schema_name | Should -Be "video-manager.resi-source-receipt"
            $Receipt.master_path | Should -Be $Master
            $Receipt.master_sha256 | Should -Match "^sha256:[0-9a-f]{64}$"
            $Result.schema_name | Should -Be "video-manager.resi-result"
            $Result.mode | Should -Be "exact_trim"
            $Result.master_path | Should -Be $Master
            $Result.master_sha256 | Should -Be $Receipt.master_sha256
            $Result.clip_sha256 | Should -Match "^sha256:[0-9a-f]{64}$"
            $Result.trim_start | Should -Be "00:50:12"
            $Result.trim_end | Should -Be "01:49:52"
            [double]$Result.actual_duration_seconds | Should -Be 3580
            $Result.encoder | Should -Be "cpu"

            & $Output -RepositoryRoot $TestDrive -DownloadsRoot $DownloadsRoot
            (Get-Content -Raw -LiteralPath (Join-Path $StateDir "inspect.count")) | Should -Be "1"
            (Get-Content -Raw -LiteralPath (Join-Path $StateDir "download.count")) | Should -Be "1"
            (Get-Content -Raw -LiteralPath (Join-Path $StateDir "trim.count")) | Should -Be "2"
        }
        finally {
            $env:PATH = $OriginalPath
            $env:RESI_FAKE_STATE = $OriginalFakeState
        }
    }
}
