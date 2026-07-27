[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$NoOpen,
    [string]$ReviewedDryRunBundle,
    [int]$ExpectedCount = 111,
    [string]$Account = "legendary-poet",
    [int]$Community = 235216998
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
$Handoffs = Join-Path $Repo "data\handoffs"
$CurrentPolicy = Join-Path $Repo "content\policies\vk-editorial-policy-20260727.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempRunDir = Join-Path ([System.IO.Path]::GetTempPath()) "video-channel-manager\vk-description-reviewed-$Stamp"
$ReviewedManifest = Join-Path $TempRunDir "manifest.json"
$ReviewedPlan = Join-Path $TempRunDir "reviewed-plan.json"
$ReviewedReport = Join-Path $TempRunDir "reviewed-plan.md"
$ReviewedHtml = Join-Path $TempRunDir "reviewed-plan.html"
$ReviewedSnapshot = Join-Path $TempRunDir "00-source-vk-snapshot.json"
$ReviewedPolicy = Join-Path $TempRunDir "editorial-policy.json"

function Expand-BundleEntry {
    param(
        [Parameter(Mandatory)]
        [string]$Bundle,
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($Bundle)
    try {
        $Entry = $Archive.Entries |
            Where-Object { [System.IO.Path]::GetFileName($_.FullName) -ceq $Name } |
            Select-Object -First 1
        if ($null -eq $Entry) {
            throw "В проверенном ZIP не найден обязательный файл: $Name"
        }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
            $Entry,
            $Destination,
            $true
        )
    }
    finally {
        $Archive.Dispose()
    }
}

function Get-ManifestFile {
    param(
        [Parameter(Mandatory)]
        [object]$Manifest,
        [Parameter(Mandatory)]
        [string]$Name
    )

    return @(
        $Manifest.files |
        Where-Object { [string]$_.name -ceq $Name }
    ) | Select-Object -First 1
}

function Assert-ManifestFile {
    param(
        [Parameter(Mandatory)]
        [object]$Manifest,
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$Path
    )

    $Record = Get-ManifestFile -Manifest $Manifest -Name $Name
    if ($null -eq $Record) {
        throw "manifest.json не содержит $Name."
    }
    $Item = Get-Item -LiteralPath $Path
    if ([long]$Record.size_bytes -ne [long]$Item.Length) {
        throw "Размер $Name не совпадает с manifest.json."
    }
    $ActualSha = "sha256:$((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant())"
    if ($ActualSha -cne [string]$Record.sha256) {
        throw "SHA-256 $Name не совпадает с manifest.json."
    }
}

try {
    if (-not $Execute) {
        throw "Этот helper выполняет только ранее проверенный ZIP. Добавьте явный флаг -Execute."
    }

    Set-Location -LiteralPath $Repo
    New-Item -ItemType Directory -Path $TempRunDir -Force | Out-Null

    if ([string]::IsNullOrWhiteSpace($ReviewedDryRunBundle)) {
        $LatestReviewedBundle = Get-ChildItem `
            -LiteralPath $Handoffs `
            -File `
            -Filter "vk-description-wave-dry-run-*.zip" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -eq $LatestReviewedBundle) {
            throw "Не найден проверенный ZIP description dry-run."
        }
        $ReviewedDryRunBundle = $LatestReviewedBundle.FullName
    }

    $ResolvedBundle = (Resolve-Path -LiteralPath $ReviewedDryRunBundle).Path
    Expand-BundleEntry -Bundle $ResolvedBundle -Name "manifest.json" -Destination $ReviewedManifest
    Expand-BundleEntry -Bundle $ResolvedBundle -Name "plan.json" -Destination $ReviewedPlan
    Expand-BundleEntry -Bundle $ResolvedBundle -Name "plan-review.md" -Destination $ReviewedReport
    Expand-BundleEntry -Bundle $ResolvedBundle -Name "plan-review.html" -Destination $ReviewedHtml
    Expand-BundleEntry -Bundle $ResolvedBundle -Name "00-source-vk-snapshot.json" -Destination $ReviewedSnapshot
    Expand-BundleEntry -Bundle $ResolvedBundle -Name "editorial-policy.json" -Destination $ReviewedPolicy

    $Manifest = Get-Content -LiteralPath $ReviewedManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $PlanJson = Get-Content -LiteralPath $ReviewedPlan -Raw -Encoding UTF8 | ConvertFrom-Json
    $SnapshotJson = Get-Content -LiteralPath $ReviewedSnapshot -Raw -Encoding UTF8 | ConvertFrom-Json

    foreach ($Pair in @(
        @("plan.json", $ReviewedPlan),
        @("plan-review.md", $ReviewedReport),
        @("plan-review.html", $ReviewedHtml),
        @("00-source-vk-snapshot.json", $ReviewedSnapshot),
        @("editorial-policy.json", $ReviewedPolicy)
    )) {
        Assert-ManifestFile -Manifest $Manifest -Name $Pair[0] -Path $Pair[1]
    }

    if ([string]$Manifest.status -ne "dry_run_completed" -or
        [string]$Manifest.mode -ne "dry-run" -or
        [string]$Manifest.component_scope -ne "descriptions_only") {
        throw "Выбранный ZIP не является завершённым descriptions-only dry-run."
    }
    if ([int]$Manifest.community_id -ne $Community) {
        throw "Dry-run ZIP относится к другому VK-сообществу."
    }
    if ([int]$Manifest.ready -ne $ExpectedCount -or
        [int]$Manifest.already_applied -ne 0 -or
        [int]$Manifest.conflicts -ne 0) {
        throw "Ожидался dry-run ready=$ExpectedCount, already_applied=0, conflicts=0."
    }
    if ([string]$Manifest.plan_sha256 -cne [string]$PlanJson.plan_sha256) {
        throw "Plan SHA в manifest не совпадает с plan.json."
    }

    if ([string]$PlanJson.operation_scope -ne "editorial_only" -or
        [string]$PlanJson.component_scope -ne "descriptions_only") {
        throw "План не является descriptions-only editorial plan."
    }
    if ([int]$PlanJson.target_community_id -ne $Community) {
        throw "План относится к другому VK-сообществу."
    }
    if ([string]$PlanJson.target_snapshot_id -cne [string]$SnapshotJson.snapshot_id) {
        throw "План относится к другому source snapshot."
    }
    if ([int]$PlanJson.summary.total_operations -ne $ExpectedCount -or
        [int]$PlanJson.summary.descriptions_to_update -ne $ExpectedCount -or
        [int]$PlanJson.summary.titles_to_update -ne 0 -or
        [int]$PlanJson.summary.albums_to_rename -ne 0 -or
        [int]$PlanJson.summary.placements_to_add -ne 0 -or
        [int]$PlanJson.summary.placements_to_remove -ne 0 -or
        [int]$PlanJson.summary.videos_to_delete -ne 0 -or
        [int]$PlanJson.summary.review_only -ne 0) {
        throw "План содержит неожиданный scope или количество операций."
    }
    if (@($PlanJson.album_title_operations).Count -ne 0) {
        throw "План содержит album operations."
    }

    $Operations = @($PlanJson.video_text_operations)
    if ($Operations.Count -ne $ExpectedCount) {
        throw "Количество video operations не совпало с ожидаемым."
    }
    $DuplicateIds = @(
        $Operations |
        Group-Object target_video_id |
        Where-Object { $_.Count -gt 1 }
    )
    if ($DuplicateIds.Count -gt 0) {
        throw "План содержит повторяющиеся video IDs."
    }
    $UnsafeOperations = @(
        $Operations |
        Where-Object {
            [string]$_.before_title -cne [string]$_.after_title -or
            [string]$_.before_title_sha256 -cne [string]$_.after_title_sha256 -or
            [bool]$_.title_changed -or
            -not [bool]$_.description_changed -or
            -not [bool]$_.semantic_body_preserved -or
            [string]::IsNullOrWhiteSpace([string]$_.semantic_body_sha256) -or
            @($_.change_reasons).Count -eq 0
        }
    )
    if ($UnsafeOperations.Count -gt 0) {
        throw "План содержит скрытое изменение названия или описание без semantic-body защиты."
    }

    $CurrentPolicySha = "sha256:$((Get-FileHash -LiteralPath $CurrentPolicy -Algorithm SHA256).Hash.ToLowerInvariant())"
    $ReviewedPolicySha = "sha256:$((Get-FileHash -LiteralPath $ReviewedPolicy -Algorithm SHA256).Hash.ToLowerInvariant())"
    if ($CurrentPolicySha -cne $ReviewedPolicySha) {
        throw "Текущая редакционная политика отличается от проверенной политики из ZIP."
    }

    Write-Host "" 
    Write-Host "ПРОВЕРЕННЫЙ DESCRIPTION-ПЛАН ДОПУЩЕН К EXECUTE" -ForegroundColor Green
    Write-Host "  ZIP:             $ResolvedBundle"
    Write-Host "  operations:      $($Operations.Count)"
    Write-Host "  plan SHA-256:    $($PlanJson.plan_sha256)"
    Write-Host "  video coverage:  $($PlanJson.target_video_ids_sha256)"
    Write-Host "  memberships:     $($PlanJson.initial_memberships_sha256)"
    Write-Host ""

    $InvokeArguments = @(
        "-File",
        (Join-Path $PSScriptRoot "Invoke-VkDescriptionWave.ps1"),
        "-Execute",
        "-Plan",
        $ReviewedPlan,
        "-SourceSnapshot",
        $ReviewedSnapshot,
        "-Account",
        $Account,
        "-Community",
        [string]$Community
    )
    if ($NoOpen) {
        $InvokeArguments += "-NoOpen"
    }

    & pwsh @InvokeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Description-wave wrapper завершился с кодом $LASTEXITCODE."
    }
}
finally {
    if (Test-Path -LiteralPath $TempRunDir) {
        Remove-Item -LiteralPath $TempRunDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
