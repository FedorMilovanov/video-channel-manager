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
7. at-least-one-owned-comment validation for every current public video;
8. exact duplicate-text detection among channel-authored comments;
9. creation of a SHA-256-bound coverage certificate.

## Coverage and comment hygiene are different questions

A public video is covered when it has at least one top-level comment authored by the channel. Additional channel-authored comments are not automatically duplicates. They may be intentional and complementary, for example:

- an editorial or historical explanation;
- a playlist link;
- channel and social links;
- a production note or audience question.

The recovery certificate records how many videos have multiple channel-authored comments and how many extra comments exist. Distinct additional comments do not block coverage.

A blocking duplicate is narrower: two channel-authored comments on the same video with the same normalized text SHA-256. Exact duplicate text indicates a likely accidental repeated publication and must be reviewed before certification.

Near-duplicate or editorially redundant comments remain a separate review concern. The recovery command does not delete, merge, or rewrite them.

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
- `owned_comments` must agree with `owned_comment_count`;
- comment IDs must be unique within each video's audit record;
- every public video must have at least one channel-authored top-level comment;
- `missing`, `foreign_only`, `comments_disabled`, and `error` must all be zero;
- exact same-text channel-comment duplicates are blocking failures;
- distinct additional channel comments are reported but are not destructive-action candidates;
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

Certificate schema version 2 records:

- the signed plan SHA and file SHA-256;
- the completed journal SHA-256;
- the fresh snapshot SHA-256;
- the fresh audit SHA-256;
- the number of planned and completed operations;
- the dynamic public inventory count;
- zero remaining uncovered tail;
- the number of videos with multiple channel-authored comments;
- the number of extra distinct channel-authored comments;
- zero exact same-text duplicates;
- `remote_writes: 0` for the recovery run.

Keep the plan, completed journal, fresh snapshot, final audit, and coverage certificate together as the recovery evidence bundle.
