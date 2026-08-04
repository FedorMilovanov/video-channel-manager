BeforeAll {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    $ModulePath = Join-Path $RepoRoot "scripts\operator\VideoManager.Operator.psm1"
    Import-Module -Name $ModulePath -Force -ErrorAction Stop

    function New-TestOperatorDocuments {
        param(
            [Parameter(Mandatory = $true)]
            [string]$Directory,
            [string]$Mode = "plan",
            [bool]$ProviderMutation = $false,
            [string]$OperationClass = "safe_read",
            [string[]]$Arguments = @("version"),
            [string]$ProjectKey = "legendary-poet",
            [int64]$CommunityId = 235216998,
            [int64]$OwnerId = -235216998,
            [int64]$OperationCount = 0
        )

        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
        $ManifestPath = Join-Path $Directory "manifest.json"
        $Manifest = [ordered]@{
            schema_name = "video-manager.operator-manifest"
            schema_version = 1
            project_key = $ProjectKey
            community_id = $CommunityId
            owner_id = $OwnerId
            source_snapshot_id = "snapshot-test-1"
            operation_count = $OperationCount
            operation_class = $OperationClass
            provider_mutation = $ProviderMutation
            entrypoint_id = "video-manager-cli"
            arguments = @($Arguments)
        }
        Write-VcmJsonAtomic -Path $ManifestPath -Value $Manifest
        $ManifestSha = Get-VcmSha256 -Path $ManifestPath

        $RequestPath = Join-Path $Directory "request.json"
        $Request = [ordered]@{
            schema_name = "video-manager.operator-request"
            schema_version = 1
            mode = $Mode
            manifest_path = $ManifestPath
            manifest_sha256 = $ManifestSha
            confirm_manifest_sha256 = $ManifestSha
            confirm_project_key = $ProjectKey
            confirm_community_id = $CommunityId
            confirm_owner_id = $OwnerId
            confirm_source_snapshot_id = "snapshot-test-1"
            confirm_operation_count = $OperationCount
        }
        Write-VcmJsonAtomic -Path $RequestPath -Value $Request
        return [pscustomobject]@{
            ManifestPath = $ManifestPath
            ManifestSha = $ManifestSha
            RequestPath = $RequestPath
            RequestSha = Get-VcmSha256 -Path $RequestPath
        }
    }
}

