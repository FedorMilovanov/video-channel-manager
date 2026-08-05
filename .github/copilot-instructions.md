# Windows handoff contract for repository agents

These instructions supplement the repository-root `AGENTS.md`. `AGENTS.md`, `docs/operations/current-state.md`, the machine audit register, the retirement registry, and the exact owning issue remain authoritative. This file never authorizes provider writes.

## Fixed local paths

Unless Fedor explicitly supplies another location, user-facing Windows commands use:

```text
Repository: C:\Users\Fedor\Projects\video-channel-manager
Downloads:  C:\Users\Fedor\Downloads
```

A downloaded ZIP, TXT, JSON, HTML, or PowerShell file is not assumed to be inside the repository or the current shell directory.

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

- evidence level: `editorial_prepared`, `preview_validated`, `self_tested`, `canary_verified`, or `batch_verified`;
- capability: read-only, local-only, or provider-write-capable;
- exact `project_key`;
- for VK work, exact community ID and owner ID;
- exact repository-owned entrypoint;
- exact expected result, ledger, and diagnostic paths;
- canary behavior when applicable;
- safe recovery behavior after a non-zero exit or unknown provider outcome.

A preview, ZIP name, confirmation prompt, successful self-test, green CI run, or final console line is not mutation authorization. Operational-package acceptance keeps `provider_writes_authorized=false` and `automatic_execution=false`.

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
- require exact postflight rather than trusting HTTP success or stdout.

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
6. the declared truth level and read/write capability;
7. exact project/community/owner binding for provider work;
8. expected success markers and machine-readable output paths;
9. explicit stop/reconcile instructions for unknown outcomes;
10. a prohibition on rerunning retired or already accepted operations.
