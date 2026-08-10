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
        $Content | Should -Match [regex]::Escape("$TrimStart = '00:50:12'")
        $Content | Should -Match [regex]::Escape("$TrimDuration = '00:59:40'")
        $Content | Should -Not -Match "--retries infinite"
        $Content | Should -Match "video-manager\.resi-result"
    }
}
