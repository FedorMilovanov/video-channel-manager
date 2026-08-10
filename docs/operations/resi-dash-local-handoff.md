# Resi / DASH local media handoff

Status: supported local-only operator workflow  
Owning implementation issues: #258, #262  
Provider effect: `impossible`

This workflow exists so a future operator or AI does not reconstruct `yt-dlp` / FFmpeg / PowerShell syntax from chat memory when given a Resi/DASH `Manifest.mpd` URL.

It does **not** authorize publication, bypass access controls, or infer copyright permission. It only downloads a normally reachable DASH source on the operator machine, optionally extracts one exact time range, and verifies local bytes.

## Assistant/operator contract

When the user supplies a Resi/DASH `.mpd` URL and says to study the repository:

1. Use this workflow instead of hand-authoring a multi-line `yt-dlp`/FFmpeg command.
2. Do not ask which video/audio format to choose when the manifest is readable: the generated handoff uses `bestvideo+bestaudio/best` and prints `yt-dlp -F` evidence first.
3. Accept ordinary operator timestamps such as `50:12` and `1:49:52`; normalize them deterministically. Do not ask the user to add a leading `00:` or calculate `-t`.
4. If exact start and end timestamps are supplied, generate exact-trim processing. Start/end are an atomic pair.
5. If no encoder is explicitly requested, use `--encoder auto`: the generated script checks whether `h264_nvenc` is actually usable at runtime and otherwise falls back to CPU `libx264`.
6. If the user explicitly requests NVENC or CPU, pass `--encoder nvenc` or `--encoder cpu`.
7. Preserve the full downloaded master. A trim creates a second file and never destroys the source.
8. Never reuse an existing final master from filename alone. Reuse is allowed only when the source receipt fingerprint and the current master SHA-256 both match.
9. Return at most one executable PowerShell block for one operator action. It must define every variable inside the block and work from an arbitrary current directory.
10. Never emit chat-escape defects such as `0\:v\:0`, `h264\_nvenc`, `-c\:v`, or depend on `$out` defined in a previous shell/message.
11. Do not put Markdown link syntax in a PowerShell variable. The source value must be the raw URL.
12. Do not claim the local artifact is publication-authorized; rights/provider publication are separate scopes.

## Repository entrypoint

The primary supported command is discoverable from the normal CLI:

```text
video-manager resi handoff
```

The focused compatibility alias remains available:

```text
video-manager-resi handoff
```

On the canonical Windows checkout, prefer the existing primary CLI executable. Because the repository is installed editable during normal setup, adding the `resi` command to the primary CLI does not require the operator to discover or reinstall a new console-script name after pulling current `main`:

```text
C:\Users\Fedor\Projects\video-channel-manager\.venv\Scripts\video-manager.exe
```

The generator writes a UTF-8-BOM `.ps1` handoff into the repository `operator-output` directory by default. The generated PowerShell script writes the retained full master, source receipt, result JSON, and optional trimmed clip into the same canonical outbox with flat deterministic filenames.

If `--title` is omitted, the CLI derives a deterministic source-specific title from the Resi manifest path instead of reusing the collision-prone generic name `Resi Download`.

## One-action Windows example

