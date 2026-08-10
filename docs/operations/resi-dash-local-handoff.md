# Resi / DASH local media handoff

Status: supported local-only operator workflow  
Owning issue: #258  
Provider effect: `impossible`

This workflow exists so a future operator or AI does not reconstruct `yt-dlp` / FFmpeg / PowerShell syntax from chat memory when given a Resi/DASH `Manifest.mpd` URL.

It does **not** authorize publication, bypass access controls, or infer copyright permission. It only downloads an openly reachable DASH manifest on the operator machine, optionally extracts one exact time range, and verifies local bytes.

## Assistant/operator contract

When the user supplies a Resi/DASH `.mpd` URL and says to study the repository:

1. Use this workflow instead of hand-authoring a multi-line `yt-dlp`/FFmpeg command.
2. Do not ask which video/audio format to choose when the manifest is readable: the generated handoff uses `bestvideo+bestaudio/best` and prints `yt-dlp -F` evidence first.
3. If exact start and end timestamps are supplied, calculate the duration deterministically and generate exact-trim processing. Do not ask the user to calculate `-t`.
4. If no encoder is explicitly requested, use `--encoder auto`: the generated script detects `h264_nvenc`; if present it uses the reviewed NVENC profile, otherwise it falls back to CPU `libx264`.
5. If the user explicitly requests NVENC or CPU, pass `--encoder nvenc` or `--encoder cpu`.
6. Preserve the full downloaded master. A trim must create a second file, never destroy the source.
7. Return at most one executable PowerShell block. It must define every variable inside the block and must work from an arbitrary current directory.
8. Never emit chat-escape defects such as `0\:v\:0`, `h264\_nvenc`, `-c\:v`, or depend on `$out` defined in a previous shell/message.
9. Do not put Markdown link syntax in a PowerShell variable. The source value must be the raw URL.
10. Do not claim the local artifact is publication-authorized; rights/provider publication are separate scopes.

## Repository entrypoint

Canonical Windows entrypoint:

```text
C:\Users\Fedor\Projects\video-channel-manager\scripts\resi_dash_handoff.py
```

The generator writes a UTF-8-BOM `.ps1` handoff into the repository `operator-output` directory by default. The generated PowerShell script also writes the retained full master and optional trimmed clip into that same canonical operator outbox, using flat deterministic filenames.

Example for the 2026-08-10 Abner Chou workflow:

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$OperatorOutput = Join-Path $Repo "operator-output"
$Handoff = Join-Path $OperatorOutput "Как Христианам Понимать Израиль - Абнер Чау - resi-handoff.ps1"
New-Item -ItemType Directory -Force -Path $OperatorOutput | Out-Null
& py -3.11 "$Repo\scripts\resi_dash_handoff.py" handoff "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd?src=emb" --title "Как Христианам Понимать Израиль - Абнер Чау" --start "00:50:12" --end "01:49:52" --encoder auto --output $Handoff
if ($LASTEXITCODE -ne 0) { throw "Resi handoff generation failed" }
if (-not (Test-Path -LiteralPath $Handoff -PathType Leaf)) { throw "Expected handoff was not created: $Handoff" }
Write-Host "RUN THIS FILE: $Handoff"
```

This example resolves the exact sermon duration to `00:59:40` (3580 seconds). The next operator action is one invocation of the exact generated `.ps1`; no command reconstruction is required.

For download-only work, omit `--start` and `--end`. They are an atomic pair: supplying only one is rejected.

## Generated download behavior

The handoff script:

- defines the canonical repository and `operator-output` paths inside the script;
- verifies `yt-dlp`, `ffmpeg`, and `ffprobe` are in `PATH`;
- prints the manifest format table with `yt-dlp -F`;
- downloads `bestvideo+bestaudio/best` with concurrent fragment loading and infinite transport/fragment retries;
- merges to MP4;
- checks that the exact expected master path exists;
- runs `ffprobe` over duration, size, bitrate, video dimensions/codecs and audio metadata;
- preserves the full master;
- calculates SHA-256.

The source URL is passed as a raw command argument after `--`; it is not rendered as Markdown.

## Exact trim policy

`-c copy` is not the default for an exact requested start because an H.264 stream-copy cut may begin on the nearest keyframe instead of the requested frame boundary.

For exact trim, video is re-encoded while source audio is copied without an unnecessary AAC generation loss.

### Auto / NVENC

When `h264_nvenc` exists, `auto` uses:

```text
h264_nvenc
preset p6
tune hq
rc vbr
cq 21
profile high
```

If the source exposes a numeric video bitrate, the generated script also sets a source-aware ceiling:

```text
maxrate = 1.5 × source video bitrate
bufsize = 2 × maxrate
```

This is intentional. In the 2026-08-10 real Resi test, NVENC `P6/CQ18` processed a 59:40 clip at about `7.11x` realtime but inflated it to about 4.75 GiB / 11.1 Mbit/s from a roughly 4.25 Mbit/s H.264 source. `CQ21` plus a source-aware rate ceiling avoids treating a low-bitrate source as if extra encoded bits could recreate detail that is not present.

### CPU fallback

When NVENC is unavailable, or `--encoder cpu` is selected:

```text
libx264
preset slow
crf 18
profile high
```

In the same real workflow, CPU `libx264 slow CRF18` produced a materially smaller result (about 2.88 GiB) but ran around `1.44x` realtime. The workflow therefore treats CPU as the compression-efficient fallback and NVENC as the speed-oriented default on capable machines.

## Post-trim QC

The generated script fails closed unless:

- the expected output file exists;
- `ffprobe` succeeds;
- at least one video stream exists;
- at least one audio stream exists;
- actual duration is within 0.25 seconds of the deterministic expected duration.

It then prints the exact clip path, duration, SHA-256, and retained full-master path.

## Defects this workflow prevents

### Undefined shell state

Observed failure:

```text
Error opening input file \Abner Chou - How Should We Think About Israel.mp4
```

Cause: a new PowerShell session did not contain the previously defined `$out` variable.

Prevention: generated handoffs define `$Repo`, `$OperatorOutput`, `$Master`, and `$Clip` in the same script.

### Markdown/chat escaping in commands

Observed malformed tokens included:

```text
0\:v\:0
-c\:v
h264\_nvenc
-b\:a
```

These are not PowerShell/FFmpeg syntax. They were rendering/serialization artifacts.

Prevention: the generator owns literal command rendering; the operator never repairs escaped punctuation manually.

### Broken PowerShell continuation

Observed multi-line backtick pastes caused FFmpeg to interpret `-t` as an input filename.

Prevention: generated `.ps1` uses PowerShell argument arrays for the complicated FFmpeg invocation and does not rely on fragile chat line continuations.

### Wrong format assumption

A Resi MPD may expose separate video-only and audio-only streams. In the real example, 1080p video and AAC audio were separate representations.

Prevention: the handoff prints the format table for evidence and downloads `bestvideo+bestaudio/best` instead of assuming one combined format ID.

### Wasteful audio up-bitrate

The real source audio was approximately 126 kbit/s AAC. Re-encoding it to 192 kbit/s cannot restore information and introduces another lossy generation.

Prevention: exact-trim processing copies the existing audio stream.

## Stop conditions

Stop instead of improvising when:

- the URL is not an absolute HTTP(S) `.mpd` manifest;
- DRM/access controls prevent normal `yt-dlp` access;
- only one of start/end is known;
- end is not later than start;
- required local tools are missing;
- generated QC fails.

A failure in this local workflow never justifies a provider upload workaround or revival of a retired provider executor.
