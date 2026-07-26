# YouTube comment publishing runbook

This workflow adds or updates top-level comments across the channel without copying text manually video by video.
It is deliberately split into **audit → editorial review → plan → locked preflight → execute → verify**.

## Safety boundary

- The software does not invent literary or historical claims.
- Only files with `schema_name=video-manager.youtube-comment-content` and `status=approved` can enter a write plan.
- Every approved record must contain at least one `source_id` or editorial-rule ID.
- The default plan mode creates comments only where the channel has no existing top-level comment.
- A different existing channel comment is a review-only conflict, not permission to create a duplicate.
- Updating an existing comment requires its exact comment ID and exact reviewed before-text.
- Live writes require a token containing `https://www.googleapis.com/auth/youtube.force-ssl`.
- Dry-run is the default. `--execute` still requires exact channel, source snapshot, live ready count, and plan SHA-256 confirmations.
- One per-channel Windows-safe lock prevents concurrent YouTube writers.
- The journal is saved before each write and after every result. A rerun resumes instead of duplicating completed comments.

## 1. Refresh the unified code

Use a separate worktree or wait until other Git activity has finished. Do not run two YouTube write processes for the same channel.

```powershell
git fetch origin
git switch feature/youtube-comment-publishing-v1
git pull --ff-only
python -m pip install -e ".[dev]"
```

Point the worktree to the existing shared data directory when necessary:

```powershell
$mainRepo = "C:\Users\Fedor\Projects\video-channel-manager"
$env:VCM_DATA_DIR = "$mainRepo\data"
```

## 2. Create a fresh YouTube snapshot

```powershell
video-manager youtube scan `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ
```

Save the returned path:

```powershell
$yt = Get-Item "$mainRepo\data\exports\youtube-legendary-poet-UC-78ys2S3cQ3lpqgXfo-SvQ-<TIMESTAMP>.json"
```

## 3. Read every video's live comments

This step is read-only. It classifies public videos as:

- `missing` — no top-level comments;
- `foreign_only` — viewer comments exist, but the channel has no top-level comment;
- `owned_present` — at least one top-level comment from the channel exists;
- `comments_disabled` — YouTube reports comments disabled;
- `error` — a live API read failed.

```powershell
python .\scripts\audit_youtube_comments.py `
  "$($yt.FullName)" `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ
```

The script creates JSON plus a Markdown report in `data/reports`.

## 4. Add reviewed content records

Approved records live under:

```text
content/youtube-comments/<VIDEO_ID>.json
```

Required fields:

```json
{
  "schema_name": "video-manager.youtube-comment-content",
  "schema_version": 1,
  "status": "approved",
  "channel_id": "UC-78ys2S3cQ3lpqgXfo-SvQ",
  "video_id": "VIDEO_ID",
  "video_title": "Reviewed title",
  "reviewed_at": "2026-07-25T15:40:00+00:00",
  "source_ids": ["primary-source-id", "youtube-editorial-link-map"],
  "comment_text": "Final text shown to viewers",
  "sources": []
}
```

`draft`, `needs-research`, and other statuses are never published.

## 5. Build the self-validating plan

```powershell
$audit = Get-Item "$mainRepo\data\reports\youtube-comment-audit-UC-78ys2S3cQ3lpqgXfo-SvQ-<TIMESTAMP>.json"

python .\scripts\build_youtube_comment_plan.py `
  "$($yt.FullName)" `
  "$($audit.FullName)" `
  --account legendary-poet `
  --content-dir .\content\youtube-comments
```

Default behavior is `reviewed-missing-only`:

- approved content + no channel comment → `create`;
- identical channel comment → already applied;
- different channel comment → review-only;
- disabled comments or audit errors → review-only;
- unapproved content → excluded.

Use `--include-updates` only after reviewing every existing before-text shown by the audit.

The output includes:

- exact channel and source snapshot;
- hash of the complete public-video inventory;
- hash of every comment text;
- deterministic operation IDs;
- hash of the exact operation set;
- final `plan_sha256`.

Any manual edit after review invalidates the plan.

## 6. Dry-run the live plan

```powershell
$plan = Get-Item "$mainRepo\data\reports\youtube-comment-plan-UC-78ys2S3cQ3lpqgXfo-SvQ-<TIMESTAMP>.json"

python .\scripts\apply_youtube_comment_plan.py `
  "$($plan.FullName)" `
  --account legendary-poet
```

Expected summary:

```text
planned operations: N
ready now: N
already applied / journaled: M
blockers: 0
estimated write quota: N * 50 units
```

Do not execute while `blockers` is nonzero.

## 7. Authorize guarded write access once

```powershell
video-manager youtube login `
  --account legendary-poet `
  --write `
  --force
```

## 8. Execute the exact reviewed set

Copy the live ready count and exact plan SHA from the dry-run:

```powershell
python .\scripts\apply_youtube_comment_plan.py `
  "$($plan.FullName)" `
  --account legendary-poet `
  --execute `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --confirm-count N `
  --confirm-source-snapshot <SNAPSHOT_UUID> `
  --confirm-plan-sha256 sha256:<EXACT_PLAN_SHA> `
  --write-delay 2
```

The executor then:

1. revalidates the whole plan;
2. checks all live videos and comments;
3. acquires the channel lock;
4. repeats the full preflight under the lock;
5. journals `pending` before each API call;
6. creates or updates exactly one reviewed comment;
7. rereads and verifies the stored comment;
8. records IDs and hashes;
9. runs a full postflight over the complete plan.

## 9. Resume after an interruption

Run the same command with the same plan and journal. Completed operation IDs are reused; pending or failed operations are rechecked against live YouTube before any new write.

Do not delete the journal to force a rerun. A live identical comment is also detected as already applied.

## API facts used by this implementation

- `commentThreads.list` reads top-level comment threads and costs 1 quota unit.
- `commentThreads.insert` creates a top-level comment, requires OAuth, and costs 50 quota units.
- `comments.list` verifies an exact comment ID and costs 1 quota unit.
- `comments.update` updates a comment and costs 50 quota units.
- `commentsDisabled` is handled separately from general API failures.
- Top-level comment creation uses `snippet.channelId`, `snippet.videoId`, and `snippet.topLevelComment.snippet.textOriginal`.

Official references:

- https://developers.google.com/youtube/v3/docs/commentThreads/list
- https://developers.google.com/youtube/v3/docs/commentThreads/insert
- https://developers.google.com/youtube/v3/docs/comments/list
- https://developers.google.com/youtube/v3/docs/comments/update
- https://developers.google.com/youtube/v3/guides/implementation/comments
- https://developers.google.com/youtube/v3/docs/errors
- https://developers.google.com/youtube/v3/getting-started
