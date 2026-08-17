# Resi / DASH local media handoff

Status: supported local-only operator workflow  
Owning implementation issues: #258, #262, #427  
Provider effect: `impossible`

This workflow exists so a future operator or AI does not reconstruct `yt-dlp` / FFmpeg / PowerShell syntax from chat memory when given a Resi/DASH `Manifest.mpd` URL.

It does **not** authorize publication, bypass access controls, or infer copyright permission. It downloads a normally reachable DASH source on the operator machine, optionally extracts one exact time range, and verifies local bytes.

## Assistant/operator contract

When the user supplies a Resi/DASH `.mpd` URL and says to study the repository:

1. Use this workflow instead of hand-authoring a multi-line `yt-dlp`/FFmpeg command.
2. Do not ask which video/audio format to choose when the manifest is readable: first download uses `bestvideo+bestaudio/best` and prints `yt-dlp -F` evidence.
3. Accept ordinary operator timestamps such as `50:12` and `1:49:52`; normalize them deterministically. Do not ask the user to add a leading `00:` or calculate `-t`.
4. Start/end are an atomic pair. If both are supplied, generate exact-trim processing.
5. If no encoder is explicitly requested, use `--encoder auto`: runtime-probe `h264_nvenc`, otherwise fall back to CPU `libx264`.
6. Preserve the full downloaded master in canonical Windows Downloads: `C:\Users\Fedor\Downloads\<TITLE> - FULL.mp4`. A trim creates a second file and never destroys the source.
7. Keep Resi provenance/control artifacts in repository `operator-output`: source receipt JSON, result JSON, generated handoff/watcher files, logs/state, and exact-trim output unless the user explicitly requests another destination.
8. Never trust an existing final master from filename alone. Reuse requires a matching source receipt and current master SHA-256.
9. Once that provenance is proved, reuse is **offline-safe**: do not require the original manifest to remain reachable merely to re-trim the retained master.
10. Return at most one executable PowerShell block for one operator action. It must define every variable inside the block and work from an arbitrary current directory.
11. Never emit chat-escape defects such as `0\:v\:0`, `h264\_nvenc`, `-c\:v`, or depend on `$out` defined in a previous shell/message.
12. Do not put Markdown link syntax in a PowerShell variable. The source value must be the raw URL.
13. Do not claim the local artifact is publication-authorized; rights/provider publication are separate scopes.

## Repository entrypoint

Primary command:

```text
video-manager resi handoff
```

Focused alias retained:

```text
video-manager-resi handoff
```

On the canonical Windows checkout, prefer:

```text
C:\Users\Fedor\Projects\video-channel-manager\.venv\Scripts\video-manager.exe
```

Because `video-manager` is the established editable-install entrypoint, adding the `resi` subcommand does not require the operator to discover a new executable name after pulling current code.

The generator writes a UTF-8-BOM `.ps1` handoff into canonical `operator-output`. The generated PowerShell script defaults to:

```text
Repository root: C:\Users\Fedor\Projects\video-channel-manager
Downloads root:  C:\Users\Fedor\Downloads
```

For CI/testing or an intentionally different checkout/destination, the generated handoff accepts optional `-RepositoryRoot` and `-DownloadsRoot`; ordinary operator use does not need to pass either one.

If `--title` is omitted, the CLI derives a deterministic source-specific title from the manifest path instead of using collision-prone `Resi Download`.

## One-action Windows example

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

The CLI normalizes this real case to `00:50:12 -> 01:49:52` and resolves `00:59:40` (3580 seconds). The operator does not reconstruct a second FFmpeg command.

For download-only work, omit `--start` and `--end`.

## Generated files

For `<TITLE>` on the canonical Windows machine:

```text
C:\Users\Fedor\Downloads\<TITLE> - FULL.mp4
operator-output\<TITLE> - FULL.source.json
operator-output\<TITLE> - result.json
operator-output\<TITLE>.mp4                 # exact trim only
```

This split is deliberate: the potentially multi-gigabyte retained master belongs in Downloads, while compact provenance/control evidence stays with repository operator output. Generated watcher scripts, manifest capture state and logs also stay in `operator-output`.

The source receipt binds the retained master to:

- exact master path (including the Downloads destination);
- source fingerprint;
- exact current master SHA-256;
- positive master duration;
- observed video/audio stream counts.

The result JSON always binds the operation to the exact master path and SHA-256. Exact-trim results additionally record clip SHA-256, normalized start/end, expected/actual duration, and selected encoder.

## Source identity policy

Resi recording paths contain a stable source identifier while query values such as embed/access context may rotate. For `resi.media` and its subdomains, source identity therefore uses normalized scheme + host + path and excludes the query.

For **generic non-Resi DASH URLs**, the query is retained in source identity. This prevents two potentially content-selecting URLs such as:

```text
https://media.example/video/Manifest.mpd?variant=a
https://media.example/video/Manifest.mpd?variant=b
```

from being treated as one source merely because their paths match.

The source identity is stored only as SHA-256 in the receipt/result; it is not a substitute for the exact master SHA-256.

## First download behavior

When no proven reusable master exists, the generated handoff:

