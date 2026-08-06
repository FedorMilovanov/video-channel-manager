[CmdletBinding()]
param(
    [ValidateSet("plan", "reconcile", "apply")]
    [string]$Command,

    [string]$InputPath,
    [string]$OutputPath,
    [string]$OutputDirectory,
    [string]$AccountAlias = "legendary-poet",
    [string]$ConfirmPlanSha256,
    [switch]$EnableProviderWrites,
    [int]$MinimumFutureSeconds = 600,
    [double]$InterOperationDelaySeconds = 25.0,
    [double]$PostflightDelaySeconds = 3.0,
    [double]$TransientRetryDelaySeconds = 90.0,
    [int]$MaxTransientRetries = 1,
    [int]$MaxPostsPerSurface = 10000,
    [string]$PythonCommand = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-VcmLiteralPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$FieldName
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "$FieldName cannot be blank."
    }
    return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
}

function New-VkPostponedTextCliArguments {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("plan", "reconcile", "apply")]
        [string]$Command,

        [Parameter(Mandatory = $true)]
        [string]$InputPath,

        [string]$OutputPath,
        [string]$OutputDirectory,
        [string]$AccountAlias = "legendary-poet",
        [string]$ConfirmPlanSha256,
        [switch]$EnableProviderWrites,
        [int]$MinimumFutureSeconds = 600,
        [double]$InterOperationDelaySeconds = 25.0,
        [double]$PostflightDelaySeconds = 3.0,
        [double]$TransientRetryDelaySeconds = 90.0,
        [int]$MaxTransientRetries = 1,
        [int]$MaxPostsPerSurface = 10000
    )

    if ([string]::IsNullOrWhiteSpace($AccountAlias)) {
        throw "AccountAlias cannot be blank."
    }
    if ($MaxPostsPerSurface -lt 1) {
        throw "MaxPostsPerSurface must be positive."
    }

    $ResolvedInput = Resolve-VcmLiteralPath -Path $InputPath -FieldName "InputPath"
    $Arguments = @(
        "-m",
        "video_channel_manager.cli.vk_postponed_text",
        $Command,
        $ResolvedInput,
        "--account",
        $AccountAlias,
        "--max-posts-per-surface",
        [string]$MaxPostsPerSurface
    )

    if ($Command -eq "plan" -or $Command -eq "reconcile") {
        if ([string]::IsNullOrWhiteSpace($OutputPath)) {
            throw "OutputPath is required for $Command."
        }
        if (-not [string]::IsNullOrWhiteSpace($OutputDirectory)) {
            throw "OutputDirectory is valid only for apply."
        }
        if ($EnableProviderWrites -or -not [string]::IsNullOrWhiteSpace($ConfirmPlanSha256)) {
            throw "Provider-write confirmation parameters are valid only for apply."
        }
        $Arguments += @("--output", [IO.Path]::GetFullPath($OutputPath))
        return ,$Arguments
    }

    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        throw "OutputDirectory is required for apply."
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
        throw "OutputPath is valid only for plan or reconcile."
    }
    if ([string]::IsNullOrWhiteSpace($ConfirmPlanSha256) -or -not $ConfirmPlanSha256.StartsWith("sha256:")) {
        throw "Apply requires an exact sha256: plan confirmation."
    }
    if (-not $EnableProviderWrites) {
        throw "Apply requires -EnableProviderWrites."
    }
    if ($MinimumFutureSeconds -lt 0 -or $MaxTransientRetries -lt 0) {
        throw "MinimumFutureSeconds and MaxTransientRetries cannot be negative."
    }
    if (
        $InterOperationDelaySeconds -lt 0 -or
        $PostflightDelaySeconds -lt 0 -or
        $TransientRetryDelaySeconds -lt 0
    ) {
        throw "Operation delays cannot be negative."
    }

    $Arguments += @(
        "--output-dir",
        [IO.Path]::GetFullPath($OutputDirectory),
        "--confirm-plan-sha256",
        $ConfirmPlanSha256,
        "--enable-provider-writes",
        "--minimum-future-seconds",
        [string]$MinimumFutureSeconds,
        "--inter-operation-delay-seconds",
        [string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $InterOperationDelaySeconds),
        "--postflight-delay-seconds",
        [string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $PostflightDelaySeconds),
        "--transient-retry-delay-seconds",
        [string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $TransientRetryDelaySeconds),
        "--max-transient-retries",
        [string]$MaxTransientRetries
    )
    return ,$Arguments
}

function Invoke-VcmNativeCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Executable @Arguments | Out-Host
    return [int]$LASTEXITCODE
}

function Invoke-VkPostponedTextEdit {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("plan", "reconcile", "apply")]
        [string]$Command,

        [Parameter(Mandatory = $true)]
        [string]$InputPath,

        [string]$OutputPath,
        [string]$OutputDirectory,
        [string]$AccountAlias = "legendary-poet",
        [string]$ConfirmPlanSha256,
        [switch]$EnableProviderWrites,
        [int]$MinimumFutureSeconds = 600,
        [double]$InterOperationDelaySeconds = 25.0,
        [double]$PostflightDelaySeconds = 3.0,
        [double]$TransientRetryDelaySeconds = 90.0,
        [int]$MaxTransientRetries = 1,
        [int]$MaxPostsPerSurface = 10000,
        [string]$PythonCommand = "python"
    )

    if ([string]::IsNullOrWhiteSpace($PythonCommand)) {
        throw "PythonCommand cannot be blank."
    }

    $Forwarded = @{
        Command = $Command
        InputPath = $InputPath
        OutputPath = $OutputPath
        OutputDirectory = $OutputDirectory
        AccountAlias = $AccountAlias
        ConfirmPlanSha256 = $ConfirmPlanSha256
        EnableProviderWrites = $EnableProviderWrites
        MinimumFutureSeconds = $MinimumFutureSeconds
        InterOperationDelaySeconds = $InterOperationDelaySeconds
        PostflightDelaySeconds = $PostflightDelaySeconds
        TransientRetryDelaySeconds = $TransientRetryDelaySeconds
        MaxTransientRetries = $MaxTransientRetries
        MaxPostsPerSurface = $MaxPostsPerSurface
    }
    $Arguments = New-VkPostponedTextCliArguments @Forwarded
    $ExitCode = Invoke-VcmNativeCommand -Executable $PythonCommand -Arguments $Arguments
    if ($ExitCode -ne 0) {
        throw "VK postponed-text CLI failed with exit code $ExitCode."
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    $Invocation = @{}
    foreach ($Key in $PSBoundParameters.Keys) {
        $Invocation[$Key] = $PSBoundParameters[$Key]
    }
    Invoke-VkPostponedTextEdit @Invocation
}
