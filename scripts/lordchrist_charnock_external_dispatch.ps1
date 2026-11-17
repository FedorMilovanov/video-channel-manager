# Independent Windows clock -> existing owner-only GitHub Actions dispatch.
# Does not publish to Telegram or Telegraph. No stored tokens, no catch-up.
[CmdletBinding()]
param(
    [switch]$Dispatch,
    [string]$ProbeAt
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = 'FedorMilovanov/video-channel-manager'
$workflow = 'lordchrist-charnock-scheduled-reissue.yml'
$manifestPath = 'content/telegram/lordchrist/telegraph-v1/charnock/charnock-reschedule-2026.json'
$ledgerPath = 'content/telegram/lordchrist/telegraph-v1/publication-ledger.json'
$approvedManifestSha256 = '13f3716d5dffc32291ac3c9ee12f82591389bcb5154e7ecf0a534741c6b960fd'
$approvedWorkflowBlob = '3cd700040228cd6b6ba2227ad22cd87e7d7e9c32'
$confirm = 'RUN_APPROVED_CHARNOCK_SLOT_ONCE'
$slots = [ordered]@{
    '2026-11-20' = 'lordchrist-telegraph-charnock-09'
    '2026-11-24' = 'lordchrist-telegraph-charnock-10'
    '2026-11-27' = 'lordchrist-telegraph-charnock-11'
    '2026-12-01' = 'lordchrist-telegraph-charnock-12'
}
if ($Dispatch -and $ProbeAt) { throw 'Simulated time forbidden in execution mode' }
$moscow = [TimeZoneInfo]::FindSystemTimeZoneById('Russian Standard Time')
$instant = if ($ProbeAt) {
    if ($ProbeAt -notmatch '^2026-(11|12)-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+03:00$') {
        throw 'ProbeAt requires explicit +03:00 date-time in approved year'
    }
    [DateTimeOffset]::Parse($ProbeAt, [Globalization.CultureInfo]::InvariantCulture)
} else { [DateTimeOffset]::UtcNow }
$local = [TimeZoneInfo]::ConvertTime($instant, $moscow)
$dateKey = $local.ToString('yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
if (-not $slots.Contains($dateKey)) {
    Write-Output "NO_DUE date=$dateKey; no provider operation"
    exit 0
}
$publicationId = $slots[$dateKey]
if ($local.Hour -notin @(12, 13)) {
    Write-Output "OUTSIDE_APPROVED_WINDOW date=$dateKey; no provider operation"
    exit 0
}
# A scheduled task has a different PATH from the interactive terminal.
$gh = 'C:\Program Files\GitHub CLI\gh.exe'
if (-not (Test-Path -LiteralPath $gh -PathType Leaf)) {
    throw 'Approved GitHub CLI executable is missing'
}
function Invoke-CheckedGh {
    param([string[]]$Arguments)
    $result = & $gh @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI request unsuccessful; no dispatch' }
    return ($result -join "`n")
}
function Get-VerifiedGitHubFile {
    param([string]$Path, [string]$Ref)
    $api = "repos/$repo/contents/$Path`?ref=$Ref"
    $response = Invoke-CheckedGh -Arguments @('api', $api) | ConvertFrom-Json -Depth 100
    if ($response.encoding -ne 'base64' -or -not $response.content) {
        throw 'GitHub content response integrity failure'
    }
    $rawBytes = [Convert]::FromBase64String(($response.content -replace '\s', ''))
    $text = [Text.Encoding]::UTF8.GetString($rawBytes)
    return [pscustomobject]@{ Blob = [string]$response.sha; Text = $text; Bytes = $rawBytes }
}
$actor = (Invoke-CheckedGh -Arguments @('api', 'user', '--jq', '.login')).Trim()
if ($actor -cne 'FedorMilovanov') { throw 'Current GitHub CLI actor is not the approved owner' }
$workflowFile = Get-VerifiedGitHubFile -Path ".github/workflows/$workflow" -Ref 'main'
if ($workflowFile.Blob -cne $approvedWorkflowBlob) { throw 'Approved publisher workflow changed on main; no dispatch' }
$manifestFile = Get-VerifiedGitHubFile -Path $manifestPath -Ref 'main'
$hasher = [Security.Cryptography.SHA256]::Create()
try { $hash = [BitConverter]::ToString($hasher.ComputeHash($manifestFile.Bytes)).Replace('-', '').ToLowerInvariant() }
finally { $hasher.Dispose() }
if ($hash -cne $approvedManifestSha256) { throw 'Approved manifest SHA-256 changed; no dispatch' }
$manifest = $manifestFile.Text | ConvertFrom-Json -Depth 100
if ($manifest.channel -cne '@lordchrist' -or $manifest.timezone -cne 'Europe/Moscow' -or
    $manifest.release_time -cne '12:00' -or @($manifest.items).Count -ne 8) {
    throw 'Approved release manifest structure changed'
}
$due = @($manifest.items | Where-Object {
    $_.scheduled_on_moscow -ceq $dateKey -and $_.publication_id -ceq $publicationId
})
if ($due.Count -ne 1) { throw 'No unique exact approved Charnock due slot' }
$ledgerFile = Get-VerifiedGitHubFile -Path $ledgerPath -Ref 'state/lordchrist-telegram'
$ledger = $ledgerFile.Text | ConvertFrom-Json -Depth 100
if ($ledger.schema_name -cne 'video-channel-manager.lordchrist-telegraph-ledger' -or
    $ledger.project_key -cne 'lord-god-strength') {
    throw 'Protected ledger schema mismatch'
}
$receiptProperty = $ledger.entries.PSObject.Properties[$publicationId]
if ($null -eq $receiptProperty -or $null -eq $receiptProperty.Value) {
    throw 'Original verified receipt missing; no dispatch'
}
$entry = $receiptProperty.Value
if ($entry.state -cne 'published' -or $entry.provider_effect -cne 'verified' -or
    $entry.telegram_message_id -ne (1590 + [int]$publicationId.Substring($publicationId.Length - 2))) {
    throw 'Original receipt mismatch; no dispatch'
}
if ($entry.PSObject.Properties.Name -contains 'scheduled_reissue') {
    Write-Output "ALREADY_CLAIMED $publicationId; no dispatch"
    exit 0
}
if (-not $Dispatch) {
    Write-Output "WOULD_DISPATCH $publicationId date=$dateKey; read-only, no event sent"
    exit 0
}
# One dispatch request only. GitHub's shared concurrency lock, live lease,
# exact-head proof, durable state claim and no-replay checks are still required.
Invoke-CheckedGh -Arguments @('workflow','run',$workflow,'--repo',$repo,'--ref','main',
    '-f',"publication_id=$publicationId",'-f',"confirm=$confirm") | Out-Null
Write-Output "DISPATCH_REQUESTED $publicationId date=$dateKey; publication NOT verified"
