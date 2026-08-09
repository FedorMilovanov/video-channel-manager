# «Чёрный человек» — YouTube metadata refinement plan

Status: review/read-only planning. This document authorizes **zero provider writes**.

## Exact project identity

- project key: `legendary-poet`;
- OAuth alias: `legendary-poet`;
- channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- historical private target video under review: `x-puy27S2qs`;
- recorded media SHA-256: `e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0`.

The video ID/media hash are historical target evidence, not proof that current remote state is unchanged. Any future metadata plan must perform a fresh official-API read and prove the exact canonical `project_key + OAuth alias + channel_id` triple before credentials are used.

## Canonical copy inputs

- literary/body source: `content/youtube/legendary-poet/black-man-album-description-body.txt`;
- factual evidence: `docs/operations/black-man-youtube-description-sources.md`;
- formatting: `docs/youtube-description-rendering-standard.md`;
- authoring/handoff: `docs/youtube-copy-authoring-standard.md`;
- project identity: `docs/operations/project-identity-registry.md`.

There is intentionally **one** tracked body artifact. The stale `v2-final` / `v3-final` fork is not reproduced.

## Media-dependent chapter boundary

The body contains `[[CHAPTERS_FROM_EXACT_VERIFIED_TIMING]]` instead of hard-coded timestamps. That placeholder is a STOP marker, not publishable copy.

Before a final description plan can exist:

1. identify the exact target media bytes and their SHA-256;
2. bind the final accepted quality-master manifest used by the album pipeline;
3. load the exact final `timing.json`/render package corresponding to those bytes;
4. generate chapter lines from that timing evidence;
5. verify first chapter starts at `00:00`, chapter order is strict, every chapter lies within media duration, and the final target description contains no unresolved placeholder;
6. save the fully rendered description as immutable operator evidence outside the tracked body template;
7. only then perform a fresh read-only YouTube description preflight and freeze a digest-bound plan.

If the existing private video bytes do not match the current final render package, do not silently transplant timestamps between them. Treat media replacement/upload and metadata refinement as separate operations.

## Guarded metadata scope

A future separately authorized execution may change only `snippet.description` for the exact video. It must preserve title, tags, category, status/privacy, thumbnail and playlist membership, then verify the provider-visible description after the write.

The current description planner emits `provider_write_authorized=false`; current code therefore refuses execution even with a matching confirmation phrase. Enabling a provider mutation requires a new explicit user authorization and a separately reviewed authorization mechanism/plan; editing JSON by hand is invalid because it breaks the digest.

Provider reads/writes performed by this document: `0/0`.
