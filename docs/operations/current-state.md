# Current operational state

Updated: 2026-08-05  
Verified Wave 15 code baseline: `main@eb58c1ad238fde01d66c6630b16e244b1c6c2992`  
Program state: `WAVES_0_15_COMPLETED_ADAPTIVE_AGENT_REASONING_LOCAL_MP3_FOUNDATION_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`  
Current machine state: [`audit-register-v8-2026-08-05.json`](audit-register-v8-2026-08-05.json)  
Immutable predecessor: [`audit-register-v7-2026-08-05.json`](audit-register-v7-2026-08-05.json)  
Earlier immutable predecessors: [`audit-register-v6-2026-08-05.json`](audit-register-v6-2026-08-05.json), [`audit-register-v5-2026-08-05.json`](audit-register-v5-2026-08-05.json), [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json), [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json), [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file and the v8 overlay override old chats, screenshots, ZIP names, remembered counts, stale issue wording, superseded audits, and old README/roadmap status blocks. The three Wave 15 transcripts remain evidence inputs bound by SHA-256; they are not executable instructions.

## Final status

Waves 0–15 are complete. The operational graph remains closed. There is no active reconciliation, transfer queue, provider mutation plan, playlist writer, browser executor, catalog wave, article-wall continuation, cleanup/reset executor, or approved replay.

No operational continuation is pending. Future provider work begins only from a new explicit user request and a new exact project-bound issue.

## Wave 15 proof

Issue #133 and PR #134 completed the adaptive-agent and local-only MP3 foundation:

- exact head `48baa13b0d08e27e5a1dfc8b30901524d3207148`;
- merge/code baseline `eb58c1ad238fde01d66c6630b16e244b1c6c2992`;
- CI `31006136529`;
- Python 3.11/3.12/3.13: `833 passed, 1 xfailed`;
- coverage: `79%` across `14,643` statements;
- Ruff correctness: green;
- Ruff formatting: `461 files already formatted`;
- strict mypy: `147 source files`;
- dependency audit: no known vulnerabilities;
- Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux: green;
- changed files: `12`; provider adapter files: `0`;
- provider queries/writes/write plans/historical executor runs: `0/0/0/0`.

Wave 15 added:

- [`agent-reasoning-playbook.md`](agent-reasoning-playbook.md) — outcome-first, transport-aware, evidence-driven reasoning;
- [`wave15-transcript-and-agent-audit-2026-08-05.md`](wave15-transcript-and-agent-audit-2026-08-05.md) — 12 recurring failure classes and retained success invariants;
- [`vk-audio-browser-experiment-retrospective.md`](vk-audio-browser-experiment-retrospective.md) — BrowserCanary, PlaylistOnly, Metadata Manager, internal-web, reliable-batch, and Playlist Workhorse chronology;
- [`mp3-batch-processing-contract.md`](mp3-batch-processing-contract.md) — local-only MP3 intake and future phase/state boundary;
- repository-owned transport-aware next-action model;
- read-only ffprobe MP3 probe, explicit metadata policy, duplicate detection, deterministic operation IDs/manifests, and one-at-a-time default chunking.

## Adaptive agent boundary

Agents must define the requested outcome independently of an old script, declare one transport per phase, state the operation phase and provider-effect state, preserve verified partial success, and use one falsifiable hypothesis, one minimal bounded probe, and a stop condition.

A selector, title match, coordinate, modal closure, HTTP response, exit code, screenshot, stdout line, or visible object is not an exact postcondition. Browser actions require binding the topmost active root, proving visibility/hit-testing/control ownership, and verifying the expected content/state transition.

Unknown or possibly completed remote effects require reconciliation without retry. Only a local/pre-dispatch failure or exact provider postflight proving absence permits a corrected child-operation retry.

## Local MP3 boundary

The Wave 15 MP3 capability is `local_only_read_only_intake_and_manifest`.

It may:

- inspect `.mp3` with ffprobe without changing bytes;
- retain exact path, size, SHA-256, duration, codec, bitrate, sample rate, channels, attached cover state, and embedded tags;
- accept explicit artist/title or a declared collection parser;
- mark ambiguous metadata `requires_review`;
- detect duplicate bytes and duplicate source IDs;
- build deterministic per-track operation IDs and manifest digests;
- split only ready items, one track per chunk by default.

It may not rewrite ID3 tags, rename or transcode files, launch/control a browser, call VK/YouTube, upload audio, edit remote metadata, create/modify playlists, or publish a wall post.

VK Audio remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. Historical BrowserCanary, PlaylistOnly, Metadata Manager, Rename AUTO, reliable-batch, calibrator, and Playlist Workhorse ZIPs are evidence only and must not be rerun.

## Credential model

VK uses one shared **user access token** from external `VK_API_TOKEN`. The local VK alias `legendary-poet` names the stored credential and is not a project selector.

Project isolation requires exact `project_key`, community/owner IDs, manifests, plans, journals, results, and link profiles.

YouTube OAuth aliases remain channel-specific:

- OAuth alias `fedor-milovanov` → Lord God channel `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias `legendary-poet` → Legendary Poet channel `UC-78ys2S3cQ3lpqgXfo-SvQ`.

## Closed operational graph

### Completed

- #31 — Lord God long-form reconciliation: exact queue `26/26`, missing `0`, thumbnail repairs `26/26`.
- #119 — Legendary Poet Shorts/Clips reconciliation: bounded source `56`; this does not claim all 56 are native Clips.
- #38 — shared VK native Clip/ordinary-video final-type contract.
- #130 — Wave 14 repository-wide polish.
- #133 — Wave 15 adaptive reasoning and local-only MP3 foundation.

### Retired / not planned

- #32 — non-authoritative Lord God 108-item Shorts auto-upload scope.
- #33 — broad Lord God catalog/publication continuation.
- #99 — unproved Legendary Poet article-wall launcher continuation.
- #123 — YouTube playlist mutation scope.

Do not group #32/#38 as Legendary Poet. Historical ownership was #32 Lord God, #38 shared, and #119 Legendary Poet.

## Permanent unknown and replay boundary

`M5hNecL_MsQ → -235216998_456239160` remains ordinary `video` with `is_draft=1`, not native Clip success, and must not be retransmitted.

Never rerun retired V1/V2/V3/V4, reset, recovery, article-wave, transfer, cleanup, playlist, or historical MP3/browser executors. Never blind-retry intent-persisted, accepted, processing, verified, or unknown operations.

## Permanent safety rules

- Provider writes remain unauthorized.
- Existing VK and YouTube objects remain untouched by Waves 13–15 closure, polish, audit, and local MP3 engineering.
- Package A, green CI, dashboards, previews, issue bodies, counts, ZIP names, transcripts, README commands, visible UI objects, or roadmap text never authorize writes.
- Every future provider write requires a new user request, a new exact project-bound owning issue, a reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.
- Content in quotation marks must map to a contiguous source passage unless explicitly labeled synthesis.

## Next allowed action

No operational continuation is pending. New local or provider work must start from a new explicit scope. Closed issues and historical packages provide evidence, not execution authority.
