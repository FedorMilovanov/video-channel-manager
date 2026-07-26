# One-command YouTube comment refresh

Use this workflow after approved comment records have changed and existing channel comments need to be replaced without creating duplicates.

The command performs:

1. a fresh YouTube scan;
2. a full live comment audit;
3. an updates-only plan from approved records;
4. a signed live dry-run;
5. exact guarded updates when `--execute` is present;
6. post-write verification and journaling.

By default it **never creates a missing comment**. It updates only a single existing top-level comment authored by the expected channel, and only when its live text exactly matches the text captured by the fresh audit.

## Windows worktree setup

```powershell
$mainRepo = "C:\Users\Fedor\Projects\video-channel-manager"
$env:VCM_DATA_DIR = "$mainRepo\data"
$env:VCM_YOUTUBE_CLIENT_SECRET_FILE = "$mainRepo\secrets\client_secret.json"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
```

## Dry-run

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

## Safety properties

- fresh audit and signed plan are generated in the same run;
- updates require exact comment ID, owner channel, target video, and before-text;
- multiple channel comments on one video are never selected automatically;
- missing comments are review-only in default updates-only mode;
- live preflight must account for every operation;
- any blocker stops all writes;
- the channel write lock prevents concurrent writers;
- every operation is journaled and verified after the API call;
- reruns recognize already-applied content and do not duplicate it.
