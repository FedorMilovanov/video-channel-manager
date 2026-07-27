[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$NoOpen,
    [string]$SourceBundle,
    [string]$SourceSnapshot,
    [string]$ReviewedDryRunBundle,
    [int]$ExpectedCount = 3,
    [string]$Account = "legendary-poet",
    [int]$Community = 235216998
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Repo = Split-Path -Parent $PSScriptRoot
$Reports = Join-Path $Repo "data\reports"
$Handoffs = Join-Path $Repo "data\handoffs"
$Policy = Join-Path $Repo "content\policies\vk-editorial-policy-20260727.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Plan = Join-Path $Reports "vk-editorial-title-cosmetic-$Stamp.json"
$Report = Join-Path $Reports "vk-editorial-title-cosmetic-$Stamp.md"
$TempRunDir = Join-Path ([System.IO.Path]::GetTempPath()) "video-channel-manager\vk-title-cosmetic-$Stamp"
$TemporarySnapshot = Join-Path $TempRunDir "source-vk-snapshot.json"
$ReviewedPlan = Join-Path $TempRunDir "reviewed-plan.json"
$ReviewedReport = Join-Path $TempRunDir "reviewed-plan.md"
$ReviewedManifest = Join-Path $TempRunDir "reviewed-manifest.json"

$ExpectedTitles = [ordered]@{
    "-235216998_456239022" = "我还从未如此疲惫 ⚡ Китайская Версия «Я Усталым Таким Ещё Не Был» ⚡ Сергей Есенин"
    "-235216998_456239096" = "Шабаш ⚡ АЛИСА Cover"
    "-235216998_456239101" = "Внимая Ужасам Войны... ⚡ Николай Некрасов"
}

function Expand-BundleEntry {
    param(
        [Parameter(Mandatory)]
        [string]$Bundle,
        [Parameter(Mandatory)]
        [string[]]$CandidateNames,
        [Parameter(Mandatory)]
        [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($Bundle)
    try {
        $Entry = $null
        foreach ($Name in $CandidateNames) {
            $Entry = $Archive.Entries |
                Where-Object { [System.IO.Path]::GetFileName($_.FullName) -eq $Name } |
                Select-Object -First 1
            if ($null -ne $Entry) {
                break
            }
        }
        if ($null -eq $Entry) {
            throw (
                "В ZIP не найден ни один из обязательных файлов: " +
                ($CandidateNames -join ", ")
            )
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

function Assert-ReviewedBundle {
    param(
        [Parameter(Mandatory)]
        [string]$Bundle
    )

    Expand-BundleEntry `
        -Bundle $Bundle `
        -CandidateNames @("manifest.json") `
        -Destination $ReviewedManifest
    Expand-BundleEntry `
        -Bundle $Bundle `
        -CandidateNames @("plan.json") `
        -Destination $ReviewedPlan
    Expand-BundleEntry `
        -Bundle $Bundle `
        -CandidateNames @("plan-review.md") `
        -Destination $ReviewedReport

    $Manifest = Get-Content -LiteralPath $ReviewedManifest -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $ReviewedPlanJson = Get-Content -LiteralPath $ReviewedPlan -Raw -Encoding UTF8 |
        ConvertFrom-Json

    if ([string]$Manifest.status -ne "dry_run_completed" -or
        [string]$Manifest.mode -ne "dry-run") {
        throw "Выбранный ZIP не является завершённым dry-run."
    }
    if ([int]$Manifest.community_id -ne $Community) {
        throw "Dry-run ZIP относится к другому VK-сообществу."
    }
    if ([int]$Manifest.ready -ne $ExpectedCount -or
        [int]$Manifest.already_applied -ne 0 -or
        [int]$Manifest.conflicts -ne 0) {
        throw (
            "Ожидался dry-run ready=$ExpectedCount, already_applied=0, conflicts=0."
        )
    }
    if ([string]$Manifest.plan_sha256 -cne [string]$ReviewedPlanJson.plan_sha256) {
        throw "Plan SHA в manifest не совпадает с plan.json."
    }

    $ManifestPlan = Get-ManifestFile -Manifest $Manifest -Name "plan.json"
    if ($null -eq $ManifestPlan) {
        throw "manifest.json не содержит plan.json."
    }
    $ActualPlanFileSha = "sha256:$((Get-FileHash -LiteralPath $ReviewedPlan -Algorithm SHA256).Hash.ToLowerInvariant())"
    if ($ActualPlanFileSha -cne [string]$ManifestPlan.sha256) {
        throw "SHA-256 файла plan.json не совпадает с manifest."
    }

    return $ReviewedPlanJson
}

function Assert-CosmeticPlan {
    param(
        [Parameter(Mandatory)]
        [object]$PlanJson
    )

    if ([string]$PlanJson.operation_scope -ne "editorial_only") {
        throw "План не является editorial_only."
    }
    if ([string]$PlanJson.component_scope -ne "titles_only") {
        throw "План не является titles_only."
    }
    if ([int]$PlanJson.target_community_id -ne $Community) {
        throw "План относится к другому VK-сообществу."
    }
    if ([int]$PlanJson.summary.total_operations -ne $ExpectedCount) {
        throw (
            "Ожидалось $ExpectedCount косметических операций, найдено: " +
            "$($PlanJson.summary.total_operations)"
        )
    }
    if ([int]$PlanJson.summary.descriptions_to_update -ne 0 -or
        [int]$PlanJson.summary.albums_to_rename -ne 0 -or
        [int]$PlanJson.summary.placements_to_add -ne 0 -or
        [int]$PlanJson.summary.placements_to_remove -ne 0 -or
        [int]$PlanJson.summary.videos_to_delete -ne 0) {
        throw "Косметический план содержит неразрешённые изменения."
    }

    $Operations = @($PlanJson.video_text_operations)
    $ActualIds = @($Operations | ForEach-Object { [string]$_.target_video_id })
    $ExpectedIds = @($ExpectedTitles.Keys)

    if (@($ActualIds | Where-Object { $_ -notin $ExpectedIds }).Count -gt 0 -or
        @($ExpectedIds | Where-Object { $_ -notin $ActualIds }).Count -gt 0) {
        throw "План содержит неожиданный набор видео."
    }

    foreach ($Operation in $Operations) {
        $VideoId = [string]$Operation.target_video_id
        if ([string]$Operation.after_title -cne [string]$ExpectedTitles[$VideoId]) {
            throw "Не совпало проверенное косметическое название: $VideoId"
        }
        if ([string]$Operation.before_description -cne [string]$Operation.after_description -or
            [string]$Operation.before_description_sha256 -cne
                [string]$Operation.after_description_sha256 -or
            [bool]$Operation.description_changed) {
            throw "Операция пытается изменить описание: $VideoId"
        }
        if (-not [bool]$Operation.semantic_title_labels_preserved) {
            throw "Операция меняет смысловой ярлык названия: $VideoId"
        }
    }

    return $Operations
}

try {
    Set-Location -LiteralPath $Repo
    New-Item -ItemType Directory -Path $Reports -Force | Out-Null
    New-Item -ItemType Directory -Path $TempRunDir -Force | Out-Null

    if (-not (Test-Path -LiteralPath $Policy -PathType Leaf)) {
        throw "Не найдена редакционная политика: $Policy"
    }

    if ($Execute) {
        if ([string]::IsNullOrWhiteSpace($ReviewedDryRunBundle)) {
            $LatestReviewedBundle = Get-ChildItem `
                -LiteralPath $Handoffs `
                -File `
                -Filter "vk-title-wave-dry-run-*.zip" |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            if ($null -eq $LatestReviewedBundle) {
                throw "Не найден проверенный ZIP косметического dry-run."
            }
            $ReviewedDryRunBundle = $LatestReviewedBundle.FullName
        }

        $ResolvedReviewedBundle = (Resolve-Path -LiteralPath $ReviewedDryRunBundle).Path
        $PlanJson = Assert-ReviewedBundle -Bundle $ResolvedReviewedBundle
        $Plan = $ReviewedPlan
        $Report = $ReviewedReport
    }
    else {
        if (-not [string]::IsNullOrWhiteSpace($SourceSnapshot)) {
            $ResolvedSnapshot = (Resolve-Path -LiteralPath $SourceSnapshot).Path
        }
        else {
            if ([string]::IsNullOrWhiteSpace($SourceBundle)) {
                $LatestDescriptionBundle = Get-ChildItem `
                    -LiteralPath $Handoffs `
                    -File `
                    -Filter "vk-description-wave-dry-run-*.zip" |
                    Sort-Object LastWriteTime -Descending |
                    Select-Object -First 1

                if ($null -ne $LatestDescriptionBundle) {
                    $SourceBundle = $LatestDescriptionBundle.FullName
                }
                else {
                    $LatestTitleBundle = Get-ChildItem `
                        -LiteralPath $Handoffs `
                        -File `
                        -Filter "vk-title-wave-apply-*.zip" |
                        Sort-Object LastWriteTime -Descending |
                        Select-Object -First 1
                    if ($null -eq $LatestTitleBundle) {
                        throw "Не найден ZIP dry-run описаний или успешной волны названий."
                    }
                    $SourceBundle = $LatestTitleBundle.FullName
                }
            }

            $ResolvedBundle = (Resolve-Path -LiteralPath $SourceBundle).Path
            Expand-BundleEntry `
                -Bundle $ResolvedBundle `
                -CandidateNames @(
                    "00-source-vk-snapshot.json",
                    "04-final-vk-snapshot.json"
                ) `
                -Destination $TemporarySnapshot
            $ResolvedSnapshot = $TemporarySnapshot
        }

        & py -3.11 -X utf8 .\scripts\build_vk_editorial_title_wave.py `
            "$ResolvedSnapshot" `
            --policy-json "$Policy" `
            --output "$Plan" `
            --report "$Report"

        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось построить косметический title-only план."
        }

        $PlanJson = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 |
            ConvertFrom-Json
    }

    $Operations = Assert-CosmeticPlan -PlanJson $PlanJson

    Write-Host ""
    if ($Execute) {
        Write-Host "ПРОВЕРЕННЫЙ КОСМЕТИЧЕСКИЙ ПЛАН ДОПУЩЕН К EXECUTE" -ForegroundColor Green
    }
    else {
        Write-Host "КОСМЕТИЧЕСКИЙ ПЛАН ПРОВЕРЕН" -ForegroundColor Green
    }
    foreach ($Operation in $Operations) {
        Write-Host "  $($Operation.before_title)" -ForegroundColor DarkGray
        Write-Host "  → $($Operation.after_title)" -ForegroundColor Cyan
    }
    Write-Host ""

    $InvokeArguments = @(
        "-File",
        (Join-Path $PSScriptRoot "Invoke-VkTitleWave.ps1"),
        "-Plan",
        $Plan,
        "-Account",
        $Account,
        "-Community",
        [string]$Community
    )
    if ($Execute) {
        $InvokeArguments += "-Execute"
    }
    if ($NoOpen) {
        $InvokeArguments += "-NoOpen"
    }

    & pwsh @InvokeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Title-wave wrapper завершился с кодом $LASTEXITCODE."
    }
}
finally {
    if (Test-Path -LiteralPath $TempRunDir) {
        Remove-Item -LiteralPath $TempRunDir -Recurse -Force
    }
}
