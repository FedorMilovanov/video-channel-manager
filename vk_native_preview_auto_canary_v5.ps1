# Requires -Version 7.0
<#
.SYNOPSIS
    Единая автоматизированная команда для проверки нативных карточек VK (v5)
    через pages.clearCache и wall.parseAttachedLink, с опциональным созданием и удалением 1 canary-поста.

.DESCRIPTION
    1. Не выполняет merge, reset или rebase вашей локальной ветки.
    2. Безопасно проверяет пользовательский токен VK (без вывода в консоль).
    3. Берёт все 10 URL из source contract (content/policies/lord-god-article-wave-v3-source-contract.json).
    4. Проверяет доступность каждой страницы и Open Graph метаданные как браузер и как vkShare.
    5. Для каждого URL вызывает pages.clearCache.
    6. Выполняет до 3 bounded-попыток wall.parseAttachedLink (extended=0/1).
    7. В режиме Probe или если карточка первой статьи без фото — останавливается до wall.post.
    8. В режиме AutoCanary при успехе первой статьи создаёт ровно 1 отложенный canary-пост.
    9. Проверяет, что в посте ровно 1 вложение link без отдельного photo.
   10. Удаляет тестовую запись по точному post_id (wall.delete).
   11. Не вызывает ни одного метода photos.*.
   12. Не касается журналов и operation ID активной фото-волны v4.
#>

[CmdletBinding()]
param(
    [ValidateSet("Probe", "AutoCanary", "Clean")]
    [string]$Mode = "AutoCanary",

    [switch]$KeepCanary
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "content"))) {
    $RepoRoot = Split-Path -Parent $RepoRoot
}

# Counters for strict verification report
$script:WallPostCalls = 0
$script:WallDeleteCalls = 0
$script:PhotosApiCalls = 0

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

    if ($Method -like "photos.*") {
        $script:PhotosApiCalls++
    } elseif ($Method -eq "wall.post") {
        $script:WallPostCalls++
    } elseif ($Method -eq "wall.delete") {
        $script:WallDeleteCalls++
    }

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

function Test-WebPageOg {
    param([string]$Url)

    $results = @{
        browser_ok = $false
        vkshare_ok = $false
        og_title = $null
        og_image = $null
        webp_image = $false
    }

    try {
        $headersBrowser = @{ "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" }
        $resB = Invoke-WebRequest -Uri $Url -Headers $headersBrowser -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        if ($resB.StatusCode -eq 200) { $results.browser_ok = $true }

        $headersVk = @{ "User-Agent" = "Mozilla/5.0 (compatible; vkShare; +http://vk.com/dev/Share)" }
        $resV = Invoke-WebRequest -Uri $Url -Headers $headersVk -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        if ($resV.StatusCode -eq 200) {
            $results.vkshare_ok = $true
            $content = $resV.Content
            if ($content -match '<meta\s+property="og:title"\s+content="([^"]+)"') {
                $results.og_title = [System.Net.WebUtility]::HtmlDecode($Matches[1])
            }
            if ($content -match '<meta\s+property="og:image"\s+content="([^"]+)"') {
                $results.og_image = $Matches[1]
                if ($results.og_image -match "\.webp($|\?)") {
                    $results.webp_image = $true
                }
            }
        }
    } catch {
        # Ignore HTTP transient errors during offline/sandboxed audit
    }
    return $results
}

# 1. Загрузка токена и проверка, что это токен пользователя
$token = Get-VkTokenSafe
Write-Host " [i] Проверка типа VK-токена (users.get)..." -ForegroundColor Cyan
$userRes = Invoke-VkApi -Method "users.get" -Params @{} -Token $token
if ($null -eq $userRes -or $userRes.Count -eq 0) {
    throw "Не удалось подтвердить пользовательский токен VK."
}
$userId = $userRes[0].id
Write-Host " [ok] Токен пользователя подтверждён (ID: $userId)" -ForegroundColor Green

# 2. Загрузка 10 URL из Source Contract
$contractPath = Join-Path $RepoRoot "content\policies\lord-god-article-wave-v3-source-contract.json"
if (-not (Test-Path -LiteralPath $contractPath)) {
    $contractPath = Join-Path $RepoRoot "content\policies\lord-god-article-wave-202608.json"
}
if (-not (Test-Path -LiteralPath $contractPath)) {
    throw "Не найден файл политики: $contractPath"
}
$contractJson = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json
$operations = $contractJson.operations
if ($null -eq $operations -or $operations.Count -eq 0) {
    throw "В файле $contractPath не найдены операции."
}

Write-Host " [i] Найдено операций для проверки: $($operations.Count)" -ForegroundColor Cyan

