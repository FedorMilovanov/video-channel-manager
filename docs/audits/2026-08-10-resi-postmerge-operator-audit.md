# Resi/DASH post-merge operator audit — 2026-08-10

Scope: merged #259 / closed #258, audited from current-main baseline `484031aa17827cb1a7785470d105e866a086734b` before post-merge hardening.

Owning follow-up: #262.

Provider effect during audit/implementation: `impossible` / zero provider writes.

## Audit method

Checked the implementation against:

- `AGENTS.md`;
- `docs/operations/current-state.md`;
- `docs/operations/operator-output-handoff-rule.md`;
- `docs/operations/operational-artifact-standard.md`;
- `.github/copilot-instructions.md`;
- the actual 2026-08-10 Abner Chou Resi workflow and its observed PowerShell/FFmpeg defects;
- full repository CI surfaces, including Python 3.11/3.12/3.13 and PowerShell 5.1/7 jobs.

The audit intentionally treated green CI as necessary but not sufficient. The main questions were operator friction, stale-byte hazards, provenance, failure boundedness, shell serialization, discoverability, and whether a future agent could follow the repository without reconstructing chat history.

## Findings

### F1 — operator timestamps still required manual normalization

Severity: usability / repeat-defect risk.

The first implementation accepted only `HH:MM:SS[.mmm]`. A normal operator input such as `50:12` would fail even though that is exactly how sermon boundaries are commonly communicated.

Resolution: accept both `MM:SS[.mmm]` and `HH:MM:SS[.mmm]`; normalize internally. Regression includes `50:12 -> 00:50:12` and the real `50:12 -> 1:49:52 = 00:59:40` case.

### F2 — Resi was not discoverable from the established primary CLI

Severity: usability / repository-memory risk.

The first implementation added only `video-manager-resi`. A future operator already using `video-manager` would not discover the workflow from `video-manager --help`, and a newly added console-script name can require entrypoint metadata reinstall after a pull.

Resolution: mount the Resi Typer app at `video-manager resi`; retain `video-manager-resi` only as a focused compatibility alias.

### F3 — default title was collision-prone

Severity: correctness.

Omitting `--title` produced the generic `Resi Download`, so unrelated manifests could target the same final filename.

Resolution: derive a deterministic source-specific default title from the manifest path.

### F4 — filename-only existing-master reuse could silently process stale bytes

Severity: high correctness / provenance.

`yt-dlp` can regard an already-existing final output filename as downloaded. The first implementation had no proof that an existing `<TITLE> - FULL.mp4` belonged to the supplied manifest.

Resolution: introduce a source receipt. Existing final masters are reusable only when:

1. receipt exists;
2. canonical source fingerprint matches;
3. current master SHA-256 matches the receipt.

Anything else fails closed instead of silently using filename identity.

### F5 — trim result did not durably bind itself to the exact master hash

Severity: provenance.

The clip was hashed, but the retained master SHA-256 was not always carried into durable result evidence.

Resolution: master is always hashed after QC. Result JSON records exact master SHA-256; exact-trim results additionally record clip SHA-256, normalized timing, expected/actual duration, and selected encoder.

### F6 — master QC printed metadata but did not fail closed on missing streams

Severity: correctness.

The clip path checked A/V presence, but the retained master path only printed `ffprobe` output.

Resolution: parse master `ffprobe` JSON and require at least one video stream, one audio stream, and positive duration before receipt/result creation.

### F7 — infinite retries could turn a dead manifest into an unbounded shell hang

Severity: operator reliability.

`--retries infinite --fragment-retries infinite` is inappropriate for a self-contained handoff that is expected to fail clearly when a source is stale or inaccessible.

Resolution: bounded transport and fragment retries (`10` each) with explicit failure.

### F8 — NVENC source-aware ceiling could disappear when stream bitrate was absent

Severity: media-size regression risk.

The first version used only stream-level `bit_rate`. When absent, the rate ceiling disappeared even if container bitrate remained available.

Resolution: fall back to container-level bitrate as the conservative ceiling basis.

### F9 — NVENC compile-time presence was treated as runtime availability

Severity: portability.

An FFmpeg build may list `h264_nvenc` while the NVIDIA runtime/GPU cannot initialize it.

Resolution: `auto` performs a tiny runtime encode probe. Failed runtime initialization falls back to CPU; explicit `--encoder nvenc` fails clearly.

### F10 — current-state/README discoverability lagged the merged implementation

Severity: future-agent/repository UX.

The authoritative repository surfaces did not yet explain that Resi/DASH local video was supported.

Resolution: current-state, runbook, README and CLI inventory are updated as part of #262.

### F11 — tests asserted rendered strings but not PowerShell parser acceptance

Severity: serialization regression risk.

Python tests could prove that bad `\:` / `\_` strings were absent, but not that the complete generated `.ps1` is syntactically accepted by the PowerShell environments that operators use.

Resolution: add a Pester regression that invokes `video-manager resi handoff`, generates the UTF-8-BOM handoff, and parses it with `System.Management.Automation.Language.Parser`. The existing CI matrix exercises this under Windows PowerShell 5.1, PowerShell 7 on Windows, and PowerShell 7 on Linux.

## Expected post-hardening operator behavior

A future agent given only a Resi `.mpd` URL may use a source-derived title without asking the operator for one. If the operator supplies a title and boundaries such as `50:12–1:49:52`, the repository normalizes timing, generates one exact handoff, inspects/downloads the best A/V representation, preserves and hashes the master, performs exact trim/QC when requested, and writes source/result evidence under canonical `operator-output`.

The assistant/operator is not expected to reconstruct format IDs, calculate duration, repair Markdown escape damage, preserve prior shell variables, or decide whether a same-name master is trustworthy.

## Completion gate

This audit is repository-complete only after #262 has:

- exact-current-head full CI green;
- PowerShell parser regression green in all three PowerShell jobs;
- Python format/type/test gates green;
- source-of-truth documentation updated;
- reviewed diff with zero provider effects;
- merge into current `main`.
