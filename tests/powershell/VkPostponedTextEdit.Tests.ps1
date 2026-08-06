BeforeAll {
    $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "../..")).Path
    $WrapperPath = Join-Path $RepoRoot "scripts/Invoke-VkPostponedTextEdit.ps1"
    . $WrapperPath
}

BeforeEach {
    $TestRoot = Join-Path ([IO.Path]::GetTempPath()) ("vcm-vk-postponed-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $TestRoot -Force | Out-Null
    $InputPath = Join-Path $TestRoot "input.json"
    Set-Content -LiteralPath $InputPath -Value "{}" -Encoding UTF8
}

AfterEach {
    Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Describe "Invoke-VkPostponedTextEdit wrapper" {
    It "builds an exact read-only plan command" {
        $OutputPath = Join-Path $TestRoot "plan.json"

        $Arguments = New-VkPostponedTextCliArguments `
            -Command plan `
            -InputPath $InputPath `
            -OutputPath $OutputPath `
            -AccountAlias legendary-poet

        $Arguments | Should -Contain "video_channel_manager.cli.vk_postponed_text"
        $Arguments | Should -Contain "plan"
        $Arguments | Should -Contain (Resolve-Path -LiteralPath $InputPath).Path
        $Arguments | Should -Contain ([IO.Path]::GetFullPath($OutputPath))
        $Arguments | Should -Not -Contain "--enable-provider-writes"
        $Arguments | Should -Not -Contain "--confirm-plan-sha256"
    }

    It "refuses apply without exact digest confirmation" {
        {
            New-VkPostponedTextCliArguments `
                -Command apply `
                -InputPath $InputPath `
                -OutputDirectory (Join-Path $TestRoot "run") `
                -EnableProviderWrites
        } | Should -Throw "*sha256:*"
    }

    It "refuses apply without the explicit write switch" {
        {
            New-VkPostponedTextCliArguments `
                -Command apply `
                -InputPath $InputPath `
                -OutputDirectory (Join-Path $TestRoot "run") `
                -ConfirmPlanSha256 ("sha256:" + ("a" * 64))
        } | Should -Throw "*EnableProviderWrites*"
    }

    It "forwards the guarded apply controls to the package CLI" {
        $Digest = "sha256:" + ("a" * 64)
        $OutputDirectory = Join-Path $TestRoot "run"

        $Arguments = New-VkPostponedTextCliArguments `
            -Command apply `
            -InputPath $InputPath `
            -OutputDirectory $OutputDirectory `
            -ConfirmPlanSha256 $Digest `
            -EnableProviderWrites `
            -MinimumFutureSeconds 900 `
            -InterOperationDelaySeconds 30 `
            -PostflightDelaySeconds 4 `
            -TransientRetryDelaySeconds 120 `
            -MaxTransientRetries 0

        $Arguments | Should -Contain "apply"
        $Arguments | Should -Contain "--enable-provider-writes"
        $Arguments | Should -Contain "--confirm-plan-sha256"
        $Arguments | Should -Contain $Digest
        $Arguments | Should -Contain "900"
        $Arguments | Should -Contain "30"
        $Arguments | Should -Contain "4"
        $Arguments | Should -Contain "120"
        $Arguments | Should -Contain "0"
    }

    It "propagates a nonzero native CLI exit as a terminating error" {
        Mock Invoke-VcmNativeCommand { return 7 }

        {
            Invoke-VkPostponedTextEdit `
                -Command plan `
                -InputPath $InputPath `
                -OutputPath (Join-Path $TestRoot "plan.json") `
                -PythonCommand python
        } | Should -Throw "*exit code 7*"

        Should -Invoke Invoke-VcmNativeCommand -Times 1 -Exactly
    }

    It "contains no token or direct VK API transport parameters" {
        $Source = Get-Content -LiteralPath $WrapperPath -Raw

        $Source | Should -Not -Match "VK_API_TOKEN"
        $Source | Should -Not -Match "access_token"
        $Source | Should -Not -Match "Invoke-RestMethod"
        $Source | Should -Match "video_channel_manager\.cli\.vk_postponed_text"
    }
}