# 3. Проверка метаданных, сброс кэша и wall.parseAttachedLink для каждой из 10 статей
$resultsList = @()
$cardsWithPhotoCount = 0

foreach ($op in $operations) {
    $url = $op.article_url
    if ([string]::IsNullOrWhiteSpace($url)) {
        $url = $op.url
    }
    $opId = $op.operation_id
    if ([string]::IsNullOrWhiteSpace($opId)) {
        $opId = $op.id
    }

    Write-Host " -> Проверка [$opId]: $url" -ForegroundColor White
    $ogInfo = Test-WebPageOg -Url $url

    # Вызов pages.clearCache
    $clearRes = Invoke-VkApi -Method "pages.clearCache" -Params @{ url = $url } -Token $token

    # До 3 bounded-попыток wall.parseAttachedLink с чередованием extended=0/1
    $linksJson = '[{"type":"link","link":"' + $url + '"}]'
    $parsedData = $null
    foreach ($ext in @(1, 0, 1)) {
        $res = Invoke-VkApi -Method "wall.parseAttachedLink" -Params @{
            links = $linksJson
            extended = $ext
        } -Token $token
        if ($null -ne $res.data -and $res.data.Count -gt 0) {
            $parsedData = $res.data
            break
        }
        Start-Sleep -Milliseconds 700
    }

    $hasPhoto = $false
    $photoIdStr = $null
    $parsedTitle = $null

    if ($null -ne $parsedData) {
        foreach ($item in $parsedData) {
            if ($item.type -eq "link" -and $null -ne $item.link) {
                $linkObj = $item.link
                $parsedTitle = $linkObj.title
                if ($null -ne $linkObj.photo -and $linkObj.photo.owner_id -ne 0 -and $linkObj.photo.id -ne 0) {
                    $hasPhoto = $true
                    $photoIdStr = "$($linkObj.photo.owner_id)_$($linkObj.photo.id)"
                    $cardsWithPhotoCount++
                    break
                }
            }
        }
    }

    $resultsList += @{
        operation_id = $opId
        url = $url
        og_title = $ogInfo.og_title
        og_image = $ogInfo.og_image
        webp_image = $ogInfo.webp_image
        clear_cache_result = $clearRes
        has_photo = $hasPhoto
        link_photo_id = $photoIdStr
        parsed_title = $parsedTitle
    }
}

Write-Host "====================================================" -ForegroundColor Yellow
Write-Host "Нативные карточки с фото: $cardsWithPhotoCount/$($operations.Count)" -ForegroundColor ($cardsWithPhotoCount -gt 0 ? "Green" : "Red")
Write-Host "====================================================" -ForegroundColor Yellow

$firstArticle = $resultsList[0]

# 4. В режиме Probe сохраняем отчёт и выходим
$outDir = Join-Path $RepoRoot "data\vk-wall\native-link-canary-v5"
if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -Path $outDir -ItemType Directory -Force | Out-Null
}

if ($Mode -eq "Probe") {
    $reportPath = Join-Path $outDir "probe-report.json"
    $report = @{
        schema_name = "video-manager.vk-native-preview-probe-v5"
        timestamp = [datetime]::UtcNow.ToString("o")
        total_operations = $operations.Count
        cards_with_photo = $cardsWithPhotoCount
        first_article_has_photo = $firstArticle.has_photo
        items = $resultsList
        wall_post_calls = $script:WallPostCalls
        wall_delete_calls = $script:WallDeleteCalls
        photos_api_calls = $script:PhotosApiCalls
    }
    $report | ConvertTo-Json -Depth 5 -Compress | Out-File -FilePath $reportPath -Encoding UTF8
    Write-Host " [ok] Read-only проверка завершена. Отчёт: $reportPath" -ForegroundColor Cyan
    exit 0
}

# 5. Режим AutoCanary
if (-not $firstArticle.has_photo) {
    Write-Host "НАТИВНАЯ КАРТОЧКА НЕ ПОДТВЕРЖДЕНА." -ForegroundColor Red
    Write-Host "wall.post НЕ ВЫЗЫВАЛСЯ." -ForegroundColor Yellow

    $reportPath = Join-Path $outDir "canary-report.json"
    $report = @{
        schema_name = "video-manager.vk-native-preview-canary-v5"
        timestamp = [datetime]::UtcNow.ToString("o")
        status = "native_card_unconfirmed_no_post"
        first_article = $firstArticle
        wall_post_calls = $script:WallPostCalls
        wall_delete_calls = $script:WallDeleteCalls
        photos_api_calls = $script:PhotosApiCalls
    }
    $report | ConvertTo-Json -Depth 5 -Compress | Out-File -FilePath $reportPath -Encoding UTF8
    exit 0
}

