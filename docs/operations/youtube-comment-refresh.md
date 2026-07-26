# One-command YouTube comment refresh

Use this workflow after approved comment records have changed. It supports three fail-closed operating modes:

- the default **updates-only** mode, which never creates missing comments;
- an explicitly requested **create-and-update** mode through `--create-missing`;
- a strict **create-only** mode through `--create-missing --creates-only`, intended for final channel-closing waves.

The command performs:

1. a fresh YouTube scan, unless an explicit snapshot mode is selected;
2. a full live comment audit;
3. a signed plan from approved records;
4. a guarded live dry-run;
5. exact creates or updates when `--execute` is present;
6. per-operation post-write verification and journaling;
7. an optional channel-wide postflight audit.

By default it **never creates a missing comment**. It updates only a single existing top-level comment authored by the expected channel, and only when its live text exactly matches the text captured by the fresh audit.

## Windows worktree setup

```powershell
$mainRepo = "C:\Users\Fedor\Projects\video-channel-manager"
$env:VCM_DATA_DIR = "$mainRepo\data"
$env:VCM_YOUTUBE_CLIENT_SECRET_FILE = "$mainRepo\secrets\client_secret.json"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
```

## Dry-run approved updates

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ
```

## Execute all approved updates

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --execute `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --write-delay 3
```

The wrapper derives the exact live ready count, source snapshot, and signed plan SHA from the freshly generated plan and passes them to the guarded executor. A nonzero blocker count stops the whole batch before any write.

## Final create-only channel-closing pass

Use a dedicated approved content directory and require complete coverage of every live `missing` or `foreign_only` public video:

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --content-dir C:\path\to\approved-final-wave `
  --create-missing `
  --creates-only `
  --require-complete-coverage `
  --require-no-review-only `
  --postflight-audit `
  --require-zero-tail `
  --execute `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --write-delay 3
```

`--creates-only` omits update planning and then verifies defensively that every signed operation is a `create`. Existing channel comments cannot be changed in this mode.

`--require-complete-coverage` fails before plan signing when any actionable public video lacks a valid approved create operation. `--require-no-review-only` fails when an approved record cannot safely enter the plan. `--require-zero-tail` runs a channel-wide postflight and requires:

```text
missing + foreign_only == 0
```

A zero-tail failure happens **after** already verified writes and is reported as a remaining channel-coverage problem, not as a rollback. The journal and completed comments remain valid.

## Recovery after a postflight-only indexing failure

YouTube may accept every write while one new comment is still absent from immediate list reads. The executor now retries the complete postflight with bounded increasing delays. When an older run has already written every operation but stopped with `Full postflight did not confirm every planned comment operation`, use the original signed plan and original journal in `--verify-only` mode.

`--verify-only` has a hard no-write boundary:

- it requires an existing journal bound to the same plan SHA-256;
- every planned operation must already have a `completed` journal attempt;
- it acquires the normal channel writer lock;
- it repeatedly reads the complete plan until every operation is `already_applied`;
- it never calls create or update;
- it marks the original journal `completed` only after full confirmation.

Example:

```powershell
python -X utf8 .\scripts\apply_youtube_comment_plan.py `
  "C:\path\to\original-signed-plan.json" `
  --account legendary-poet `
  --verify-only `
  --journal "C:\path\to\original-apply-journal.json" `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --confirm-source-snapshot <SOURCE_SNAPSHOT_FROM_PLAN> `
  --confirm-plan-sha256 <PLAN_SHA256_FROM_PLAN> `
  --max-operations 200
```

Do not delete the journal, rebuild the plan, or rerun the original create wave blindly. A genuine remaining `ready` operation remains unconfirmed and is not written by recovery mode; a conflicting live comment or API error remains a blocker.

After successful recovery, run a new channel-wide scan and audit. Complete closure requires `missing: 0`, `foreign_only: 0`, and no `comments_disabled` or `error` targets hidden from the result.

## Optional modes

Use the newest existing snapshot without scanning again:

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --skip-scan
```

Use a specific snapshot:

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --snapshot C:\path\to\youtube-snapshot.json
```

Allow approved creates as well as updates only when that is the intended reviewed operation set:

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --create-missing
```

Allow creates but prohibit updates:

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --create-missing `
  --creates-only
```

Run a channel-wide audit after verified execution without requiring a zero tail:

```powershell
python -X utf8 .\scripts\refresh_youtube_comments.py `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --postflight-audit `
  --execute `
  --confirm-channel UC-78ys2S3cQ3lpqgXfo-SvQ
```

## Safety properties

- fresh audit and signed plan are generated in the same run;
- updates require exact comment ID, owner channel, target video, and before-text;
- strict create-only mode cannot include update operations;
- multiple channel comments on one video are never selected automatically;
- missing comments are review-only in default updates-only mode;
- final waves can require complete coverage before plan signing;
- live preflight must account for every operation;
- any blocker stops all writes;
- the channel write lock prevents concurrent writers;
- every operation is journaled and verified after the API call;
- full-plan postflight uses bounded retries for eventual YouTube indexing;
- verify-only recovery requires a complete original write journal and cannot write;
- optional channel-wide postflight distinguishes plan success from complete channel coverage;
- reruns recognize already-applied content and do not duplicate it.

See `youtube-comment-live-rollout-lessons.md` for the incidents and reasoning behind these rules.
