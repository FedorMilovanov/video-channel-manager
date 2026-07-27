[CmdletBinding()]
param(
    [switch]$NoOpen,
    [string]$SourceBundle,
    [string]$SourceSnapshot,
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

$ExpectedTitles = [ordered]@{
    "-235216998_456239022" = "我还从未如此疲惫 ⚡ Китайская Версия «Я Усталым Таким Ещё Не Был» ⚡ Сергей Есенин"
    "-235216998_456239096" = "Шабаш ⚡ АЛИСА Cover"
    "-235216998_456239101" = "Внимая Ужасам Войны... ⚡ Николай Некрасов"
}

function Expand-SourceSnapshot {
    param(
        [Parameter(Mandatory)]
        [string]$Bundle,
        [Parameter(Mandatory)]
        [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($Bundle)
    try {
        $PreferredNames = @(
            "00-source-vk-snapshot.json",
            "04-final-vk-snapshot.json"
        )
        $Entry = $null
        foreach ($Name in $PreferredNames) {
            $Entry = $Archive.Entries |
                Where-Object { [System.IO.Path]::GetFileName($_.FullName) -eq $Name } |
                Select-Object -First 1
            if ($null -ne $Entry) {
                break
            }
        }
        if ($null -eq $Entry) {
            throw "В ZIP не найден исходный или финальный VK snapshot: $Bundle"
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

try {
    Set-Location -LiteralPath $Repo
    New-Item -ItemType Directory -Path $Reports -Force | Out-Null
    New-Item -ItemType Directory -Path $TempRunDir -Force | Out-Null

    if (-not (Test-Path -LiteralPath $Policy -PathType Leaf)) {
        throw "Не найдена редакционная политика: $Policy"
    }

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
        Expand-SourceSnapshot `
            -Bundle $ResolvedBundle `
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

    if ([string]$PlanJson.component_scope -ne "titles_only") {
        throw "План не является titles_only."
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
            [bool]$Operation.description_changed) {
            throw "Операция пытается изменить описание: $VideoId"
        }
        if (-not [bool]$Operation.semantic_title_labels_preserved) {
            throw "Операция меняет смысловой ярлык названия: $VideoId"
        }
    }

    Write-Host "" 
    Write-Host "КОСМЕТИЧЕСКИЙ ПЛАН ПРОВЕРЕН" -ForegroundColor Green
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
    if ($NoOpen) {
        $InvokeArguments += "-NoOpen"
    }

    & pwsh @InvokeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Title-wave dry-run wrapper завершился с кодом $LASTEXITCODE."
    }
}
finally {
    if (Test-Path -LiteralPath $TempRunDir) {
        Remove-Item -LiteralPath $TempRunDir -Recurse -Force
    }
}
