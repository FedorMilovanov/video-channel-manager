# Windows handoff contract for repository agents

These instructions supplement the repository-root `AGENTS.md`. `AGENTS.md`, `docs/operations/current-state.md`, the machine audit register, the retirement registry, and the exact owning issue remain authoritative. This file never authorizes provider writes.

## Fixed local paths

Unless Fedor explicitly supplies another location, user-facing Windows commands use:

```text
Repository: C:\Users\Fedor\Projects\video-channel-manager
Downloads:  C:\Users\Fedor\Downloads
```

A downloaded ZIP, TXT, JSON, HTML, PowerShell, MP3, or browser result file is not assumed to be inside the repository or the current shell directory.

## One self-contained PowerShell block

Every copy-paste PowerShell block must work from an arbitrary current directory and define every variable it uses in that same block.

Required construction rules:

1. Set `$ErrorActionPreference = "Stop"`.
2. Define `$Repo`, `$Downloads`, the exact artifact path, extraction root, and exact entrypoint path.
3. Use absolute paths or paths derived from those variables.
4. Use `-LiteralPath` for known paths.
5. Validate required files with `Test-Path -LiteralPath ... -PathType Leaf` before reading or invoking them.
6. Invoke the exact full script path; do not depend on `./script.ps1` or the prompt's current directory.
7. Inside delivered scripts, resolve sibling files from `$PSScriptRoot`.
8. For ZIP handoffs, show extraction, the exact inner package root, and the exact resulting entrypoint.
9. Use the exact known filename. When discovery is unavoidable, require exactly one match and fail on zero or multiple matches.
10. Never choose an artifact by `LastWriteTime`, “newest ZIP”, or a broad wildcard that can silently select the wrong generation.

Undefined variables such as `$wave`, `$package`, `$zip`, or `$out` are prohibited. A command must not depend on variables from an earlier message or terminal session.

## Mandatory handoff declaration

Before any command block, state:

- requested outcome independently of the historical mechanism;
- evidence level: `editorial_prepared`, `preview_validated`, `self_tested`, `canary_verified`, or `batch_verified`;
- capability: read-only, local-only, or provider-write-capable;
- transport for each phase: `local_only`, `official_api_read`, `official_api_write`, `internal_web_read`, `browser_ui_read`, or `browser_ui_write`;
- exact `project_key`;
- for VK work, exact community ID and owner ID;
- exact repository-owned entrypoint;
- current phase and provider-effect state: impossible, not dispatched, confirmed absent, may exist, or verified;
- exact expected result, ledger, and diagnostic paths;
- exact postcondition;
- canary behavior when applicable;
- safe recovery behavior after a non-zero exit or unknown provider outcome;
- stop condition and the one next bounded probe.

A preview, ZIP name, confirmation prompt, successful self-test, green CI run, final console line, modal closure, HTTP response, visible title, or screenshot is not mutation authorization or a complete postcondition. Operational-package acceptance keeps `provider_writes_authorized=false` and `automatic_execution=false`.

## Adaptive diagnosis before another package version

When a workflow fails, do not immediately produce another ZIP generation.

1. Preserve the exact result, screenshot/DOM evidence, and prior phase state.
2. State one falsifiable hypothesis.
3. Choose the smallest non-mutating probe that distinguishes it.
4. Record whether a remote effect is impossible, confirmed absent, may exist, or verified.
5. Patch repository-owned code and a regression fixture.
6. Resume only the failed child operation.

A second selector-only revision without a new DOM/state observation is prohibited. Do not blame manual user action until the defect is reproduced or excluded in a clean run.

## Browser UI contract

Browser automation must operate inside one exact active page or modal root.

Before every click or fill:

- identify the topmost active root;
- prove visibility and hit-testing;
- prove the control is a descendant of that root;
- retain before-state evidence;
- declare the expected state transition;
- perform one action;
- verify content/state and exact remote postcondition.

Do not use global text search or arbitrary coordinates when the same label may exist in a background page. A row click that starts playback is not selection. A background quick-search input is not an audio selector. `already_correct` requires exact separate-field readback.

One automation browser profile is a single-writer resource. Use one exact profile directory, reject concurrent ownership, and terminate the root process tree once. Do not iterate through child PIDs after the root tree has already been killed.

## Provider and implementation boundary

PowerShell orchestrates the repository-owned implementation. It must not become a second provider client and must not embed independent retry, pagination, permission, upload, publication, or postflight logic.

Do not create or hand off a generated external `executor.py` or a new v2/v3/v4 ZIP family as a shortcut. Fix the permanent repository implementation and its regression tests.

Never rerun a retired executor merely because its ZIP remains in Downloads. Read `docs/operations/retirement-registry-v1.json` before naming any executable path.

For any provider-capable operation:

- bind the exact project, community/channel, owner, manifest, and evidence digests;
- keep read-only preflight separate from mutation approval;
- persist intent before dispatch;
- preserve accepted, processing, verified, and unknown outcomes;
- never blind-retry an unknown outcome;
- require exact postflight rather than trusting HTTP success or stdout;
- preserve successful parent phases when a child phase fails.

Upload, upload visibility, metadata edit, playlist creation, track membership, final save, and wall publication are separate operations.

## MP3 local-only handoffs

Wave 15 local MP3 tooling may only probe and plan. A local-only MP3 command must state that it will not:

- rewrite ID3 tags;
- rename or transcode files;
- open or control a browser;
- call VK or YouTube;
- upload audio;
- edit remote metadata;
- create or modify playlists;
- publish a wall post.

The default metadata policy is explicit artist plus explicit title. Filename parsing requires a declared collection policy. The result must show exact input paths, SHA-256, duplicate/review states, manifest digest, and output path.

Historical BrowserCanary, PlaylistOnly, Metadata Manager, Rename AUTO, reliable batch, calibrator, and Playlist Workhorse ZIPs are evidence only and must not be selected by a handoff.

## Windows encoding

For user-facing Russian Windows artifacts:

- write `.ps1` and human-readable `.txt` as UTF-8 with BOM;
- write HTML with an explicit UTF-8 charset;
- keep JSON as valid UTF-8 without adding comments or non-JSON wrappers;
- verify the exact file path being opened or executed.

Encoding rules do not relax SHA-256, manifest, or exact-file identity checks.

## Final response checklist

A handoff is incomplete unless it includes:

1. the exact artifact filename and location;
2. one complete self-contained PowerShell block;
3. extraction steps when the artifact is a ZIP;
4. exact `Test-Path` checks;
5. exact full-path invocation;
6. declared outcome, truth level, capability, and transport;
7. exact project/community/owner binding for provider work;
8. current phase and provider-effect state;
9. expected success markers and machine-readable output paths;
10. exact postcondition;
11. explicit stop/reconcile instructions for unknown outcomes;
12. a prohibition on rerunning retired or already accepted operations.
