# Requires -Version 7.0
<#
.SYNOPSIS
    Автономный read-only probe для проверки нативных карточек VK через wall.parseAttachedLink
    и предварительный сброс кэша pages.clearCache.

.DESCRIPTION
    - Безопасно загружает VK токен пользователя из переменных окружения или локального .env
    - Не выводит токен в консоль и логи
    - Сбрасывает кэш внешних ссылок через pages.clearCache
    - Выполняет wall.parseAttachedLink с корректной JSON-структурой [{"type":"link","link":"URL"}]
    - Проверяет наличие встроенного изображения (owner_id_id)
    - НЕ вызывает wall.post
    - НЕ вызывает ни одного метода photos.*
    - Сохраняет полный отчёт в data\vk-wall\native-preview-probe\probe-report.json
#>

[CmdletBinding()]
param(
    [string]$TargetUrl = "https://gospod-bog.ru/articles/rimlyanam-7-veruyushchiy-ili-neveruyushchiy/"
)

$ErrorActionPreference = "Stop"

# Setup UTF-8 encoding for clean output
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "content"))) {
    $RepoRoot = Split-Path -Parent $RepoRoot
}

function Get-VkTokenSafe {
    # 1. Прямые переменные окружения
    $candidates = @("VCM_VK_ACCESS_TOKEN", "VK_API_TOKEN", "VK_TOKEN", "VK_USER_TOKEN", "VK_ACCESS_TOKEN")
    foreach ($name in $candidates) {
        $val = [Environment]::GetEnvironmentVariable($name)
        if (![string]::IsNullOrWhiteSpace($val)) {
            return $val.Trim()
        }
    }

    # 2. Внутреннее хранилище токенов репозитория (data\secrets\vk\*.json)
    $tokenDir = Join-Path $RepoRoot "data\secrets\vk"
    if (Test-Path -LiteralPath $tokenDir) {
        $jsonFiles = @("legendary-poet.json", "lord-god.json") + (Get-ChildItem -LiteralPath $tokenDir -Filter "*.json" -File | Select-Object -ExpandProperty Name)
        foreach ($jf in ($jsonFiles | Select-Object -Unique)) {
            $jp = Join-Path $tokenDir $jf
            if (Test-Path -LiteralPath $jp) {
                try {
                    $obj = Get-Content -LiteralPath $jp -Raw -Encoding UTF8 | ConvertFrom-Json
                    if (![string]::IsNullOrWhiteSpace($obj.access_token)) {
                        return $obj.access_token.Trim()
                    }
                } catch {}
            }
        }
    }

    # 3. Внешний общий файл настроек (C:\Users\Fedor\Projects\mp3telegrambot\.env или VCM_VK_SHARED_ENV_FILE)
    $sharedPaths = @()
    if (![string]::IsNullOrWhiteSpace($env:VCM_VK_SHARED_ENV_FILE)) {
        $sharedPaths += $env:VCM_VK_SHARED_ENV_FILE
    }
    if (![string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $sharedPaths += Join-Path $env:USERPROFILE "Projects\mp3telegrambot\.env"
    }
    $sharedPaths += "C:\Users\Fedor\Projects\mp3telegrambot\.env"
    $sharedPaths += Join-Path $RepoRoot ".env"

    foreach ($path in ($sharedPaths | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $path) {
            $lines = Get-Content -LiteralPath $path -Encoding UTF8
            foreach ($line in $lines) {
                if ($line -match "^\s*(VK_API_TOKEN|VCM_VK_ACCESS_TOKEN|VK_TOKEN|VK_USER_TOKEN|VK_ACCESS_TOKEN)\s*=\s*(.+)$") {
                    $val = $Matches[2].Trim()
                    if ($val.StartsWith('"') -and $val.EndsWith('"')) {
                        $val = $val.Substring(1, $val.Length - 2)
                    }
                    if (![string]::IsNullOrWhiteSpace($val)) {
                        return $val
                    }
                }
            }
        }
    }

    throw "Не найден токен пользователя VK (VK_API_TOKEN). Проверены окружение, data\secrets\vk\ и C:\Users\Fedor\Projects\mp3telegrambot\.env."
}

function Invoke-VkApi {
    param(
        [Parameter(Mandatory=$true)][string]$Method,
        [Parameter(Mandatory=$true)][hashtable]$Params,
        [Parameter(Mandatory=$true)][string]$Token
    )

    $uri = "https://api.vk.com/method/$Method"
    $body = @{
        access_token = $Token
        v = "5.199"
    }
    foreach ($key in $Params.Keys) {
        $body[$key] = $Params[$key]
    }

    $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ErrorAction Stop
    if ($response.error) {
        throw "VK API Error [$($response.error.error_code)] in method ${Method}: $($response.error.error_msg)"
    }
    return $response.response
}

# 1. Загрузка токена и проверка прав пользователя
$token = Get-VkTokenSafe
Write-Host " [i] Проверка VK токена пользователя..." -ForegroundColor Cyan
$userInfo = Invoke-VkApi -Method "users.get" -Params @{} -Token $token
if ($null -eq $userInfo -or $userInfo.Count -eq 0) {
    throw "Не удалось подтвердить пользовательский токен VK."
}
Write-Host " [ok] Токен подтверждён для пользователя ID: $($userInfo[0].id)" -ForegroundColor Green

# 2. Очистка кэша ссылки VK (pages.clearCache)
Write-Host " [i] Вызов pages.clearCache для URL: $TargetUrl" -ForegroundColor Cyan
$clearRes = Invoke-VkApi -Method "pages.clearCache" -Params @{ url = $TargetUrl } -Token $token
Write-Host " [ok] Кэш VK сброшен (результат: $clearRes)" -ForegroundColor Green

# 3. Запрос структуры карточки VK (wall.parseAttachedLink)
Write-Host " [i] Вызов wall.parseAttachedLink с корректной структурой..." -ForegroundColor Cyan
$linksJson = '[{"type":"link","link":"' + $TargetUrl + '"}]'

$parsedData = $null
$attempts = @(1, 0, 1)
foreach ($ext in $attempts) {
    $res = Invoke-VkApi -Method "wall.parseAttachedLink" -Params @{
        links = $linksJson
        extended = $ext
    } -Token $token

    if ($null -ne $res.data -and $res.data.Count -gt 0) {
        $parsedData = $res.data
        break
    }
    Start-Sleep -Seconds 1
}

# 4. Анализ полученного ответа
$matchingLink = $null
$linkTitle = "<none>"
$linkPhotoId = "<none>"
$verdict = "native_preview_no_photo"

if ($null -ne $parsedData) {
    foreach ($item in $parsedData) {
        if ($item.type -eq "link" -and $null -ne $item.link) {
            $linkObj = $item.link
            $linkTitle = $linkObj.title
            if ($null -ne $linkObj.photo -and $linkObj.photo.owner_id -ne 0 -and $linkObj.photo.id -ne 0) {
                $linkPhotoId = "$($linkObj.photo.owner_id)_$($linkObj.photo.id)"
                $verdict = "native_preview_ready"
                $matchingLink = $linkObj
                break
            }
        }
    }
}

Write-Host "----------------------------------------------------" -ForegroundColor Yellow
Write-Host "Verdict: $verdict" -ForegroundColor ($verdict -eq "native_preview_ready" ? "Green" : "Red")
Write-Host "link_title: $linkTitle" -ForegroundColor White
Write-Host "link_photo_id: $linkPhotoId" -ForegroundColor White
Write-Host "wall.post called: false" -ForegroundColor White
Write-Host "photos.* called: false" -ForegroundColor White
Write-Host "----------------------------------------------------" -ForegroundColor Yellow

# 5. Сохранение отчёта
$outDir = Join-Path $RepoRoot "data\vk-wall\native-preview-probe"
if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -Path $outDir -ItemType Directory -Force | Out-Null
}
$reportPath = Join-Path $outDir "probe-report.json"

$report = @{
    schema_name = "video-manager.vk-native-preview-probe"
    timestamp = [datetime]::UtcNow.ToString("o")
    target_url = $TargetUrl
    clear_cache_result = $clearRes
    verdict = $verdict
    link_title = $linkTitle
    link_photo_id = $linkPhotoId
    raw_response_count = ($null -ne $parsedData ? $parsedData.Count : 0)
    wall_post_called = $false
    photos_api_called = $false
}

$jsonStr = $report | ConvertTo-Json -Depth 5 -Compress
[System.IO.File]::WriteAllText($reportPath, $jsonStr, [System.Text.UTF8Encoding]::new($false))
Write-Host " [ok] Отчёт сохранён: $reportPath" -ForegroundColor Cyan