Describe "Wave 5 PowerShell operator contract" {
    BeforeEach {
        $TestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("vcm-wave5-tests-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $TestRoot -Force | Out-Null
        $OutputDir = Join-Path $TestRoot "output"
    }

    AfterEach {
        Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item Env:CI -ErrorAction SilentlyContinue
        Remove-Item Env:GITHUB_ACTIONS -ErrorAction SilentlyContinue
    }

    It "writes atomic JSON as UTF-8 without BOM" {
        $Path = Join-Path $TestRoot "evidence.json"
        Write-VcmJsonAtomic -Path $Path -Value ([ordered]@{ message = "Привет"; value = 7 })

        $Bytes = [System.IO.File]::ReadAllBytes($Path)
        $Bytes.Length | Should -BeGreaterThan 3
        ($Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) | Should -BeFalse
        (Read-VcmJsonFile -Path $Path).message | Should -Be "Привет"

        Write-VcmJsonAtomic -Path $Path -Value ([ordered]@{ message = "Заменено"; value = 8 })
        (Read-VcmJsonFile -Path $Path).message | Should -Be "Заменено"
        @(Get-ChildItem -LiteralPath $TestRoot -Filter ".evidence.json.*" -Force).Count | Should -Be 0
    }

    It "canonicalizes text digests across LF and CRLF checkouts" {
        $LfPath = Join-Path $TestRoot "lf.ps1"
        $CrlfPath = Join-Path $TestRoot "crlf.ps1"
        [System.IO.File]::WriteAllText($LfPath, "one`ntwo`n", (New-Object System.Text.UTF8Encoding($false)))
        [System.IO.File]::WriteAllText($CrlfPath, "one`r`ntwo`r`n", (New-Object System.Text.UTF8Encoding($false)))

        (Get-VcmCanonicalTextSha256 -Path $LfPath) | Should -Be (Get-VcmCanonicalTextSha256 -Path $CrlfPath)
    }

    It "resolves only a supported Python interpreter" {
        $Python = Resolve-VcmPython -RepositoryRoot $RepoRoot -ProbeDirectory $TestRoot
        $Python.version | Should -BeIn @("3.11", "3.12", "3.13")
        (Test-Path -LiteralPath $Python.path -PathType Leaf) | Should -BeTrue
    }

    It "does not fall back when an explicit Python path is invalid" {
        $InvalidPython = Join-Path $TestRoot "not-python.exe"
        Write-VcmUtf8Text -Path $InvalidPython -Text "not a Python interpreter"

        {
            Resolve-VcmPython -RepositoryRoot $RepoRoot -ExplicitPath $InvalidPython -ProbeDirectory $TestRoot
        } | Should -Throw "*explicit Python path*"
    }

    It "captures a native nonzero exit code without parsing human stdout" {
        $Python = Resolve-VcmPython -RepositoryRoot $RepoRoot -ProbeDirectory $TestRoot
        $Result = Invoke-VcmNativeProcess `
            -FilePath $Python.path `
            -ArgumentList @("-X", "utf8", "-c", "import sys; print('machine-output'); sys.exit(7)") `
            -WorkingDirectory $RepoRoot `
            -StdoutPath (Join-Path $TestRoot "stdout.log") `
            -StderrPath (Join-Path $TestRoot "stderr.log")

        $Result.exit_code | Should -Be 7
        (Get-Content -LiteralPath $Result.stdout_path -Raw -Encoding UTF8) | Should -Match "machine-output"
    }

    It "creates preflight and result evidence in plan mode without starting a child" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents")
        $Result = Invoke-VcmOperatorRequest `
            -RequestPath $Documents.RequestPath `
            -RequestSha256 $Documents.RequestSha `
            -OutputDirectory $OutputDir `
            -RepositoryRoot $RepoRoot

        $Result.status | Should -Be "planned"
        $Result.child | Should -BeNullOrEmpty
        (Test-Path -LiteralPath (Join-Path $OutputDir "preflight-summary.json")) | Should -BeTrue
        (Test-Path -LiteralPath (Join-Path $OutputDir "result.json")) | Should -BeTrue
    }

    It "executes a supported safe-read CLI command and preserves its exit code" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents") -Mode "dry-run"
        $Result = Invoke-VcmOperatorRequest `
            -RequestPath $Documents.RequestPath `
            -RequestSha256 $Documents.RequestSha `
            -OutputDirectory $OutputDir `
            -RepositoryRoot $RepoRoot

        $Result.status | Should -Be "succeeded"
        $Result.exit_code | Should -Be 0
        $Result.unknown_requires_reconciliation | Should -BeFalse
    }

    It "rejects an incorrect request digest before manifest execution" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents")
        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 ("0" * 64) `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*request SHA-256 mismatch*"
    }

    It "rejects string-typed IDs instead of coercing them" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents")
        $Manifest = Read-VcmJsonFile -Path $Documents.ManifestPath
        $Manifest.community_id = "235216998"
        Write-VcmJsonAtomic -Path $Documents.ManifestPath -Value $Manifest
        $ManifestSha = Get-VcmSha256 -Path $Documents.ManifestPath
        $Request = Read-VcmJsonFile -Path $Documents.RequestPath
        $Request.manifest_sha256 = $ManifestSha
        $Request.confirm_manifest_sha256 = $ManifestSha
        Write-VcmJsonAtomic -Path $Documents.RequestPath -Value $Request

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 (Get-VcmSha256 -Path $Documents.RequestPath) `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*exact integers*"
    }

    It "rejects numeric source snapshots instead of coercing them" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents")
        $Manifest = Read-VcmJsonFile -Path $Documents.ManifestPath
        $Request = Read-VcmJsonFile -Path $Documents.RequestPath
        $Manifest.source_snapshot_id = 123
        $Request.confirm_source_snapshot_id = 123
        Write-VcmJsonAtomic -Path $Documents.ManifestPath -Value $Manifest
        $ManifestSha = Get-VcmSha256 -Path $Documents.ManifestPath
        $Request.manifest_sha256 = $ManifestSha
        $Request.confirm_manifest_sha256 = $ManifestSha
        Write-VcmJsonAtomic -Path $Documents.RequestPath -Value $Request
        $RequestSha = Get-VcmSha256 -Path $Documents.RequestPath

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 $RequestSha `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*source snapshot*string*"
    }

    It "rejects a blank source snapshot even when both files agree" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents")
        $Manifest = Read-VcmJsonFile -Path $Documents.ManifestPath
        $Manifest.source_snapshot_id = ""
        Write-VcmJsonAtomic -Path $Documents.ManifestPath -Value $Manifest
        $ManifestSha = Get-VcmSha256 -Path $Documents.ManifestPath
        $Request = Read-VcmJsonFile -Path $Documents.RequestPath
        $Request.manifest_sha256 = $ManifestSha
        $Request.confirm_manifest_sha256 = $ManifestSha
        $Request.confirm_source_snapshot_id = ""
        Write-VcmJsonAtomic -Path $Documents.RequestPath -Value $Request

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 (Get-VcmSha256 -Path $Documents.RequestPath) `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*source snapshot confirmation must be a non-empty string*"
    }

    It "rejects a scalar arguments field" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents")
        $Manifest = Read-VcmJsonFile -Path $Documents.ManifestPath
        $Manifest.arguments = "version"
        Write-VcmJsonAtomic -Path $Documents.ManifestPath -Value $Manifest
        $ManifestSha = Get-VcmSha256 -Path $Documents.ManifestPath
        $Request = Read-VcmJsonFile -Path $Documents.RequestPath
        $Request.manifest_sha256 = $ManifestSha
        $Request.confirm_manifest_sha256 = $ManifestSha
        Write-VcmJsonAtomic -Path $Documents.RequestPath -Value $Request

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 (Get-VcmSha256 -Path $Documents.RequestPath) `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*JSON array*"
    }

    It "rejects output paths that would overwrite the request" {
        $DocumentsDirectory = Join-Path $TestRoot "documents"
        $Documents = New-TestOperatorDocuments -Directory $DocumentsDirectory
        $CollisionRequest = Join-Path $DocumentsDirectory "result.json"
        Copy-Item -LiteralPath $Documents.RequestPath -Destination $CollisionRequest

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $CollisionRequest `
                -RequestSha256 (Get-VcmSha256 -Path $CollisionRequest) `
                -OutputDirectory $DocumentsDirectory `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*cannot overwrite*"
    }

    It "rejects cross-project confirmation before child execution" {
        $Documents = New-TestOperatorDocuments -Directory (Join-Path $TestRoot "documents")
        $Request = Read-VcmJsonFile -Path $Documents.RequestPath
        $Request.confirm_community_id = 60805374
        Write-VcmJsonAtomic -Path $Documents.RequestPath -Value $Request
        $RequestSha = Get-VcmSha256 -Path $Documents.RequestPath

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 $RequestSha `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*confirmations do not match*"
    }

    It "blocks apply mode in CI before a provider child can start" {
        $env:CI = "true"
        $Documents = New-TestOperatorDocuments `
            -Directory (Join-Path $TestRoot "documents") `
            -Mode "apply" `
            -ProviderMutation $true `
            -OperationClass "ambiguous_mutation" `
            -OperationCount 1

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 $Documents.RequestSha `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot `
                -EnableProviderWrites
        } | Should -Throw "*prohibited in CI*"
        (Test-Path -LiteralPath (Join-Path $OutputDir "stdout.log")) | Should -BeFalse
    }

    It "rejects safe-read manifests outside the explicit CLI allowlist" {
        $Documents = New-TestOperatorDocuments `
            -Directory (Join-Path $TestRoot "documents") `
            -Mode "dry-run" `
            -Arguments @("vk", "login")

        {
            Invoke-VcmOperatorRequest `
                -RequestPath $Documents.RequestPath `
                -RequestSha256 $Documents.RequestSha `
                -OutputDirectory $OutputDir `
                -RepositoryRoot $RepoRoot
        } | Should -Throw "*safe-read allowlist*"
    }

    It "fails every retired wrapper through the reviewed registry" {
        $RetiredPath = Join-Path $RepoRoot "scripts\run-vk-shorts-reset.ps1"
        {
            Stop-VcmRetiredWrapper -WrapperPath $RetiredPath -RepositoryRoot $RepoRoot
        } | Should -Throw "*is retired by Wave 5*"
    }
}
