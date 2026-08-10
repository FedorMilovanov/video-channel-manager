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
- full repository CI surfaces: Python 3.11/3.12/3.13 and PowerShell 5.1/7.

Green CI was treated as necessary but not sufficient. The audit explicitly examined operator friction, shell-state dependence, stale-byte hazards, provenance, retry boundedness, source identity, offline continuation, runtime encoder availability, serialization, discoverability, and whether a future agent can use repository truth instead of chat memory.

## Findings and dispositions

### F1 — operator timestamps required manual normalization

Severity: usability / repeat-defect risk.

Initial support accepted only `HH:MM:SS[.mmm]`; natural operator input `50:12` failed.

**Disposition:** accept `MM:SS[.mmm]` and `HH:MM:SS[.mmm]`, normalize internally. The real regression is `50:12 -> 1:49:52 = 00:59:40`.

### F2 — Resi was not discoverable from the established primary CLI

Severity: usability / repository-memory risk.

Initial support added only `video-manager-resi`. Existing operators naturally discover functionality through `video-manager`.

**Disposition:** mount the same Typer app at `video-manager resi`; keep `video-manager-resi` only as a focused alias.

### F3 — default title was collision-prone

Severity: correctness.

Omitting `--title` produced generic `Resi Download`.

**Disposition:** derive a deterministic source-specific default title from the manifest path.

### F4 — filename-only existing-master reuse could silently process stale bytes

Severity: high correctness / provenance.

`yt-dlp` can treat an already-existing final output filename as downloaded. A filename did not prove source identity.

**Disposition:** introduce source receipt; existing master reuse requires matching source fingerprint and current master SHA-256. Missing/mismatched evidence fails closed.

### F5 — trim result did not durably bind to exact master hash

Severity: provenance.

Clip hash existed, but durable result evidence did not always bind the clip to exact master bytes.

**Disposition:** always hash master after QC. Result JSON records exact master SHA-256; trim results also record clip SHA-256, normalized timing, expected/actual duration and selected encoder.

### F6 — master QC printed metadata but did not fail closed on missing streams

Severity: correctness.

Initial master path printed `ffprobe` output but only the clip path enforced A/V presence.

**Disposition:** parse master `ffprobe` JSON; require video, audio and positive duration before receipt/result creation.

### F7 — infinite retries could create an unbounded shell hang

Severity: operator reliability.

`--retries infinite --fragment-retries infinite` could leave a dead/stale manifest retrying indefinitely.

**Disposition:** bounded transport and fragment retries (`10` each) with explicit failure.

### F8 — NVENC source-aware ceiling disappeared when stream bitrate was absent

Severity: media-size regression risk.

Initial implementation used only stream-level `bit_rate`.

**Disposition:** use container bitrate as conservative fallback when stream bitrate is unavailable.

### F9 — NVENC listing was treated as runtime availability

Severity: portability.

An FFmpeg build can list `h264_nvenc` even when the NVIDIA runtime/GPU cannot initialize it.

**Disposition:** `auto` performs a tiny runtime encode probe. Failure falls back to CPU; explicit `--encoder nvenc` fails clearly.

### F10 — current-state/README discoverability lagged implementation

Severity: future-agent/repository UX.

Authoritative repository surfaces did not expose the newly supported local-video workflow.

**Disposition:** update README, current-state, runbook and CLI inventory.

### F11 — tests checked rendered strings but not PowerShell parser acceptance

Severity: serialization regression risk.

Python tests could reject known `\:` / `\_` corruption without proving that the complete generated `.ps1` parses on operator PowerShell versions.

**Disposition:** Pester generates the actual handoff and parses it with `System.Management.Automation.Language.Parser` in the repository PowerShell matrix.

### F12 — generated handoff was difficult to execute safely in hermetic CI

Severity: testability / portability.

The generated script hardcoded the canonical Windows repository root with no override, making full control-flow execution in Linux/temporary CI workspaces impractical.

**Disposition:** generated handoff now has optional `-RepositoryRoot`, defaulting to the canonical Windows checkout. Ordinary users provide nothing; CI can execute the exact same script in `$TestDrive` without text-rewriting it.

### F13 — generic DASH query variants could collide if every query were discarded

Severity: source-identity correctness.

For Resi, path identity is stable while embed/access query context may rotate. Extending that assumption to arbitrary DASH URLs would be unsafe because `?variant=a` and `?variant=b` may select different content.

**Disposition:** Resi host/subdomain source identity excludes transient query; generic non-Resi DASH identity preserves query. Receipt stores only the resulting SHA-256 identity, not a replacement for master SHA-256.

### F14 — proven master still depended on live source reachability

Severity: operator UX / recovery.

Initial hardened flow validated receipt+SHA but then still ran `yt-dlp -F`. An expired Resi URL therefore blocked re-trimming an already proven retained master.

**Disposition:** once receipt fingerprint and current master SHA-256 match, remote inspection/download are skipped. Master is still re-probed/re-hashed locally. This makes later trim work offline-safe without weakening byte identity.

### F15 — parser-only CI still did not prove generated control flow

Severity: integration confidence.

A syntactically valid script can still have broken path, receipt, hashing, branch or reuse logic.

**Disposition:** Pester additionally executes the generated handoff end-to-end using provider-free `yt-dlp`, `ffmpeg`, and `ffprobe` tool doubles. It proves:

- initial format-inspection branch;
- fake master creation;
- master A/V/duration QC;
- source receipt + master SHA-256;
- CPU fallback branch;
- exact fake trim + clip SHA-256;
- result JSON timing/provenance;
- second-run master reuse;
- no second remote inspection/download on verified reuse.

This test is intentionally provider-free and network-free.

## Expected post-hardening operator behavior

A future agent given only a Resi `.mpd` URL can derive a collision-resistant title and generate the supported handoff without asking format/encoder/path questions. If the operator supplies a human title and boundaries such as `50:12–1:49:52`, repository code normalizes timing, downloads best A/V when needed, preserves/hashes the master, performs exact trim/QC, and writes source/result evidence under canonical `operator-output`.

If that retained master later has a valid source receipt and unchanged SHA-256, the same handoff can re-trim it without the source remaining online.

The operator is not expected to reconstruct format IDs, calculate duration, repair Markdown escapes, preserve prior shell variables, decide whether a same-name master is trustworthy, or manually distinguish compile-time from runtime NVENC availability.

## Completion gate

This audit is repository-complete only after #262 has:

- exact-current-head full CI green;
- PowerShell parser + executable provider-free handoff regressions green in all three PowerShell jobs;
- Python format/type/test gates green;
- source-of-truth documentation updated;
- reviewed diff with zero provider effects;
- merge into current `main`.
