# YouTube comment preflight report

`preflight_youtube_comment_plan.py` reads the complete live state for every operation in a signed YouTube comment plan and writes a machine-readable artifact before any remote mutation.

## Command

```powershell
python -X utf8 .\scripts\preflight_youtube_comment_plan.py `
  .\data\reports\youtube-comment-plan.json `
  --account legendary-poet `
  --json-output .\data\reports\youtube-comment-preflight.json
```

The command never calls a YouTube write method. Exit code `0` means the read completed with no blockers. Exit code `1` means the report was written successfully but contains one or more blockers. Exit code `2` means the plan or local configuration could not be loaded or validated.

## Schema

```json
{
  "schema_name": "video-manager.youtube-comment-preflight",
  "schema_version": 1,
  "generated_at": "2026-07-26T00:00:00+00:00",
  "channel_id": "UC_EXACT_CHANNEL",
  "source_snapshot": "snapshot-id",
  "plan_sha256": "sha256:...",
  "counts": {
    "planned": 33,
    "ready": 33,
    "already_applied": 0,
    "blockers": 0
  },
  "estimated_write_quota_units": 1650,
  "results": []
}
```

Every result includes:

- `operation_id`;
- `video_id`;
- `status`;
- `detail`.

Allowed operational classifications are produced by the same `_preflight` and `_classify_operation` functions used by the guarded executor. The report is therefore not a second policy implementation.

## Binding rules

A consumer must reject the report unless all of these match the signed plan exactly:

- `channel_id`;
- `source_snapshot`;
- `plan_sha256`;
- `counts.planned` and the plan operation count.

It must also require:

```text
ready + already_applied + blockers == planned
```

The one-command refresh workflow follows these rules and no longer parses human-readable console wording to obtain confirmation values.

## Execution boundary

The report is evidence for the operator-facing dry-run only. It does not replace the executor's complete live preflight or the second preflight under the channel writer lock. Exact confirmations, journal-before-write, per-operation verification, and full postflight remain mandatory.
