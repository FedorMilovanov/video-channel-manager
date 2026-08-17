# Grace Church Russian Resi live capture

Status: supported local-only workflow after Issues #425 and #440  
Provider effect: `impossible`

Use this runbook when the operator wants to capture the changing Grace Community Church **Russian-page** Resi manifest now or on a later service without reconstructing commands from chat history.

Canonical pages:

```text
Russian: https://www.gracechurch.org/live?language=russian
English: https://www.gracechurch.org/live?language=english
```

## Critical distinction

`?language=russian` selects the Russian-labelled Grace page/player. It does **not** prove that a Russian interpreter is speaking in a particular service.

Keep these facts separate:

1. **page identity** — which Grace language page was opened;
2. **Resi player identity** — which `control.resi.io/webplayer/video.html?id=...` frame the page loaded;
3. **manifest identity** — which `resi.media/.../Manifest.mpd` that player requested;
4. **spoken-language evidence** — what is actually heard during sermon speech.

Never collapse 1–3 into claim 4. A hymn, intro, room audio, or Russian player carrying house English can all sound English. Conversely, one English hymn is not proof that sermon interpretation is absent. Verify multiple sermon speech points before deciding.

## 2026-08-17 incident evidence — historical, not current routing

These values explain the defect class and are **not** forever-current manifests:

```text
English page
  player:   8fd0d098-1c9e-4580-9f8a-3c8cc57d1624
  manifest: https://resi.media/HccRTy/f142475a-2c9b-48d0-bd75-c3be730ca14c/Manifest.mpd?src=emb

Russian page
  player:   52260827-f6e9-4a2e-8978-aed53dbf1413
  manifest: https://resi.media/GiHDtf/e4335292-5fe8-4525-b6c0-845265e30192/Manifest.mpd?src=emb
```

The Russian manifest exposed one AAC audio representation, not separate English/Russian tracks. Multiple sampled sermon positions were heard as English. The correct conclusion is therefore `Russian player / Russian interpretation not confirmed for that service`, **not** `yt-dlp selected the wrong language track` and not `there must be a hidden second audio track`.

Historical older Russian baseline:

```text
https://resi.media/GiHDtf/a19407ff-e767-4a17-87d0-f3758bd87bfe/Manifest.mpd?src=emb
```

Treat every old UUID only as evidence/baseline. The next service is expected to change.

## One-time browser setup

`resi watch` uses the optional Playwright read-only browser transport. On the canonical Windows checkout, install/update it once after pulling current `main`:

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
Set-Location $Repo
& $Python -m pip install -e ".[browser-read]"
if ($LASTEXITCODE -ne 0) { throw "browser-read install failed" }
& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium install failed" }
```

Do not create a second ad-hoc watcher Python/PowerShell implementation after the supported command exists.

## Legacy state migration after Issue #440

Watcher state is bound to the exact target page so an English/other Resi watch cannot silently become the Russian baseline. A pre-#440 `resi-watch-state.json` has no page owner and is deliberately rejected.

If a legacy state exists, preserve its last manifest through `latest-resi-manifest.txt`, then delete **only** the legacy state file before the first new run. Do not delete the latest manifest baseline.

```powershell
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$State = Join-Path $Repo "operator-output\resi-watch-state.json"
$Latest = Join-Path $Repo "operator-output\latest-resi-manifest.txt"
if (Test-Path -LiteralPath $State -PathType Leaf) {
    $StateJson = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
    if (-not $StateJson.target_page_identity) {
        if (-not (Test-Path -LiteralPath $Latest -PathType Leaf)) {
            throw "Legacy state exists but latest manifest baseline is missing; inspect before migration."
        }
        Remove-Item -LiteralPath $State -Force
        Write-Host "Legacy unscoped Resi state removed; latest manifest baseline preserved."
    }
}
```

## Future service: unattended Russian-page capture

For an overnight/unattended Windows run use the repository-owned `--background` mode. It launches a detached child watcher; that child owns Windows keep-awake while active, so the launching PowerShell window may be closed after the launch command returns.

The parent waits through a short startup grace check before reporting success. A returned PID therefore proves that the child launched and survived that initial check, but it still does **not** prove later liveness or capture success. Durable success is `latest-resi-manifest.json` / `latest-resi-manifest.txt`; diagnose the background log on failure.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$VM = Join-Path $Repo ".venv\Scripts\video-manager.exe"
$Latest = Join-Path $Repo "operator-output\latest-resi-manifest.txt"
$RussianPage = "https://www.gracechurch.org/live?language=russian"
$EnglishPage = "https://www.gracechurch.org/live?language=english"

$Args = @(
    "resi", "watch", $RussianPage,
    "--compare-page", $EnglishPage,
    "--timeout-seconds", "10800",
    "--poll-seconds", "30",
    "--probe-wait-seconds", "12",
    "--max-consecutive-probe-errors", "10",
    "--background"
)

if (Test-Path -LiteralPath $Latest -PathType Leaf) {
    $Known = (Get-Content -LiteralPath $Latest -Raw).Trim()
    if ($Known) { $Args += @("--known-manifest", $Known) }
}

& $VM @Args
if ($LASTEXITCODE -ne 0) { throw "Resi background watch launch failed" }
```

Default background evidence:

```text
operator-output\resi-watch-background.log
operator-output\resi-watch-background.pid
```

