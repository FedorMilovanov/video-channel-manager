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
  -Journal "C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-comment-apply-2de3f5091e87a7bd.json" `
  -ExpectedOwnedPresent 127
```

The script performs, in order:

1. a fresh-process import smoke test;
2. no-write `--verify-only` recovery;
3. journal status validation;
4. a new read-only YouTube scan;
5. a new full comment audit;
6. strict validation of the JSON file and all required counters.

## Why this must be a script file

An interactive PowerShell paste can continue with later commands after a `throw`. If a JSON audit was never created, later casts such as `[int]$null` produce `0`, which can print a false success message.

`recover_youtube_comment_wave.ps1` is fail-closed:

- `Set-StrictMode` and `$ErrorActionPreference = "Stop"` are enabled;
- every native command exit code is checked;
- the final JSON must exist and be nonempty;
- the `counts` object and every required property must exist and parse as integers;
- `owned_present` must match the expected public-video count;
- `missing`, `foreign_only`, `comments_disabled`, and `error` must all be zero;
- any failure exits the script with code 1 before a success message can be printed.

## Circular-import regression

The recovery and audit scripts import `video_channel_manager.platforms.youtube.comments` directly. Package initializers must therefore remain safe when YouTube modules load before editorial preview helpers.

`video_channel_manager.editorial` now exposes preview helpers lazily, preventing this cycle:

```text
youtube.__init__ -> youtube.renderers -> editorial.__init__
-> editorial.preview -> youtube.renderers (partially initialized)
```

Fresh-process regression tests preserve both import orders.

## Successful completion criteria

For the current 127-public-video inventory, completion requires a real audit JSON containing:

```text
owned_present: 127
foreign_only: 0
missing: 0
comments_disabled: 0
error: 0
```

Do not accept console zeros when the audit command failed or the JSON file is absent.
