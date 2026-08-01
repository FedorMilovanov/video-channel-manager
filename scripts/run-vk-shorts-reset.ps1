[CmdletBinding()]
param(
    [ValidateSet("Prepare", "Canary", "Apply", "Status")]
    [string]$Mode = "Prepare",

    [string]$Repo = "C:\Users\Fedor\Projects\video-channel-manager",

    [string]$Account = "legendary-poet",

    [int]$Community = 60805374,

    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$Script = Join-Path $Repo "scripts\vk_shorts_reset_current.py"
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $VenvPython
}
else {
    (Get-Command python -ErrorAction Stop).Source
}

if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
    throw "Не найден актуальный исполнитель V3: $Script. Сначала выполните git pull."
}

$env:VCM_DATA_DIR = Join-Path $Repo "data"
$env:PYTHONPATH = Join-Path $Repo "src"
$OperationRoot = Join-Path $Repo "data\vk-shorts-reset-20260801-v3"
New-Item -ItemType Directory -Path $OperationRoot -Force | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Log = Join-Path $OperationRoot ("{0}-{1}.log" -f $Mode.ToLowerInvariant(), $Timestamp)

function Get-ConfirmationToken {
    $Summary = Join-Path $OperationRoot "plan-summary.json"
    if (-not (Test-Path -LiteralPath $Summary -PathType Leaf)) {
        throw "Нет plan-summary.json V3. Сначала запустите -Mode Prepare."
    }
    $Payload = Get-Content -LiteralPath $Summary -Raw -Encoding UTF8 | ConvertFrom-Json
    $Token = [string]$Payload.confirmation_token
    if ([string]::IsNullOrWhiteSpace($Token)) {
        throw "В plan-summary.json отсутствует confirmation_token."
    }
    return $Token
}

function Assert-MediaTools {
    foreach ($Tool in @("ffmpeg", "ffprobe")) {
        if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
            throw "Не найден $Tool в PATH."
        }
    }
    $YtDlpCommand = Get-Command "yt-dlp" -ErrorAction SilentlyContinue
    if (-not $YtDlpCommand) {
        & $Python -c "import yt_dlp" 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Не найден yt-dlp. Установите: python -m pip install -U yt-dlp"
        }
    }
}

$Arguments = @(
    $Script,
    "--repo", $Repo,
    "--account", $Account,
    "--community", "$Community"
)

Remove-Item Env:VCM_ALLOW_UPLOAD_OPERATIONS -ErrorAction SilentlyContinue
Remove-Item Env:VCM_ALLOW_DESTRUCTIVE_OPERATIONS -ErrorAction SilentlyContinue

switch ($Mode) {
    "Prepare" {
        $Arguments += @(
            "prepare",
            "--boundary-post", "12400",
            "--view-cutoff", "20"
        )
    }

    "Canary" {
        if (-not $Execute) {
            throw "Canary выполняет одну загрузку. Добавьте -Execute."
        }
        Assert-MediaTools
        $env:VCM_ALLOW_UPLOAD_OPERATIONS = "1"
        $Arguments += @(
            "canary",
            "--confirm", (Get-ConfirmationToken),
            "--execute"
        )
    }

    "Apply" {
        if (-not $Execute) {
            throw "Apply выполняет загрузки и удаления. Добавьте -Execute."
        }
        Assert-MediaTools
        $env:VCM_ALLOW_UPLOAD_OPERATIONS = "1"
        $env:VCM_ALLOW_DESTRUCTIVE_OPERATIONS = "1"
        $Arguments += @(
            "apply",
            "--confirm", (Get-ConfirmationToken),
            "--execute"
        )
    }

    "Status" {
        $Arguments += "status"
    }
}

$TranscriptStarted = $false
try {
    Start-Transcript -LiteralPath $Log -Force | Out-Null
    $TranscriptStarted = $true

    Write-Host ""
    Write-Host "VK SHORTS RESET V3 — $Mode" -ForegroundColor Cyan
    Write-Host "Project: Господь Бог — Сила Моя" -ForegroundColor Cyan
    Write-Host "Community: 60805374" -ForegroundColor Cyan
    Write-Host "Сохраняем стену до post_id 12400 включительно." -ForegroundColor Green
    Write-Host "Источник при отсутствии MP4: существующий VK-клип." -ForegroundColor Green
    Write-Host "Новые загрузки не публикуются на стене." -ForegroundColor Green
    Write-Host "Log: $Log" -ForegroundColor Cyan
    Write-Host ""

    & $Python @Arguments
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "Исполнитель завершился с кодом $ExitCode. См. лог: $Log"
    }

    Write-Host ""
    Write-Host "ГОТОВО: $Mode" -ForegroundColor Green
    Write-Host "Статус: pwsh -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode Status" -ForegroundColor Cyan
}
finally {
    Remove-Item Env:VCM_ALLOW_UPLOAD_OPERATIONS -ErrorAction SilentlyContinue
    Remove-Item Env:VCM_ALLOW_DESTRUCTIVE_OPERATIONS -ErrorAction SilentlyContinue
    if ($TranscriptStarted) {
        Stop-Transcript | Out-Null
    }
}
