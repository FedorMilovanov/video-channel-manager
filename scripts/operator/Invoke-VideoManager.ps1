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
    [ValidateRange(1, 86400)]
    [int]$TimeoutSeconds = 900
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ModulePath = Join-Path $PSScriptRoot "VideoManager.Operator.psm1"
Import-Module -Name $ModulePath -Force -ErrorAction Stop

$RepositoryRoot = Get-VcmRepositoryRoot -StartPath $PSScriptRoot
$OutputPath = Resolve-VcmExactPath -Path $OutputDirectory -RepositoryRoot $RepositoryRoot
[System.IO.Directory]::CreateDirectory($OutputPath) | Out-Null
$ResultPath = Join-Path $OutputPath "result.json"

try {
    $Result = Invoke-VcmOperatorRequest `
        -RequestPath $RequestPath `
        -RequestSha256 $RequestSha256 `
        -OutputDirectory $OutputPath `
        -PythonPath $PythonPath `
        -EnableProviderWrites:$EnableProviderWrites `
        -TimeoutSeconds $TimeoutSeconds `
        -RepositoryRoot $RepositoryRoot

    Write-Host ("Operator status: {0}. Structured result: {1}" -f $Result.status, $ResultPath)
    exit [int]$Result.exit_code
}
catch {
    $Failure = [ordered]@{
        schema_name = "video-manager.operator-result"
        schema_version = 1
        status = "rejected"
        exit_code = 2
        retry_safe = $false
        unknown_requires_reconciliation = $false
        observed_at = [DateTime]::UtcNow.ToString("o")
        error_type = $_.Exception.GetType().FullName
        error_message = $_.Exception.Message
        result_path = [System.IO.Path]::GetFullPath($ResultPath)
    }
    Write-VcmJsonAtomic -Path $ResultPath -Value $Failure
    Write-Error ("Operator request rejected. Structured result: {0}" -f $ResultPath)
    exit 2
}
