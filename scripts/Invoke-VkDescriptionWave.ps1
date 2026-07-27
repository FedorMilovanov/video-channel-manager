[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$NoOpen,
    [string]$Plan,
    [string]$SourceSnapshot,
    [string]$SourceBundle,
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
$Exports = Join-Path $Repo "data\exports"
$Handoffs = Join-Path $Repo "data\handoffs"
$PolicyPath = Join-Path $Repo "content\policies\vk-editorial-policy-20260727.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Mode = if ($Execute) { "apply" } else { "dry-run" }
$BundleName = "vk-description-wave-$Mode-$Stamp"
$BundleDir = Join-Path $Handoffs $BundleName
$ZipPath = Join-Path $Handoffs "$BundleName.zip"
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "video-channel-manager"
$TempRunDir = Join-Path $TempRoot $BundleName
$TemporarySnapshot = Join-Path $TempRunDir "source-vk-snapshot.json"

New-Item -ItemType Directory -Path $BundleDir -Force | Out-Null
New-Item -ItemType Directory -Path $TempRunDir -Force | Out-Null

$PreflightLog = Join-Path $BundleDir "01-preflight.txt"
$ApplyLog = Join-Path $BundleDir "02-apply.txt"
$ResultPath = Join-Path $BundleDir "03-result.json"
$FinalSnapshot = Join-Path $BundleDir "04-final-vk-snapshot.json"
$ReadmePath = Join-Path $BundleDir "README.txt"
$ManifestPath = Join-Path $BundleDir "manifest.json"

$RunStatus = "started"
$RunError = $null
$Ready = $null
$AlreadyApplied = $null
$Conflicts = $null
$PlanJson = $null
$ResolvedSourceSnapshot = $null
$ResolvedSourceBundle = $null
$GeneratedPlan = $false

function Get-NormalizedFullPath {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Copy-Artifact {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    $TargetName = if ($Name) { $Name } else { Split-Path -Leaf $Path }
    $Destination = Join-Path $BundleDir $TargetName
    $SourceFullPath = Get-NormalizedFullPath -Path $Path
    $DestinationFullPath = Get-NormalizedFullPath -Path $Destination

    if ([string]::Equals(
        $SourceFullPath,
        $DestinationFullPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        return
    }

    Copy-Item -LiteralPath $SourceFullPath -Destination $DestinationFullPath -Force
}

function Read-PreflightCount {
    param(
        [Parameter(Mandatory)]
        [string]$Text,
        [Parameter(Mandatory)]
        [string]$Label
    )

    $Pattern = "(?m)^\s*" + [regex]::Escape($Label) + ":\s*(\d+)\s*$"
    $Match = [regex]::Match($Text, $Pattern)
    if (-not $Match.Success) {
        throw "Не удалось прочитать '$Label' из live preflight."
    }
    return [int]$Match.Groups[1].Value
}

function Expand-SnapshotFromBundle {
    param(
        [Parameter(Mandatory)]
        [string]$Bundle,
        [Parameter(Mandatory)]
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Bundle -PathType Leaf)) {
        throw "Не найден исходный ZIP: $Bundle"
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($Bundle)
    try {
        $Entry = $Archive.Entries |
            Where-Object {
                [System.IO.Path]::GetFileName($_.FullName) -eq "04-final-vk-snapshot.json"
            } |
            Select-Object -First 1

        if ($null -eq $Entry) {
            throw "В ZIP не найден 04-final-vk-snapshot.json: $Bundle"
        }

        $DestinationDirectory = Split-Path -Parent $Destination
        New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
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

function Write-Bundle {
    $Readme = @"
VK DESCRIPTION WAVE HANDOFF

Статус: $RunStatus
Режим: $Mode
Community: $Community
Ready перед запуском: $Ready
Already applied перед запуском: $AlreadyApplied
Conflicts: $Conflicts
Ошибка: $RunError
Source snapshot: $ResolvedSourceSnapshot
Source bundle: $ResolvedSourceBundle

ОТПРАВЛЯТЬ НУЖНО ТОЛЬКО ОДИН ФАЙЛ:
$ZipPath

Внутри архива автоматически собраны:
- исходный финальный VK snapshot после волны названий;
- подписанный descriptions-only JSON-план;
- короткий Markdown-отчёт;
- удобный HTML с раскрывающимися блоками «До/После»;
- редакционная политика;
- свежий live preflight;
- лог применения и result journal при execute;
- финальный VK snapshot при успешном execute;
- manifest.json с SHA-256 каждого файла.

ВАЖНО:
- default-режим является dry-run и ничего не записывает в VK;
- execute разрешён только с явно переданным ранее проверенным -Plan;
- план блокируется, если меняется содержательная часть хотя бы одного описания;
- snapshot распаковывается во временную папку вне handoff-пакета;
- self-copy артефакта безопасно пропускается.
"@
    Set-Content -LiteralPath $ReadmePath -Value $Readme -Encoding UTF8

    $Files = @(
        Get-ChildItem -LiteralPath $BundleDir -File |
        Where-Object { $_.Name -ne "manifest.json" } |
        Sort-Object Name |
        ForEach-Object {
            $Hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            [ordered]@{
                name = $_.Name
                size_bytes = $_.Length
                sha256 = "sha256:$($Hash.Hash.ToLowerInvariant())"
            }
        }
    )

    $Manifest = [ordered]@{
        schema_name = "video-manager.vk-handoff-bundle"
        schema_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        status = $RunStatus
        mode = $Mode
        component_scope = "descriptions_only"
        community_id = $Community
        ready = $Ready
        already_applied = $AlreadyApplied
        conflicts = $Conflicts
        error = $RunError
        source_snapshot = $ResolvedSourceSnapshot
        source_bundle = $ResolvedSourceBundle
        plan_sha256 = if ($null -ne $PlanJson) {
            [string]$PlanJson.plan_sha256
        }
        else {
            $null
        }
        files = $Files
    }

    $Manifest |
        ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $ManifestPath -Encoding UTF8

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    Compress-Archive `
        -Path (Join-Path $BundleDir "*") `
        -DestinationPath $ZipPath `
        -CompressionLevel Optimal

    Write-Host ""
    Write-Host "ГОТОВ ОДИН ФАЙЛ ДЛЯ ОТПРАВКИ:" -ForegroundColor Green
    Write-Host $ZipPath -ForegroundColor Cyan

    if (-not $NoOpen -and $IsWindows) {
        $Html = Join-Path $BundleDir "plan-review.html"
        if (Test-Path -LiteralPath $Html -PathType Leaf) {
            Start-Process $Html
        }
        Start-Process explorer.exe -ArgumentList "/select,`"$ZipPath`""
    }
}

try {
    Set-Location -LiteralPath $Repo

    if (-not (Test-Path -LiteralPath $PolicyPath -PathType Leaf)) {
        throw "Не найдена редакционная политика: $PolicyPath"
    }

    if ($Execute -and [string]::IsNullOrWhiteSpace($Plan)) {
        throw (
            "Execute требует явно переданный ранее проверенный -Plan. " +
            "Новый план нельзя построить и тут же исполнить."
        )
    }

    if (-not [string]::IsNullOrWhiteSpace($SourceSnapshot)) {
        $ResolvedSourceSnapshot = (Resolve-Path -LiteralPath $SourceSnapshot).Path
    }
    elseif (-not [string]::IsNullOrWhiteSpace($SourceBundle)) {
        $ResolvedSourceBundle = (Resolve-Path -LiteralPath $SourceBundle).Path
        Expand-SnapshotFromBundle `
            -Bundle $ResolvedSourceBundle `
            -Destination $TemporarySnapshot
        $ResolvedSourceSnapshot = $TemporarySnapshot
    }
    else {
        $LatestBundle = Get-ChildItem `
            -LiteralPath $Handoffs `
            -File `
            -Filter "vk-title-wave-apply-*.zip" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if ($null -ne $LatestBundle) {
            $ResolvedSourceBundle = $LatestBundle.FullName
            Expand-SnapshotFromBundle `
                -Bundle $ResolvedSourceBundle `
                -Destination $TemporarySnapshot
            $ResolvedSourceSnapshot = $TemporarySnapshot
        }
        else {
            $LatestSnapshot = Get-ChildItem `
                -LiteralPath $Exports `
                -File `
                -Filter "vk-*-post-title-wave-*.json" |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1

            if ($null -eq $LatestSnapshot) {
                throw (
                    "Не найден финальный snapshot волны названий " +
                    "или её ZIP в data\handoffs."
                )
            }
            $ResolvedSourceSnapshot = $LatestSnapshot.FullName
        }
    }

    Copy-Artifact `
        -Path $ResolvedSourceSnapshot `
        -Name "00-source-vk-snapshot.json"
    Copy-Artifact -Path $PolicyPath -Name "editorial-policy.json"

    if ([string]::IsNullOrWhiteSpace($Plan)) {
        $Plan = Join-Path $Reports "vk-editorial-description-wave-$Stamp.json"
        $Report = Join-Path $Reports "vk-editorial-description-wave-$Stamp.md"
        $HtmlReport = Join-Path $Reports "vk-editorial-description-wave-$Stamp.html"

        & py -3.11 -X utf8 .\scripts\build_vk_editorial_description_wave.py `
            "$ResolvedSourceSnapshot" `
            --policy-json "$PolicyPath" `
            --output "$Plan" `
            --report "$Report" `
            --html-report "$HtmlReport"

        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось построить descriptions-only план."
        }
        $GeneratedPlan = $true
    }
    else {
        $Plan = (Resolve-Path -LiteralPath $Plan).Path
        $Report = [System.IO.Path]::ChangeExtension($Plan, ".md")
        $HtmlReport = [System.IO.Path]::ChangeExtension($Plan, ".html")
    }

    $PlanJson = Get-Content `
        -LiteralPath $Plan `
        -Raw `
        -Encoding UTF8 |
        ConvertFrom-Json

    if ([string]$PlanJson.operation_scope -ne "editorial_only") {
        throw "План не является editorial_only."
    }
    if ([string]$PlanJson.component_scope -ne "descriptions_only") {
        throw "План не является descriptions_only."
    }
    if ([int]$PlanJson.target_community_id -ne $Community) {
        throw "План относится к другому VK-сообществу."
    }
    if ([int]$PlanJson.summary.titles_to_update -ne 0) {
        throw "План содержит изменения названий."
    }
    if ([int]$PlanJson.summary.albums_to_rename -ne 0) {
        throw "План содержит переименование альбомов."
    }
    if (
        [int]$PlanJson.summary.placements_to_add -ne 0 -or
        [int]$PlanJson.summary.placements_to_remove -ne 0 -or
        [int]$PlanJson.summary.videos_to_delete -ne 0
    ) {
        throw "План содержит каталожные изменения или удаления."
    }

    $BadTitles = @(
        $PlanJson.video_text_operations |
        Where-Object {
            [string]$_.before_title -cne [string]$_.after_title -or
            [string]$_.before_title_sha256 -cne [string]$_.after_title_sha256 -or
            [bool]$_.title_changed
        }
    )
    if ($BadTitles.Count -gt 0) {
        throw "План содержит скрытые изменения названий."
    }

    $UnprotectedDescriptions = @(
        $PlanJson.video_text_operations |
        Where-Object {
            -not [bool]$_.description_changed -or
            -not [bool]$_.semantic_body_preserved -or
            [string]::IsNullOrWhiteSpace([string]$_.semantic_body_sha256) -or
            @($_.change_reasons).Count -eq 0
        }
    )
    if ($UnprotectedDescriptions.Count -gt 0) {
        throw (
            "План содержит описание без semantic-body защиты " +
            "или причины изменения."
        )
    }

    Copy-Artifact -Path $Plan -Name "plan.json"
    Copy-Artifact -Path $Report -Name "plan-review.md"
    Copy-Artifact -Path $HtmlReport -Name "plan-review.html"

    if ($Execute) {
        $PreviousDryRun = Get-ChildItem `
            -LiteralPath $Handoffs `
            -File `
            -Filter "vk-description-wave-dry-run-*.zip" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if ($null -ne $PreviousDryRun) {
            Copy-Artifact `
                -Path $PreviousDryRun.FullName `
                -Name "previous-reviewed-dry-run.zip"
        }
    }

    Write-Host "План: $Plan" -ForegroundColor Cyan
    Write-Host "Запускается свежий live preflight..." -ForegroundColor Yellow

    & py -3.11 -X utf8 .\scripts\apply_vk_editorial_cleanup_plan.py `
        "$Plan" `
        --account "$Account" `
        --community $Community `
        --max-operations ([int]$PlanJson.summary.total_operations) 2>&1 |
        Tee-Object -FilePath $PreflightLog

    $PreflightExit = $LASTEXITCODE
    if ($PreflightExit -ne 0) {
        throw "Live preflight завершился с кодом $PreflightExit."
    }

    $PreflightText = Get-Content `
        -LiteralPath $PreflightLog `
        -Raw `
        -Encoding UTF8
    $Ready = Read-PreflightCount -Text $PreflightText -Label "ready"
    $AlreadyApplied = Read-PreflightCount `
        -Text $PreflightText `
        -Label "already applied"
    $Conflicts = Read-PreflightCount -Text $PreflightText -Label "conflicts"

    if ($Conflicts -ne 0) {
        throw "Live preflight обнаружил $Conflicts конфликтов."
    }

    if (-not $Execute) {
        $RunStatus = "dry_run_completed"
        Write-Host ""
        Write-Host "Dry-run описаний завершён. Записей в VK не было." `
            -ForegroundColor Green
        return
    }

    Write-Host ""
    Write-Host "Выполняется безопасное продолжение описаний:" `
        -ForegroundColor Yellow
    Write-Host "  ready:           $Ready"
    Write-Host "  already applied: $AlreadyApplied"
    Write-Host "  total plan ops:  $($PlanJson.summary.total_operations)"

    & py -3.11 -X utf8 .\scripts\apply_vk_editorial_cleanup_plan.py `
        "$Plan" `
        --account "$Account" `
        --community $Community `
        --execute `
        --confirm-community $Community `
        --confirm-ready $Ready `
        --confirm-plan-sha256 "$($PlanJson.plan_sha256)" `
        --confirm-video-coverage "$($PlanJson.target_video_ids_sha256)" `
        --confirm-memberships "$($PlanJson.initial_memberships_sha256)" `
        --max-operations ([int]$PlanJson.summary.total_operations) `
        --write-delay 2.0 `
        --result-output "$ResultPath" 2>&1 |
        Tee-Object -FilePath $ApplyLog

    $ApplyExit = $LASTEXITCODE
    if ($ApplyExit -ne 0) {
        throw "Применение завершилось с кодом $ApplyExit."
    }

    if (-not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        throw "Не создан result journal."
    }

    $ResultJson = Get-Content `
        -LiteralPath $ResultPath `
        -Raw `
        -Encoding UTF8 |
        ConvertFrom-Json

    if ([string]$ResultJson.status -ne "completed") {
        throw "Result journal не получил status=completed."
    }
    if ([string]$ResultJson.plan_sha256 -ne [string]$PlanJson.plan_sha256) {
        throw "Result journal относится к другому плану."
    }

    video-manager vk scan `
        --account "$Account" `
        --community "$Community" `
        --output "$FinalSnapshot"

    if ($LASTEXITCODE -ne 0) {
        throw "Финальный read-only VK scan завершился ошибкой."
    }

    $RunStatus = "completed"
    Write-Host ""
    Write-Host "VK description wave завершена и postflight-подтверждена." `
        -ForegroundColor Green
}
catch {
    $RunStatus = "failed"
    $RunError = $_.Exception.Message
    Write-Host ""
    Write-Host "ОШИБКА: $RunError" -ForegroundColor Red
    throw
}
finally {
    try {
        Write-Bundle
    }
    finally {
        if (Test-Path -LiteralPath $TempRunDir) {
            Remove-Item -LiteralPath $TempRunDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