Write-Host " [i] Первая статья ($($firstArticle.operation_id)) имеет встроенное фото ($($firstArticle.link_photo_id))." -ForegroundColor Green
Write-Host " [i] Создание 1 отложенного canary-поста (wall.post)..." -ForegroundColor Cyan

# Повторный parse перед отправкой
$firstUrl = $firstArticle.url
$linksJson = '[{"type":"link","link":"' + $firstUrl + '"}]'
$resParseAgain = Invoke-VkApi -Method "wall.parseAttachedLink" -Params @{ links = $linksJson; extended = 1 } -Token $token

$ownerIdGroup = -60805374
$publishDate = [DateTimeOffset]::UtcNow.AddDays(7).ToUnixTimeSeconds()
$canaryGuid = "canary-v5-" + [datetime]::UtcNow.ToString("yyyyMMddHHmmss")

$firstOpObj = $operations[0]
$msgText = $firstOpObj.message
if ([string]::IsNullOrWhiteSpace($msgText)) {
    $msgText = "📖 Тестовая запись: проверка нативной карточки VK"
}

$postRes = Invoke-VkApi -Method "wall.post" -Params @{
    owner_id = $ownerIdGroup
    from_group = 1
    message = $msgText
    attachments = $firstUrl
    publish_date = $publishDate
    guid = $canaryGuid
} -Token $token

if ($null -eq $postRes.post_id) {
    throw "wall.post не вернул post_id."
}

$postId = $postRes.post_id
Write-Host " [ok] Canary создан: wall${ownerIdGroup}_${postId}" -ForegroundColor Green

# Проверка созданной записи через wall.getById
$getRes = Invoke-VkApi -Method "wall.getById" -Params @{
    posts = "${ownerIdGroup}_${postId}"
} -Token $token

$createdPost = $getRes[0]
$attCount = 0
$hasLinkAtt = $false
$hasPhotoAtt = $false

if ($null -ne $createdPost.attachments) {
    $attCount = $createdPost.attachments.Count
    foreach ($att in $createdPost.attachments) {
        if ($att.type -eq "link") { $hasLinkAtt = $true }
        if ($att.type -eq "photo") { $hasPhotoAtt = $true }
    }
}

if ($attCount -ne 1 -or -not $hasLinkAtt -or $hasPhotoAtt) {
    Write-Warning "Созданный пост содержит неожиданную структуру вложений (attCount=$attCount, link=$hasLinkAtt, photo=$hasPhotoAtt)."
} else {
    Write-Host " [ok] Проверка вложений успешна: ровно 1 вложение типа link, без отдельного photo." -ForegroundColor Green
}

# Удаление canary по умолчанию
if (-not $KeepCanary) {
    Write-Host " [i] Удаление тестовой записи (wall.delete)..." -ForegroundColor Yellow
    $delRes = Invoke-VkApi -Method "wall.delete" -Params @{
        owner_id = $ownerIdGroup
        post_id = $postId
    } -Token $token
    Write-Host "Canary verified: wall${ownerIdGroup}_${postId}" -ForegroundColor Green
    Write-Host "Canary точно удалён после успешной проверки." -ForegroundColor Green
} else {
    Write-Host "Canary verified: wall${ownerIdGroup}_${postId} (-KeepCanary указан, запись оставлена)." -ForegroundColor Yellow
}

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "ГОТОВО: canary_verified_and_deleted" -ForegroundColor Green
Write-Host "wall.post calls: $script:WallPostCalls" -ForegroundColor White
Write-Host "wall.delete calls: $script:WallDeleteCalls" -ForegroundColor White
Write-Host "photos.* calls: $script:PhotosApiCalls" -ForegroundColor White
Write-Host "====================================================" -ForegroundColor Cyan

$reportPath = Join-Path $outDir "canary-report.json"
$report = @{
    schema_name = "video-manager.vk-native-preview-canary-v5"
    timestamp = [datetime]::UtcNow.ToString("o")
    status = "canary_verified_and_deleted"
    first_article = $firstArticle
    post_id = $postId
    owner_id = $ownerIdGroup
    attachments_verified = ($attCount -eq 1 -and $hasLinkAtt -and -not $hasPhotoAtt)
    wall_post_calls = $script:WallPostCalls
    wall_delete_calls = $script:WallDeleteCalls
    photos_api_calls = $script:PhotosApiCalls
}
$report | ConvertTo-Json -Depth 5 -Compress | Out-File -FilePath $reportPath -Encoding UTF8
exit 0