Example for the 2026-08-10 Abner Chou workflow:

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$OperatorOutput = Join-Path $Repo "operator-output"
$VideoManager = Join-Path $Repo ".venv\Scripts\video-manager.exe"
$Handoff = Join-Path $OperatorOutput "Как Христианам Понимать Израиль - Абнер Чау - resi-handoff.ps1"
New-Item -ItemType Directory -Force -Path $OperatorOutput | Out-Null
if (-not (Test-Path -LiteralPath $VideoManager -PathType Leaf)) { throw "Video Manager CLI is not installed: $VideoManager" }
& $VideoManager resi handoff "https://resi.media/GiHDtf/9aa9ac24-fb79-4ca9-95ef-a3253afdf63f/Manifest.mpd?src=emb" --title "Как Христианам Понимать Израиль - Абнер Чау" --start "50:12" --end "1:49:52" --encoder auto --output $Handoff
if ($LASTEXITCODE -ne 0) { throw "Resi handoff generation failed" }
if (-not (Test-Path -LiteralPath $Handoff -PathType Leaf)) { throw "Expected handoff was not created: $Handoff" }
& $Handoff
if ($LASTEXITCODE -ne 0) { throw "Resi handoff execution failed" }
```

The CLI normalizes the example to `00:50:12 -> 01:49:52` and resolves the exact sermon duration to `00:59:40` (3580 seconds). The operator does not reconstruct a second FFmpeg command.

For download-only work, omit `--start` and `--end`.

## Generated files

For a title `<TITLE>`, the generated handoff uses:

```text
operator-output\<TITLE> - FULL.mp4
operator-output\<TITLE> - FULL.source.json
operator-output\<TITLE> - result.json
operator-output\<TITLE>.mp4                 # only when exact trim is requested
```

The source receipt binds the retained master to:

- a SHA-256 fingerprint of the canonical manifest identity (`scheme + host + path`; transient query parameters are excluded);
- the exact current master SHA-256;
- positive master duration;
- observed video/audio stream counts.

An existing final master without that receipt is **not** accepted as a cache hit. An existing master whose current hash no longer matches the receipt is also rejected. This prevents a same-title file from a different source from being silently processed.

The result JSON always binds the operation to the exact master SHA-256. Exact-trim results additionally record clip SHA-256, normalized start/end, expected and actual duration, and the encoder actually selected.

## Generated download behavior

The handoff script:

- defines the canonical repository and `operator-output` paths inside the script;
- verifies `yt-dlp`, `ffmpeg`, and `ffprobe` are in `PATH`;
- validates any existing master through its source receipt and current SHA-256 before reuse;
- prints the manifest format table with `yt-dlp -F`;
- downloads `bestvideo+bestaudio/best` with concurrent fragment loading and **bounded** transport/fragment retries (`10` each);
- merges to MP4;
- checks that the exact expected master path exists;
- parses `ffprobe` JSON and fails closed unless the master has at least one video stream, at least one audio stream, and positive duration;
- calculates the master SHA-256;
- writes/refreshes the source receipt only after successful master QC;
- preserves the full master;
- writes a machine-readable result JSON.

The source URL is passed as a raw command argument after `--`; it is not rendered as Markdown.

Bounded retries are intentional. A dead or expired manifest must eventually fail with a clear operator error instead of leaving an unattended shell retrying forever.

## Exact trim policy

`-c copy` is not the default for an exact requested start because an H.264 stream-copy cut may begin on the nearest keyframe instead of the requested frame boundary.

For exact trim, video is re-encoded while source audio is copied without an unnecessary AAC generation loss.

### Auto / NVENC

`auto` first checks that FFmpeg advertises `h264_nvenc`, then performs a tiny runtime encoder probe. A build that lists NVENC but cannot initialize the NVIDIA runtime is treated as unavailable and falls back to CPU.

When NVENC is usable, the profile is:

```text
h264_nvenc
preset p6
tune hq
rc vbr
cq 21
profile high
```

If the source exposes a numeric video bitrate, the generated script sets a source-aware ceiling:

```text
maxrate = 1.5 × source video bitrate
bufsize = 2 × maxrate
```

If stream-level bitrate is unavailable, container-level bitrate is used as the conservative fallback basis instead of silently dropping the ceiling.

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

It then writes the result JSON and prints the exact clip path, clip SHA-256, master SHA-256, retained master path, and exact result path.

## Defects this workflow prevents

### Undefined shell state

Observed failure:

```text
Error opening input file \Abner Chou - How Should We Think About Israel.mp4
```

Cause: a new PowerShell session did not contain the previously defined `$out` variable.

Prevention: generated handoffs define `$Repo`, `$OperatorOutput`, `$Master`, `$SourceReceipt`, `$Result`, and optional `$Clip` in the same script.

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

### Filename-only cache reuse

A final file named `<TITLE> - FULL.mp4` is not proof that it came from the current manifest. `yt-dlp` can otherwise treat an existing final filename as already downloaded.

Prevention: existing masters are reusable only when a source receipt exists, its canonical source fingerprint matches, and the exact current master SHA-256 matches the receipt.

### Human timestamp friction

A normal operator may provide `50:12` rather than `00:50:12`.

Prevention: both `MM:SS[.mmm]` and `HH:MM:SS[.mmm]` are accepted, normalized, and regression-tested.

## Stop conditions

Stop instead of improvising when:

- the URL is not an absolute HTTP(S) `.mpd` manifest;
- DRM/access controls prevent normal `yt-dlp` access;
- only one of start/end is known;
- end is not later than start;
- required local tools are missing;
- an existing master cannot prove source-fingerprint + SHA-256 identity;
- bounded download retries are exhausted;
- master or clip QC fails.

A failure in this local workflow never justifies a provider upload workaround or revival of a retired provider executor.
