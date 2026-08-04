BeforeAll {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    $ModulePath = Join-Path $RepoRoot "scripts\operator\VideoManager.Operator.psm1"
    Import-Module -Name $ModulePath -Force -ErrorAction Stop
}

Describe "Wave 7 PowerShell mutation-boundary faults" {
    BeforeEach {
        $TestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("vcm-wave7-operator-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $TestRoot -Force | Out-Null
        $Python = Resolve-VcmPython -RepositoryRoot $RepoRoot -ProbeDirectory $TestRoot
    }

    AfterEach {
        Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    It "terminates an interrupted child at the reviewed timeout boundary" {
        $StdoutPath = Join-Path $TestRoot "timeout.stdout.log"
        $StderrPath = Join-Path $TestRoot "timeout.stderr.log"
        $Result = Invoke-VcmNativeProcess `
            -FilePath $Python.path `
            -ArgumentList @("-X", "utf8", "-c", "import time; print('started', flush=True); time.sleep(30)") `
            -WorkingDirectory $RepoRoot `
            -StdoutPath $StdoutPath `
            -StderrPath $StderrPath `
            -TimeoutSeconds 1

        $Result.exit_code | Should -Be 124
        $Result.timed_out | Should -BeTrue
        $Result.termination_kind | Should -Be "timeout"
        $Result.timeout_seconds | Should -Be 1
        $Result.duration_ms | Should -BeLessThan 10000
        (Test-Path -LiteralPath $StdoutPath -PathType Leaf) | Should -BeTrue
        (Test-Path -LiteralPath $StderrPath -PathType Leaf) | Should -BeTrue
        (Get-Content -LiteralPath $StdoutPath -Raw -Encoding UTF8) | Should -Match "started"
    }

    It "drains concurrent stdout and stderr without deadlock" {
        $StdoutPath = Join-Path $TestRoot "large.stdout.log"
        $StderrPath = Join-Path $TestRoot "large.stderr.log"
        $Result = Invoke-VcmNativeProcess `
            -FilePath $Python.path `
            -ArgumentList @(
                "-X", "utf8", "-c",
                "import sys; sys.stdout.write('o'*262144); sys.stderr.write('e'*262144)"
            ) `
            -WorkingDirectory $RepoRoot `
            -StdoutPath $StdoutPath `
            -StderrPath $StderrPath `
            -TimeoutSeconds 15

        $Result.exit_code | Should -Be 0
        $Result.timed_out | Should -BeFalse
        $Result.termination_kind | Should -Be "exit"
        (Get-Item -LiteralPath $StdoutPath).Length | Should -Be 262144
        (Get-Item -LiteralPath $StderrPath).Length | Should -Be 262144
    }

    It "classifies outcomes from exit evidence and never from stdout wording" {
        $SafeFailure = Get-VcmOperatorOutcome -OperationClass "safe_read" -ExitCode 7
        $SafeFailure.status | Should -Be "failed"
        $SafeFailure.retry_safe | Should -BeTrue
        $SafeFailure.unknown_requires_reconciliation | Should -BeFalse

        $MutationFailure = Get-VcmOperatorOutcome -OperationClass "ambiguous_mutation" -ExitCode 7
        $MutationFailure.status | Should -Be "unknown_requires_reconciliation"
        $MutationFailure.retry_safe | Should -BeFalse
        $MutationFailure.unknown_requires_reconciliation | Should -BeTrue

        $MutationTimeout = Get-VcmOperatorOutcome -OperationClass "ambiguous_mutation" -ExitCode 124 -TimedOut $true
        $MutationTimeout.status | Should -Be "unknown_requires_reconciliation"
        $MutationTimeout.retry_safe | Should -BeFalse
        $MutationTimeout.unknown_requires_reconciliation | Should -BeTrue

        $Success = Get-VcmOperatorOutcome -OperationClass "ambiguous_mutation" -ExitCode 0
        $Success.status | Should -Be "succeeded"
        $Success.retry_safe | Should -BeFalse
        $Success.unknown_requires_reconciliation | Should -BeFalse
    }

    It "rejects missing and malformed structured result evidence" {
        $Missing = Join-Path $TestRoot "missing-result.json"
        { Read-VcmOperatorResult -Path $Missing } | Should -Throw "*does not exist*"

        $Malformed = Join-Path $TestRoot "malformed-result.json"
        Write-VcmUtf8Text -Path $Malformed -Text "{"
        { Read-VcmOperatorResult -Path $Malformed } | Should -Throw "*Invalid JSON file*"
    }

    It "rejects inconsistent unknown result semantics" {
        $Path = Join-Path $TestRoot "result.json"
        Write-VcmJsonAtomic -Path $Path -Value ([ordered]@{
            schema_name = "video-manager.operator-result"
            schema_version = 1
            status = "unknown_requires_reconciliation"
            exit_code = 7
            retry_safe = $true
            unknown_requires_reconciliation = $true
            mode = "apply"
            project_key = "legendary-poet"
            request_sha256 = ("1" * 64)
            manifest_sha256 = ("2" * 64)
            preflight_path = "preflight-summary.json"
            result_path = $Path
            child = [ordered]@{
                file_path = $Python.path
            }
        })

        { Read-VcmOperatorResult -Path $Path } | Should -Throw "*semantics are inconsistent*"
    }
}
