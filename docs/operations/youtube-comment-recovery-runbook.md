# YouTube comment recovery after postflight-only failure

Use this procedure only when every planned write was journaled as `completed`, but the final full-plan postflight failed because YouTube had not indexed one or more successful comments yet.

## Important distinction

A message such as:

```text
WARNING: comment ... is not indexed in list results yet
ERROR: Full postflight did not confirm every planned comment operation.
```

means that the executor could not yet reread the complete operation set. It does **not** grant permission to repeat the create wave blindly.

The safe next action is `--verify-only`. This mode:

- requires the original signed plan;
- requires the original apply journal;
- refuses missing or non-completed journal attempts;
- acquires the normal channel writer lock;
- retries the full read-only postflight;
- never calls a YouTube create or update method;
- marks the original journal `completed` only after every operation reads as `already_applied`.

## One fail-closed recovery command

Update and install the current `main`, then run the repository PowerShell script:

```powershell
cd "C:\Users\Fedor\Projects\video-channel-manager"

git fetch origin
git switch main
git pull --ff-only origin main
py -3.11 -m pip install -e ".[dev]"

& .\scripts\recover_youtube_comment_wave.ps1 `
  -Plan "C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-comment-plan-classic-wave-3-final-20260726-021108.json" `
  -Journal "C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-comment-apply-2de3f5091e87a7bd.json"
```

The PowerShell entrypoint delegates all evidence checks to `recover_youtube_comment_wave.py`. The Python workflow performs, in order:

1. strict validation of the original signed plan and original journal;
2. no-write `--verify-only` recovery;
3. confirmation that the journal reached `completed`;
4. a new read-only YouTube scan;
5. a new full comment audit;
6. structural and arithmetic validation of the audit JSON;
7. exact-one-owned-comment validation for every current public video;
8. creation of a SHA-256-bound coverage certificate.

## Why the public-video count is dynamic

The recovery command does not accept or hard-code an expected `owned_present` value. The authoritative public inventory size comes from the fresh snapshot and must equal:

```text
len(audit.videos)
== sum(audit.counts)
== audit.inventory_video_count
== audit.counts.owned_present
```

This remains correct when videos are added, removed, published, or made nonpublic between waves.

## Why this must be a script file

An interactive PowerShell paste can continue with later commands after a `throw`. If a JSON audit was never created, later casts such as `[int]$null` produce `0`, which can print a false success message.

The recovery workflow is fail-closed:

- `Set-StrictMode` and `$ErrorActionPreference = "Stop"` protect the PowerShell entrypoint;
- every native command exit code is checked;
- the audit JSON must exist, parse, and use the supported schema;
- counts must be real non-negative integers, not booleans or absent values;
- declared counts must equal the recomputed per-video statuses;
- video IDs must be unique and cover the complete fresh inventory;
- every public video must have exactly one channel-authored top-level comment;
- `missing`, `foreign_only`, `comments_disabled`, and `error` must all be zero;
- duplicate channel-authored comments are blocking failures;
- any failure exits before a success certificate can be written.

## Circular-import regression

The recovery and audit scripts import `video_channel_manager.platforms.youtube.comments` directly. Package initializers must therefore remain safe when YouTube modules load before editorial preview helpers.

`video_channel_manager.editorial` exposes preview helpers lazily, preventing this cycle:

```text
youtube.__init__ -> youtube.renderers -> editorial.__init__
-> editorial.preview -> youtube.renderers (partially initialized)
```

Fresh-process regression tests preserve both import orders.

## Successful completion evidence

Completion is not a green console line. A successful run creates:

```text
data/reports/youtube-comment-coverage-certificate-<channel>-<timestamp>.json
```

The certificate records:

- the signed plan SHA and file SHA-256;
- the completed journal SHA-256;
- the fresh snapshot SHA-256;
- the fresh audit SHA-256;
- the number of planned and completed operations;
- the dynamic public inventory count;
- zero remaining tail and exactly one owned comment per public video;
- `remote_writes: 0` for the recovery run.

Keep the plan, completed journal, fresh snapshot, final audit, and coverage certificate together as the recovery evidence bundle.
