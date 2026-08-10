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
        $Content | Should -Match $TrimStartPattern
        $Content | Should -Match $TrimDurationPattern
        $Content | Should -Not -Match "--retries infinite"
        $Content | Should -Match "video-manager\.resi-result"
    }

    It "executes download, exact trim, receipts, and offline-safe master reuse with provider-free tool doubles" {
        $Output = Join-Path $TestDrive "resi-executable-handoff.ps1"
        $Url = "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd?src=emb"
        $ResiFakeInspectCount = 0
        $ResiFakeDownloadCount = 0
        $ResiFakeTrimCount = 0

        function yt-dlp {
            if ($args -contains "-F") {
                $script:ResiFakeInspectCount += 1
                Set-Variable -Name LASTEXITCODE -Value 0 -Scope 1
                "0 mp4 1920x1080 video only"
                "1 m4a audio only"
                return
            }

            $OutputPath = $null
            for ($Index = 0; $Index -lt $args.Count; $Index++) {
                if ($args[$Index] -eq "-o") {
                    $OutputPath = [string]$args[$Index + 1]
                    break
                }
            }
            if (-not $OutputPath) { throw "fake yt-dlp did not receive -o" }
            [System.IO.File]::WriteAllText($OutputPath, "fake-master-bytes")
            $script:ResiFakeDownloadCount += 1
            Set-Variable -Name LASTEXITCODE -Value 0 -Scope 1
        }

        function ffprobe {
            $Target = [string]$args[$args.Count - 1]
            $Duration = if ($Target -like "* - FULL.mp4") { "7200.000" } else { "3580.000" }
            Set-Variable -Name LASTEXITCODE -Value 0 -Scope 1
            @"
{"streams":[{"codec_type":"video","codec_name":"h264","width":1920,"height":1080,"r_frame_rate":"30/1","bit_rate":"4000000"},{"codec_type":"audio","codec_name":"aac","sample_rate":"48000","channels":2}],"format":{"duration":"$Duration","size":"1234","bit_rate":"4200000"}}
"@
        }

        function ffmpeg {
            if ($args -contains "-encoders") {
                Set-Variable -Name LASTEXITCODE -Value 0 -Scope 1
                " V..... libx264"
                return
            }
            $ClipPath = [string]$args[$args.Count - 1]
            [System.IO.File]::WriteAllText($ClipPath, "fake-clip-bytes")
            $script:ResiFakeTrimCount += 1
            Set-Variable -Name LASTEXITCODE -Value 0 -Scope 1
        }

        & video-manager resi handoff $Url --title "Fixture" --start "50:12" --end "1:49:52" --output $Output
        $LASTEXITCODE | Should -Be 0

        . $Output -RepositoryRoot $TestDrive

        $Outbox = Join-Path $TestDrive "operator-output"
        $Master = Join-Path $Outbox "Fixture - FULL.mp4"
        $ReceiptPath = Join-Path $Outbox "Fixture - FULL.source.json"
        $Clip = Join-Path $Outbox "Fixture.mp4"
        $ResultPath = Join-Path $Outbox "Fixture - result.json"

        Test-Path -LiteralPath $Master -PathType Leaf | Should -BeTrue
        Test-Path -LiteralPath $ReceiptPath -PathType Leaf | Should -BeTrue
        Test-Path -LiteralPath $Clip -PathType Leaf | Should -BeTrue
        Test-Path -LiteralPath $ResultPath -PathType Leaf | Should -BeTrue
        $script:ResiFakeInspectCount | Should -Be 1
        $script:ResiFakeDownloadCount | Should -Be 1
        $script:ResiFakeTrimCount | Should -Be 1

        $Receipt = Get-Content -Raw -LiteralPath $ReceiptPath | ConvertFrom-Json
        $Result = Get-Content -Raw -LiteralPath $ResultPath | ConvertFrom-Json
        $Receipt.schema_name | Should -Be "video-manager.resi-source-receipt"
        $Receipt.master_sha256 | Should -Match "^sha256:[0-9a-f]{64}$"
        $Result.schema_name | Should -Be "video-manager.resi-result"
        $Result.mode | Should -Be "exact_trim"
        $Result.master_sha256 | Should -Be $Receipt.master_sha256
        $Result.clip_sha256 | Should -Match "^sha256:[0-9a-f]{64}$"
        $Result.trim_start | Should -Be "00:50:12"
        $Result.trim_end | Should -Be "01:49:52"
        [double]$Result.actual_duration_seconds | Should -Be 3580
        $Result.encoder | Should -Be "cpu"

        . $Output -RepositoryRoot $TestDrive
        $script:ResiFakeInspectCount | Should -Be 1
        $script:ResiFakeDownloadCount | Should -Be 1
        $script:ResiFakeTrimCount | Should -Be 2
    }
}
