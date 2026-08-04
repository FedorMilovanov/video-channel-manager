Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:OperatorRequestSchema = "video-manager.operator-request"
$script:OperatorManifestSchema = "video-manager.operator-manifest"
$script:WrapperRegistrySchema = "video-manager.powershell-wrapper-registry"
$script:OperatorSchemaVersion = 1

function Get-VcmUtf8NoBomEncoding {
    return New-Object System.Text.UTF8Encoding($false)
}

function Write-VcmUtf8Text {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Text
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Text, (Get-VcmUtf8NoBomEncoding))
}

function Write-VcmJsonAtomic {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [object]$Value
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $parent = Split-Path -Parent $fullPath
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = Join-Path $parent (".{0}.{1}.{2}.tmp" -f ([System.IO.Path]::GetFileName($fullPath)), $PID, [guid]::NewGuid().ToString("N"))
    $json = ($Value | ConvertTo-Json -Depth 64 -Compress) + [Environment]::NewLine
    try {
        Write-VcmUtf8Text -Path $temporary -Text $json
        if ([System.IO.File]::Exists($fullPath)) {
            [System.IO.File]::Delete($fullPath)
        }
        [System.IO.File]::Move($temporary, $fullPath)
    }
    finally {
        if ([System.IO.File]::Exists($temporary)) {
            [System.IO.File]::Delete($temporary)
        }
    }
}

function Read-VcmJsonFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "JSON file does not exist: $Path"
    }
    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "Invalid JSON file '$Path': $($_.Exception.Message)"
    }
}