- creates/uses the selected Downloads root for the retained master and repository `operator-output` for provenance/control files;
- verifies `yt-dlp`, `ffmpeg`, and `ffprobe` are available;
- prints `yt-dlp -F` evidence;
- downloads `bestvideo+bestaudio/best`;
- uses concurrent fragment loading;
- uses bounded transport/fragment retries (`10` each), not infinite retry;
- merges to MP4;
- parses `ffprobe` JSON;
- requires at least one video stream, one audio stream, and positive duration;
- calculates master SHA-256;
- writes the source receipt only after successful QC;
- writes machine-readable result evidence.

A dead or expired source eventually fails clearly instead of leaving an unattended shell retrying forever.

## Existing-master reuse

If `<DownloadsRoot>\<TITLE> - FULL.mp4` already exists, the handoff does **not** let `yt-dlp` decide cache identity from the filename.

It first requires `operator-output\<TITLE> - FULL.source.json`, then checks:

1. receipt source fingerprint equals the handoff source fingerprint;
2. current Downloads master SHA-256 equals the receipt master SHA-256.

Missing/mismatched evidence fails closed. A proven master is then re-probed and re-hashed before result production.

When those checks pass, remote format inspection and download are skipped. This intentionally allows later exact trims from the retained master even if the original Resi URL has expired or the machine is temporarily offline.

## Exact trim policy

H.264 stream-copy is not the default for an exact requested start because it may begin at a nearby keyframe. Exact trim re-encodes video while copying the source audio stream without an unnecessary AAC generation loss.

### Auto / NVENC

`auto` first checks whether FFmpeg advertises `h264_nvenc`, then performs a tiny runtime encode probe. A build that lists NVENC but cannot initialize the NVIDIA runtime/GPU is treated as unavailable.

Usable NVENC profile:

```text
h264_nvenc
preset p6
tune hq
rc vbr
cq 21
profile high
```

If source video bitrate is numeric:

```text
maxrate = 1.5 × source video bitrate
bufsize = 2 × maxrate
```

If stream bitrate is absent, container bitrate is used as the conservative fallback basis instead of silently dropping the ceiling.

The policy is based on the 2026-08-10 real Resi run: NVENC `P6/CQ18` processed the 59:40 clip at about `7.11x` realtime but inflated it to about 4.75 GiB / 11.1 Mbit/s from a roughly 4.25 Mbit/s H.264 source. `CQ21` plus the source-aware ceiling avoids spending bits that cannot restore absent source detail.

### CPU fallback

```text
libx264
preset slow
crf 18
profile high
```

In the same workflow CPU `libx264 slow CRF18` produced about 2.88 GiB but ran around `1.44x` realtime. CPU is therefore the compression-efficient fallback and NVENC the speed-oriented default on a capable machine.

Source audio remains `-c:a copy` during exact trim.

## Post-trim QC

The handoff fails closed unless:

- expected output exists;
- `ffprobe` succeeds;
- video stream exists;
- audio stream exists;
- actual duration is within 0.25 seconds of deterministic expected duration.

It then writes result JSON and prints clip SHA-256, master SHA-256, retained master path, duration, and result path.

## CI proof

The repository does not rely only on Python string assertions.

Pester CI:

- generates the actual UTF-8-BOM handoff through `video-manager resi handoff`;
- parses it with `System.Management.Automation.Language.Parser`;
- executes the generated script end-to-end against provider-free `yt-dlp`/`ffmpeg`/`ffprobe` tool doubles;
- injects an isolated Downloads root and proves the full master is created there, not in `operator-output`;
- proves source receipt, result JSON and exact trim remain in `operator-output`;
- proves master/clip SHA evidence and JSON receipts bind the actual split paths;
- proves exact `50:12 -> 1:49:52` normalization/result duration;
- proves CPU fallback control flow;
- runs the handoff a second time and proves the verified Downloads master is reused without another remote inspection/download.

The repository's PowerShell matrix runs these tests in Windows PowerShell 5.1, PowerShell 7 on Windows, and PowerShell 7 on Linux. Python CI additionally covers timestamp validation, source identity, title safety, CLI integration, rendering and provenance guards.

## Defects explicitly prevented

Observed/reviewed failure classes now covered include:

- undefined previous-session `$out` producing paths such as `\Abner Chou...mp4`;
- chat/Markdown escapes such as `0\:v\:0`, `-c\:v`, `h264\_nvenc`;
- fragile multiline backtick paste causing FFmpeg argument shifts;
- assuming one combined Resi format when video/audio are separate;
- wasteful AAC up-bitrate;
- generic `Resi Download` filename collisions;
- same-name stale master reuse;
- master without A/V proof;
- accidental accumulation of multi-gigabyte retained `FULL.mp4` masters inside repository `operator-output`;
- unbounded retry on dead manifest;
- compile-time-only NVENC detection;
- loss of bitrate ceiling when stream-level bitrate is absent;
- forcing the operator to rewrite `50:12` as `00:50:12`;
- forcing a network recheck when a retained master has already proved source + SHA identity.

## Stop conditions

Stop instead of improvising when:

- URL is not an absolute HTTP(S) `.mpd` manifest;
- normal `yt-dlp` access is blocked by DRM/access controls;
- only one of start/end is known;
- end is not later than start;
- required local tools are missing;
- an existing master cannot prove source-fingerprint + SHA-256 identity;
- bounded download retries are exhausted;
- master or clip QC fails.

A failure in this local workflow never justifies a provider upload workaround or revival of a retired provider executor.
