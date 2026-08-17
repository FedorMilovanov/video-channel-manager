# Grace Church Russian Resi live capture

Status: supported local-only workflow after Issue #425 implementation is merged to `main`  
Owning issue: #425  
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

Never collapse 1–3 into claim 4.

A hymn, intro, room audio, or a Russian player carrying house English can all sound English. Conversely, one English hymn is not proof that sermon interpretation is absent. Verify multiple sermon speech points before deciding.

## 2026-08-17 incident evidence — historical, not current routing

The following values explain the defect class and are **not** forever-current manifests:

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

`resi watch` uses the optional Playwright read-only browser transport. On the canonical Windows checkout, install/update it once after pulling a `main` that includes Issue #425:

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

Do not create a second ad-hoc watcher Python file after this supported command exists.

## Future service: capture the new Russian-page manifest

This block is safe to reuse next week. It uses the last captured manifest as the baseline when present, compares the contemporaneous English page, keeps Windows awake while the supported watcher is active, and does **not** start a multi-gigabyte download.

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
    "--probe-wait-seconds", "12"
)

if (Test-Path -LiteralPath $Latest -PathType Leaf) {
    $Known = (Get-Content -LiteralPath $Latest -Raw).Trim()
    if ($Known) {
        $Args += @("--known-manifest", $Known)
    }
}

& $VM @Args
if ($LASTEXITCODE -ne 0) { throw "Resi watch failed" }
```

Success creates/updates:

```text
operator-output\latest-resi-manifest.txt
operator-output\latest-resi-manifest.json
operator-output\resi-watch-state.json
```

The JSON records target page, final page, exact manifest, normalized source identity/fingerprint, Resi frame/player ID when observable, capture time, optional English comparison evidence, `language_claim=unverified`, and `full_download_dispatched=false`.

If the target page exposes multiple distinct Resi manifests in one probe, the watcher fails closed instead of guessing which one is Russian.

If the state file is corrupt, the watcher fails closed rather than silently forgetting what it already captured.

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

Default sample points are:

```text
00:30:00
00:50:00
01:10:00
01:30:00
```

Each is 45 seconds and audio-only. Samples and `samples.json` stay under:

```text
operator-output\resi-language-samples\<source-derived-title>\
```

Listen to several points during sermon speech. The command deliberately does not pretend to classify Russian vs English.

Decision:

- Russian interpretation confirmed -> proceed to explicit `resi handoff` full download.
- sermon samples remain English -> record `Russian player / no Russian interpretation detected` and stop; do not download another multi-GB copy looking for a nonexistent second track.
- samples are only music/hymns -> choose additional `--at` points during spoken sermon before deciding.

Example additional points:

```text
video-manager resi sample <MANIFEST> --at 40:00 --at 60:00 --at 80:00 --duration-seconds 45
```

## Explicit FULL download only after language confirmation

Use the existing repository-owned handoff. Do not replace it with hand-written `ffmpeg -i Manifest.mpd` or a second downloader.

The generated handoff:

- prints `yt-dlp -F` evidence;
- downloads `bestvideo+bestaudio/best` with bounded fragment retries;
- performs ffprobe A/V/duration QC;
- calculates SHA-256;
- writes source/result receipts;
- keeps the retained master in `C:\Users\Fedor\Downloads`.

The watcher and sampler never auto-execute this step.

## GPU clarification

Downloading DASH fragments is primarily network/server/storage work. GPU acceleration does not make the HTTP fragment transfer materially faster.

Repository `--encoder auto` applies to **exact video re-encoding/trimming**:

- usable NVIDIA -> `h264_nvenc`;
- otherwise -> CPU `libx264` fallback.

A plain download/remux or `-c copy` does not become faster merely by selecting the RTX GPU.

## Stop conditions

Stop instead of improvising when:

- the page is not the exact intended Grace language route;
- target capture has multiple distinct Resi manifests and ownership is ambiguous;
- watcher state is corrupt/unreadable;
- Playwright/browser dependencies cannot start after bounded attempts;
- the captured manifest belongs only to the English comparison page, not the target Russian page;
- sermon speech samples do not confirm the desired language;
- the manifest exposes only one audio representation: do not invent a hidden language track;
- access requires DRM/access-control bypass;
- full download is being proposed before language preflight merely because the page says Russian.

## Agent handoff rule

A future agent must read this runbook and Issue #425 before Resi live work. Chat history is supporting incident evidence, not the executable source of truth. The supported sequence is `watch -> sample -> explicit handoff`, never `watch -> automatic multi-GB download`.
