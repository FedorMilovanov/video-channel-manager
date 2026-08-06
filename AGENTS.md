# Repository agent instructions

This file is the entry contract for work in `FedorMilovanov/video-channel-manager`.

## Read first

1. `docs/operations/current-state.md`
2. `docs/operations/project-identity-registry.md`
3. `docs/operations/audit-register-v10-2026-08-06.json`
4. `docs/operations/vk-postponed-text-second-pass-audit-2026-08-06.md`
5. `docs/operations/vk-postponed-text-edit-runbook-2026-08-06.md`
6. `docs/operations/audit-register-v9-2026-08-05.json`
7. `docs/operations/agent-reasoning-playbook.md`
8. `docs/operations/operational-artifact-standard.md`
9. `docs/operations/operational-package-acceptance.md`
10. `docs/operations/local-credential-sources.md`
11. `docs/operations/retirement-registry-v1.json`
12. `.github/copilot-instructions.md`

`current-state.md` and the newest audit-register overlay override old chats, screenshots, ZIP names, remembered counts, stale issue wording, superseded audits, and historical scripts. Historical material teaches; it never authorizes execution.

## Current repository state

Baseline entering VK postponed-text hardening: `main@c0b8a303598788b2870862042d2e2868a97b3005`.

Production capability predecessor:

- issue #147;
- PR #150 exact head `0bfb1260c37411e8df686f26120ceea85e2f8116`;
- merge `c04f0a4f948174ced6287e4bae87e4bf1be2be52`.

Second-pass hardening authority:

- issue #152;
- PR #153;
- branch `agent/vk-postponed-text-audit-hardening`;
- repository-only work, no VK reads or writes, and no replay.

The completed 2026-08-06 Lord God cleanup remains verified:

- attachment-free postponed IDs `12513..12541`;
- `29/29` exact after-state;
- `0` pending;
- postponed count `66/66`;
- 37 non-target postponed rows unchanged;
- first published quote post untouched.

## Exact project and credential boundary

Two distinct projects exist:

- `lord-god-strength` — YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, owner `-60805374`;
- `legendary-poet` — YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, owner `-235216998`.

VK uses one shared user access token from external secret storage. The local VK alias `legendary-poet` names the credential; it is not a project selector. Exact project key, community/owner IDs, plans, journals, and results select the target.

Never print, copy, package, commit, log, request manual entry of, or place a token on a command line.

## VK postponed-text contract

The supported v1 surface is existing **attachment-free postponed wall posts only**.

Required controls:

- exact project/community/owner/post binding;
- sorted unique exact target IDs;
- complete published and postponed preflight;
- immutable request and plan digests;
- exact before/after text and publication dates;
- stable account/community lock independent of output directory;
- publication-distance check immediately before every dispatch and retry;
- intent journal before dispatch;
- exact live postflight;
- no blind retry;
- CAPTCHA stop without OCR, reconstruction, or bypass;
- terminal child journals consistent with aggregate result;
- final postponed-count and raw non-target fingerprint proof.

Schema v1 rejects every target attachment and rejects `allow_attachments=true`. Attachment support requires a future reviewed schema.

PowerShell may call only `scripts/Invoke-VkPostponedTextEdit.ps1`, which invokes the package CLI. PowerShell is not a second provider client.

Never rerun the completed cleanup plan or its historical local ZIP packages.

## Adaptive reasoning contract

Before implementation or handoff, state:

- requested outcome independently of an old mechanism;
- exact project, surface, and object type;
- transport for each phase: `local_only`, `official_api_read`, `official_api_write`, `internal_web_read`, `browser_ui_read`, or `browser_ui_write`;
- allowed and forbidden side effects;
- operation phase and provider-effect state;
- exact completion postcondition;
- one falsifiable hypothesis, one bounded probe, and a stop condition.

A timeout, exit code, HTTP success, selector match, click, modal closure, screenshot, visible title, playback state, or stdout line is not a provider postcondition.

Preserve partial success. Resume from the first unverified child operation. Unknown or possibly completed remote effects require read-only reconciliation and never authorize mutation replay.

After the first diagnostic workaround, patch repository-owned code and fixtures. Do not restart a ZIP/version treadmill.

## Browser and local-resource boundaries

Before every browser action, bind the topmost active page/modal, prove visibility and control ownership, capture before-state, perform one action, and verify exact remote postcondition.

One authenticated browser profile is a single-writer resource.

Local MP3 support remains read-only intake and manifest generation. It does not authorize ID3 rewrite, rename, transcode, browser control, VK Audio upload, metadata edit, playlist mutation, or publication.

VK Audio browser/internal-web experiments remain evidence only and are not core supported execution paths.

## Package and operational truth

Package A, a filename, ZIP, preview, issue body, confirmation prompt, dashboard, README command, green CI, or visible UI object never authorizes a provider mutation by itself.

Every provider mutation requires a new explicit user request, exact owning issue, reviewed immutable plan, expected remote delta, durable per-operation journals/results, and exact postflight.

Do not mix project identities, aliases, credentials, manifests, plans, journals, snapshots, or results.

Never infer absence from an endpoint that does not cover the relevant surface.

## Repository integrity

- Every tracked JSON file must parse.
- Local Markdown links must resolve.
- Time-dependent tests freeze or inject their clock.
- SQLite connections are explicitly closed; unclosed database warnings fail tests.
- GitHub Actions remain pinned by immutable SHA to Node 24-generation releases.
- Copy-paste PowerShell defines every variable, uses exact paths and `-LiteralPath`, enables strict/fail-fast behavior, and checks native exit codes.
- Never choose operational packages by `LastWriteTime`, broad wildcard, or inherited undefined variables.

## Historical dispositions

Completed:

- #31 — Lord God long-form reconciliation;
- #119 — Legendary Poet Shorts/Clips reconciliation;
- #38 — shared VK final-type contract;
- #130 — repository integrity polish;
- #133 — adaptive reasoning and local-only MP3 foundation;
- #137 — CI, SQLite, and MP3 identity hardening;
- #147 — initial guarded postponed-text capability and retrospective.

Retired or not planned:

- #32 — non-authoritative Lord God Shorts auto-upload scope;
- #33 — broad Lord God catalog/publication continuation;
- #99 — unproved Legendary Poet article-wall continuation;
- #123 — deferred YouTube playlist mutation scope.

`M5hNecL_MsQ → -235216998_456239160` remains ordinary `video` with `is_draft=1`, is not native Clip success, and must not be retransmitted.

## Branch, review, and merge discipline

Substantial work uses one `agent/{description}` branch and one focused PR. Do not create follow-up PRs when an existing owning PR can be updated cleanly.

Merge only after:

- exact expected head is unchanged;
- all six CI jobs are green on that head;
- changed scope is reviewed;
- no review thread remains open;
- documentation matches implemented capability;
- provider calls/writes during repository-only work are recorded accurately.

An infrastructure incident explains missing CI; it does not equal green CI.

Content in quotation marks must map to a contiguous source passage unless explicitly labeled synthesis.