function Get-VcmSha256 {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Cannot hash missing file: $Path"
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-VcmCanonicalTextSha256 {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Cannot hash missing text file: $Path"
    }
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    $normalized = $text.Replace("`r`n", "`n").Replace("`r", "`n")
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $algorithm.ComputeHash($bytes)
    }
    finally {
        $algorithm.Dispose()
    }
    return (($hash | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Get-VcmRepositoryRoot {
    [CmdletBinding()]
    param(
        [string]$StartPath = $PSScriptRoot
    )

    $candidate = Get-Item -LiteralPath $StartPath -ErrorAction Stop
    if (-not $candidate.PSIsContainer) {
        $candidate = $candidate.Directory
    }
    while ($null -ne $candidate) {
        $pyproject = Join-Path $candidate.FullName "pyproject.toml"
        $source = Join-Path $candidate.FullName "src\video_channel_manager"
        if ((Test-Path -LiteralPath $pyproject -PathType Leaf) -and (Test-Path -LiteralPath $source -PathType Container)) {
            return $candidate.FullName
        }
        $candidate = $candidate.Parent
    }
    throw "Cannot resolve repository root from '$StartPath'."
}

function Resolve-VcmExactPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot,

        [switch]$RequireFile,
        [switch]$RequireDirectory
    )

    if ([System.Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path)) {
        throw "Wildcards are prohibited in exact operator paths: $Path"
    }
    $combined = if ([System.IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $RepositoryRoot $Path }
    $resolved = [System.IO.Path]::GetFullPath($combined)
    if ($RequireFile -and -not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "Required file does not exist: $resolved"
    }
    if ($RequireDirectory -and -not (Test-Path -LiteralPath $resolved -PathType Container)) {
        throw "Required directory does not exist: $resolved"
    }
    return $resolved
}

function Get-VcmRepositoryRelativePath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot
    )

    $root = [System.IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $full = [System.IO.Path]::GetFullPath($Path)
    $prefix = $root + [System.IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the repository root: $full"
    }
    return $full.Substring($prefix.Length).Replace("\", "/")
}

function Get-VcmWrapperRegistry {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot
    )

    $path = Join-Path $RepositoryRoot "scripts\operator\powershell-wrappers.json"
    $registry = Read-VcmJsonFile -Path $path
    if ($registry.schema_name -ne $script:WrapperRegistrySchema -or [int]$registry.schema_version -ne 1) {
        throw "Unsupported PowerShell wrapper registry schema."
    }
    $seen = @{}
    foreach ($entry in @($registry.wrappers)) {
        $normalized = ([string]$entry.path).Replace("\", "/")
        if (-not $normalized -or $seen.ContainsKey($normalized)) {
            throw "PowerShell wrapper registry contains a blank or duplicate path: $normalized"
        }
        $seen[$normalized] = $true
    }
    return $registry
}

function Stop-VcmRetiredWrapper {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$WrapperPath,

        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot
    )

    $relative = Get-VcmRepositoryRelativePath -Path $WrapperPath -RepositoryRoot $RepositoryRoot
    $registry = Get-VcmWrapperRegistry -RepositoryRoot $RepositoryRoot
    $entry = @($registry.wrappers | Where-Object { ([string]$_.path).Replace("\", "/") -eq $relative })
    if ($entry.Count -ne 1) {
        throw "Retired wrapper is not uniquely registered: $relative"
    }
    if ([string]$entry[0].status -ne "retired") {
        throw "Retired-wrapper guard used by a non-retired entry: $relative"
    }
    $actual = Get-VcmCanonicalTextSha256 -Path $WrapperPath
    if ([string]$entry[0].sha256 -ne $actual) {
        throw "Retired wrapper digest differs from the reviewed registry: $relative"
    }
    throw "PowerShell wrapper '$relative' is retired by Wave 5 and cannot execute. Use scripts/operator/Invoke-VideoManager.ps1 with an exact reviewed request and manifest."
}

function ConvertTo-VcmNativeArgument {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$Value
    )

    if ($Value.Length -eq 0) {
        return '""'
    }
    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes += 1
            continue
        }
        if ($character -eq '"') {
            [void]$builder.Append(('\' * (($backslashes * 2) + 1)))
            [void]$builder.Append('"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append(('\' * $backslashes))
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append(('\' * ($backslashes * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Protect-VcmArguments {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    $protected = New-Object System.Collections.Generic.List[string]
    $redactNext = $false
    foreach ($argument in $ArgumentList) {
        if ($redactNext) {
            $protected.Add("[REDACTED]")
            $redactNext = $false
            continue
        }
        $lower = $argument.ToLowerInvariant()
        if ($lower -match '(token|secret|password|authorization|upload[-_]?url)') {
            if ($argument.Contains("=")) {
                $protected.Add(($argument.Split('=', 2)[0] + "=[REDACTED]"))
            }
            else {
                $protected.Add($argument)
                $redactNext = $true
            }
            continue
        }
        $protected.Add($argument)
    }
    return $protected.ToArray()
}

function Invoke-VcmNativeProcess {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$ArgumentList = @(),

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$StdoutPath,

        [Parameter(Mandatory = $true)]
        [string]$StderrPath
    )

    $startedAt = [DateTime]::UtcNow
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $FilePath
    $info.Arguments = (($ArgumentList | ForEach-Object { ConvertTo-VcmNativeArgument -Value ([string]$_) }) -join " ")
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = Get-VcmUtf8NoBomEncoding
    $info.StandardErrorEncoding = Get-VcmUtf8NoBomEncoding
    $info.EnvironmentVariables["PYTHONUTF8"] = "1"
    $info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        if (-not $process.Start()) {
            throw "Native process did not start: $FilePath"
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        Write-VcmUtf8Text -Path $StdoutPath -Text $stdout
        Write-VcmUtf8Text -Path $StderrPath -Text $stderr
        $finishedAt = [DateTime]::UtcNow
        return [pscustomobject]@{
            file_path = $FilePath
            arguments = @(Protect-VcmArguments -ArgumentList $ArgumentList)
            started_at = $startedAt.ToString("o")
            finished_at = $finishedAt.ToString("o")
            duration_ms = [int][Math]::Round(($finishedAt - $startedAt).TotalMilliseconds)
            exit_code = [int]$process.ExitCode
            stdout_path = [System.IO.Path]::GetFullPath($StdoutPath)
            stderr_path = [System.IO.Path]::GetFullPath($StderrPath)
            stdout_text = $stdout
            stderr_text = $stderr
        }
    }
    finally {
        $process.Dispose()
    }
}

function Test-VcmCiEnvironment {
    return (
        $env:CI -eq "true" -or
        $env:CI -eq "1" -or
        $env:GITHUB_ACTIONS -eq "true" -or
        $env:TF_BUILD -eq "True"
    )
}

function Resolve-VcmPython {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot,

        [string]$ExplicitPath,

        [Parameter(Mandatory = $true)]
        [string]$ProbeDirectory
    )

    $candidates = New-Object System.Collections.Generic.List[string]
    if ($ExplicitPath) {
        $candidates.Add((Resolve-VcmExactPath -Path $ExplicitPath -RepositoryRoot $RepositoryRoot -RequireFile))
    }
    foreach ($relative in @(".venv\Scripts\python.exe", ".venv/bin/python")) {
        $candidate = Join-Path $RepositoryRoot $relative
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $candidates.Add([System.IO.Path]::GetFullPath($candidate))
        }
    }
    foreach ($commandName in @("python3", "python")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $command -and $command.Source) {
            $candidates.Add([string]$command.Source)
        }
    }

    $seen = @{}
    foreach ($candidate in $candidates) {
        if ($seen.ContainsKey($candidate)) {
            continue
        }
        $seen[$candidate] = $true
        $probeOut = Join-Path $ProbeDirectory ("python-probe-{0}.out" -f ([guid]::NewGuid().ToString("N")))
        $probeErr = Join-Path $ProbeDirectory ("python-probe-{0}.err" -f ([guid]::NewGuid().ToString("N")))
        try {
            $probe = Invoke-VcmNativeProcess -FilePath $candidate -ArgumentList @(
                "-X", "utf8", "-c",
                'import json,sys; print(json.dumps({"major":sys.version_info.major,"minor":sys.version_info.minor,"executable":sys.executable}))'
            ) -WorkingDirectory $RepositoryRoot -StdoutPath $probeOut -StderrPath $probeErr
            if ($probe.exit_code -ne 0) {
                continue
            }
            $metadata = $probe.stdout_text | ConvertFrom-Json
            $version = "{0}.{1}" -f [int]$metadata.major, [int]$metadata.minor
            if ($version -notin @("3.11", "3.12", "3.13")) {
                continue
            }
            return [pscustomobject]@{
                path = [System.IO.Path]::GetFullPath([string]$metadata.executable)
                version = $version
            }
        }
        catch {
            continue
        }
    }
    throw "No supported Python 3.11, 3.12, or 3.13 interpreter was resolved."
}

function Assert-VcmProjectBinding {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$Manifest,

        [Parameter(Mandatory = $true)]
        [object]$Request
    )

    $projects = @{
        "legendary-poet" = @{ community_id = 235216998; owner_id = -235216998 }
        "lord-god-strength" = @{ community_id = 60805374; owner_id = -60805374 }
    }
    $projectKey = [string]$Manifest.project_key
    if (-not $projects.ContainsKey($projectKey)) {
        throw "Unknown operator project_key: $projectKey"
    }
    $expected = $projects[$projectKey]
    if ([int64]$Manifest.community_id -ne [int64]$expected.community_id -or [int64]$Manifest.owner_id -ne [int64]$expected.owner_id) {
        throw "Manifest project/community/owner identity is inconsistent for '$projectKey'."
    }
    if (
        [string]$Request.confirm_project_key -ne $projectKey -or
        [int64]$Request.confirm_community_id -ne [int64]$expected.community_id -or
        [int64]$Request.confirm_owner_id -ne [int64]$expected.owner_id
    ) {
        throw "Operator project/community/owner confirmations do not match the manifest."
    }
}

function Test-VcmSafeCliArguments {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    if ($Arguments.Count -eq 0) {
        return $false
    }
    $first = $Arguments[0].ToLowerInvariant()
    $second = if ($Arguments.Count -gt 1) { $Arguments[1].ToLowerInvariant() } else { "" }
    if ($first -in @("version", "doctor")) {
        return $true
    }
    $prefix = "$first $second"
    return $prefix -in @(
        "plan validate",
        "plan preview",
        "local scan",
        "schema export",
        "example export",
        "vk accounts",
        "vk communities",
        "vk scan"
    )
}

function Invoke-VcmOperatorRequest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RequestPath,

        [Parameter(Mandatory = $true)]
        [ValidatePattern('^[0-9a-fA-F]{64}$')]
        [string]$RequestSha256,

        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,

        [string]$PythonPath,
        [switch]$EnableProviderWrites,
        [string]$RepositoryRoot = (Get-VcmRepositoryRoot -StartPath $PSScriptRoot)
    )

    $root = [System.IO.Path]::GetFullPath($RepositoryRoot)
    $output = Resolve-VcmExactPath -Path $OutputDirectory -RepositoryRoot $root
    [System.IO.Directory]::CreateDirectory($output) | Out-Null
    $preflightPath = Join-Path $output "preflight-summary.json"
    $resultPath = Join-Path $output "result.json"
    $stdoutPath = Join-Path $output "stdout.log"
    $stderrPath = Join-Path $output "stderr.log"

    $requestFile = Resolve-VcmExactPath -Path $RequestPath -RepositoryRoot $root -RequireFile
    $actualRequestSha = Get-VcmSha256 -Path $requestFile
    if ($actualRequestSha -ne $RequestSha256.ToLowerInvariant()) {
        throw "Operator request SHA-256 mismatch."
    }
    $request = Read-VcmJsonFile -Path $requestFile
    if ($request.schema_name -ne $script:OperatorRequestSchema -or [int]$request.schema_version -ne 1) {
        throw "Unsupported operator request schema."
    }
    $mode = ([string]$request.mode).ToLowerInvariant()
    if ($mode -notin @("plan", "dry-run", "apply", "reconcile")) {
        throw "Unsupported operator mode: $mode"
    }

    $manifestFile = Resolve-VcmExactPath -Path ([string]$request.manifest_path) -RepositoryRoot $root -RequireFile
    $manifestSha = Get-VcmSha256 -Path $manifestFile
    if (
        $manifestSha -ne ([string]$request.manifest_sha256).ToLowerInvariant() -or
        $manifestSha -ne ([string]$request.confirm_manifest_sha256).ToLowerInvariant()
    ) {
        throw "Operator manifest SHA-256 confirmation mismatch."
    }
    $manifest = Read-VcmJsonFile -Path $manifestFile
    if ($manifest.schema_name -ne $script:OperatorManifestSchema -or [int]$manifest.schema_version -ne 1) {
        throw "Unsupported operator manifest schema."
    }
    Assert-VcmProjectBinding -Manifest $manifest -Request $request
    if ([string]$manifest.source_snapshot_id -ne [string]$request.confirm_source_snapshot_id) {
        throw "Operator source snapshot confirmation mismatch."
    }
    if ([int64]$manifest.operation_count -ne [int64]$request.confirm_operation_count) {
        throw "Operator operation-count confirmation mismatch."
    }
    if ([int64]$manifest.operation_count -lt 0) {
        throw "Operator manifest operation_count cannot be negative."
    }
    if ([string]$manifest.entrypoint_id -ne "video-manager-cli") {
        throw "Unsupported operator entrypoint_id."
    }
    if ($manifest.provider_mutation -isnot [bool]) {
        throw "Manifest provider_mutation must be an exact boolean."
    }
    $operationClass = [string]$manifest.operation_class
    if ($operationClass -notin @("safe_read", "ambiguous_mutation")) {
        throw "Unsupported operation_class: $operationClass"
    }
    $arguments = @($manifest.arguments | ForEach-Object { [string]$_ })

    if ([bool]$manifest.provider_mutation) {
        if ($mode -ne "apply" -or $operationClass -ne "ambiguous_mutation") {
            throw "Provider mutation manifests require apply mode and ambiguous_mutation classification."
        }
        if (Test-VcmCiEnvironment) {
            throw "Provider mutations are prohibited in CI."
        }
        if (-not $EnableProviderWrites) {
            throw "Apply mode requires the explicit -EnableProviderWrites switch."
        }
        if ([int64]$manifest.operation_count -le 0) {
            throw "Apply mode requires a positive operation_count."
        }
    }
    else {
        if ($operationClass -ne "safe_read") {
            throw "Non-mutating manifests must use safe_read classification."
        }
        if (-not (Test-VcmSafeCliArguments -Arguments $arguments)) {
            throw "The CLI arguments are not in the supported safe-read allowlist."
        }
        if ($mode -eq "apply") {
            throw "Apply mode cannot be used with a non-mutating manifest."
        }
    }

    $preflight = [ordered]@{
        schema_name = "video-manager.operator-preflight"
        schema_version = 1
        status = "passed"
        observed_at = [DateTime]::UtcNow.ToString("o")
        mode = $mode
        project_key = [string]$manifest.project_key
        community_id = [int64]$manifest.community_id
        owner_id = [int64]$manifest.owner_id
        source_snapshot_id = [string]$manifest.source_snapshot_id
        operation_count = [int64]$manifest.operation_count
        operation_class = $operationClass
        provider_mutation = [bool]$manifest.provider_mutation
        request_path = $requestFile
        request_sha256 = $actualRequestSha
        manifest_path = $manifestFile
        manifest_sha256 = $manifestSha
        output_directory = [System.IO.Path]::GetFullPath($output)
    }
    Write-VcmJsonAtomic -Path $preflightPath -Value $preflight

    if ($mode -eq "plan") {
        $planned = [ordered]@{
            schema_name = "video-manager.operator-result"
            schema_version = 1
            status = "planned"
            exit_code = 0
            retry_safe = $false
            unknown_requires_reconciliation = $false
            mode = $mode
            project_key = [string]$manifest.project_key
            request_sha256 = $actualRequestSha
            manifest_sha256 = $manifestSha
            preflight_path = $preflightPath
            result_path = $resultPath
            child = $null
        }
        Write-VcmJsonAtomic -Path $resultPath -Value $planned
        return [pscustomobject]$planned
    }

    $python = Resolve-VcmPython -RepositoryRoot $root -ExplicitPath $PythonPath -ProbeDirectory $output
    $child = Invoke-VcmNativeProcess -FilePath $python.path -ArgumentList (@("-X", "utf8", "-m", "video_channel_manager.cli.app") + $arguments) -WorkingDirectory $root -StdoutPath $stdoutPath -StderrPath $stderrPath
    $status = if ($child.exit_code -eq 0) {
        "succeeded"
    }
    elseif ($operationClass -eq "ambiguous_mutation") {
        "unknown_requires_reconciliation"
    }
    else {
        "failed"
    }
    $result = [ordered]@{
        schema_name = "video-manager.operator-result"
        schema_version = 1
        status = $status
        exit_code = [int]$child.exit_code
        retry_safe = ($operationClass -eq "safe_read" -and $child.exit_code -ne 0)
        unknown_requires_reconciliation = ($status -eq "unknown_requires_reconciliation")
        mode = $mode
        project_key = [string]$manifest.project_key
        request_sha256 = $actualRequestSha
        manifest_sha256 = $manifestSha
        preflight_path = $preflightPath
        result_path = $resultPath
        child = [ordered]@{
            file_path = $child.file_path
            arguments = @($child.arguments)
            started_at = $child.started_at
            finished_at = $child.finished_at
            duration_ms = $child.duration_ms
            stdout_path = $child.stdout_path
            stderr_path = $child.stderr_path
        }
    }
    Write-VcmJsonAtomic -Path $resultPath -Value $result
    return [pscustomobject]$result
}

Export-ModuleMember -Function @(
    "Get-VcmCanonicalTextSha256",
    "Get-VcmRepositoryRoot",
    "Get-VcmSha256",
    "Get-VcmWrapperRegistry",
    "Invoke-VcmNativeProcess",
    "Invoke-VcmOperatorRequest",
    "Read-VcmJsonFile",
    "Resolve-VcmExactPath",
    "Resolve-VcmPython",
    "Stop-VcmRetiredWrapper",
    "Test-VcmCiEnvironment",
    "Test-VcmSafeCliArguments",
    "Write-VcmJsonAtomic",
    "Write-VcmUtf8Text"
)