Success creates/updates:

```text
operator-output\latest-resi-manifest.txt
operator-output\latest-resi-manifest.json
operator-output\resi-watch-state.json
```

Capture/state JSON records target page identity, exact manifest, normalized source identity/fingerprint, Resi frame/player ID when observable, capture time, optional English comparison evidence, `language_claim=unverified`, and `full_download_dispatched=false`.

If the target page exposes multiple distinct Resi manifests in one probe, the watcher fails closed instead of guessing. If state belongs to another page or is corrupt/unscoped, the watcher fails closed. The finite three-hour timeout remains authoritative; the transient probe-error budget only prevents a short browser/network wobble from killing the whole watch immediately.

## Language preflight before FULL download

After a new Russian-page manifest is captured, create short audio-only samples:

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$VM = Join-Path $Repo ".venv\Scripts\video-manager.exe"
$Latest = Join-Path $Repo "operator-output\latest-resi-manifest.txt"
if (-not (Test-Path -LiteralPath $Latest -PathType Leaf)) { throw "No captured Resi manifest" }
$Source = (Get-Content -LiteralPath $Latest -Raw).Trim()
& $VM resi sample $Source
if ($LASTEXITCODE -ne 0) { throw "Resi language sample preflight failed" }
```

Default sample points are 00:30:00, 00:50:00, 01:10:00, and 01:30:00; each is 45 seconds and audio-only. Use them only when those positions already exist in the captured/live source. If the service is still earlier, choose already-existing sermon speech with repeated `--at`, or wait until suitable speech exists.

Before sampling, `resi sample` uses ffprobe and requires **exactly one audio stream at sample time**. If multiple audio streams are present, stop: explicit audio-format selection must be implemented/reviewed before language confirmation or FULL download.

Samples and `samples.json` stay under:

```text
operator-output\resi-language-samples\<source-derived-title>\
```

Listen to several points during sermon speech. The command deliberately does not pretend to classify Russian vs English.

Decision:

- Russian interpretation confirmed -> proceed to the guarded explicit handoff below.
- sermon samples remain English -> record `Russian player / no Russian interpretation detected` and stop; do not download another multi-GB copy looking for a nonexistent second track.
- samples are only music/hymns -> choose additional `--at` points during spoken sermon before deciding.
- multiple audio streams -> stop; do not assume `0:a:0` and `bestaudio` mean the same thing.

Example additional points:

```text
video-manager resi sample <MANIFEST> --at 40:00 --at 60:00 --at 80:00 --duration-seconds 45
```

## Explicit FULL download only after language confirmation

For Grace Russian language-confirmed work, generate the existing repository-owned handoff with `--require-single-audio`. This injects a second single-audio ffprobe gate **inside the generated handoff immediately before a new remote FULL download**, closing the gap where a live MPD could change after sampling.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$VM = Join-Path $Repo ".venv\Scripts\video-manager.exe"
$Latest = Join-Path $Repo "operator-output\latest-resi-manifest.txt"
$Handoff = Join-Path $Repo "operator-output\grace-russian-latest-handoff.ps1"
if (-not (Test-Path -LiteralPath $Latest -PathType Leaf)) { throw "No captured Resi manifest" }
$Source = (Get-Content -LiteralPath $Latest -Raw).Trim()
& $VM resi handoff $Source --require-single-audio --output $Handoff
if ($LASTEXITCODE -ne 0) { throw "Resi guarded handoff generation failed" }
& $Handoff
if ($LASTEXITCODE -ne 0) { throw "Resi guarded FULL download failed" }
```

The single-audio gate runs only before a **new remote download**; verified source-bound master reuse remains offline-safe. The generated handoff still prints `yt-dlp -F` evidence, downloads `bestvideo+bestaudio/best` with bounded fragment retries, performs ffprobe A/V/duration QC, calculates SHA-256, writes source/result receipts, and keeps the retained master in `C:\Users\Fedor\Downloads`. The watcher and sampler never auto-execute this step.

For generic Resi/DASH work where language identity is irrelevant, ordinary `resi handoff` remains unchanged and does not require the single-audio option.

## GPU clarification

Downloading DASH fragments is primarily network/server/storage work. GPU acceleration does not make the HTTP fragment transfer materially faster. Repository `--encoder auto` applies to **exact video re-encoding/trimming**: usable NVIDIA -> `h264_nvenc`; otherwise -> CPU `libx264`. Plain download/remux or `-c copy` does not use GPU transcoding.

## Stop conditions

Stop instead of improvising when the page is not the exact intended Grace language route; target capture has multiple distinct manifests; watcher state is corrupt, legacy-unscoped, or belongs to another page; the background child exits and its log shows an error; sermon samples do not confirm the desired language; multiple audio streams exist without an explicit selection contract; the guarded handoff's immediate pre-download single-audio check fails; access requires DRM/access-control bypass; or a FULL download is proposed before language preflight merely because the page says Russian.

## Agent handoff rule

A future agent must read this runbook plus Issues #425 and #440 before Resi live work. Chat history is supporting incident evidence, not the executable source of truth. The supported sequence is `watch -> sample -> explicit guarded handoff`, never `watch -> automatic multi-GB download`. For unattended Windows work use repository-owned `resi watch --background`, not a recreated hidden watcher pair.
