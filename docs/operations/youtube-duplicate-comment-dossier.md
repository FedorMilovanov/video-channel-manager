# YouTube duplicate channel-comment dossier

Use this workflow when the strict recovery certificate refuses completion because one or more public videos contain multiple top-level comments authored by the channel.

The dossier command is read-only. It does not delete, update, hide, moderate, or create comments.

## Why deletion is not automatic

A duplicate count proves only that more than one channel-authored comment exists. It does not prove which comment is obsolete. A safe cleanup must preserve the comment selected by verifiable evidence and bind every proposed deletion to an exact comment ID, video ID, text hash, and live before-state.

The dossier correlates three sources:

1. the fresh channel-wide comment audit;
2. the original signed comment plan, when supplied;
3. the completed apply journal, when supplied.

A keep recommendation is made only when exactly one live comment:

- has the exact `comment_id` retained by a completed journal attempt; or
- uniquely matches the text in the signed plan.

Journal identity has priority over text matching. Ambiguous cases remain `review_required`. No deletion candidate is emitted when the keep selection is ambiguous.

## Current Wave 3 command

```powershell
cd "C:\Users\Fedor\Projects\video-channel-manager"

git fetch origin
git switch main
git pull --ff-only origin main
py -3.11 -m pip install -e ".[dev]"

py -3.11 -X utf8 .\scripts\report_youtube_duplicate_comments.py `
  "C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-comment-audit-closure-UC-78ys2S3cQ3lpqgXfo-SvQ-20260726-164501.json" `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --plan "C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-comment-plan-classic-wave-3-final-20260726-021108.json" `
  --journal "C:\Users\Fedor\Projects\video-channel-manager\data\reports\youtube-comment-apply-2de3f5091e87a7bd.json"
```

The command writes JSON and Markdown beside the audit file. Each duplicate entry contains:

- video ID and title;
- every owned top-level comment ID;
- full comment text and SHA-256;
- publication and update timestamps;
- moderation status;
- whether the comment ID came from the completed journal;
- whether its text matches the signed plan;
- a conservative keep recommendation, when unique;
- proposed deletion candidates for later review;
- `destructive_action_authorized: false`.

## Safety boundary

The dossier is analysis evidence, not permission to delete. A later cleanup executor must require a separately reviewed and signed deletion plan, exact live rereads under the channel lock, exact-before hashes, explicit count and plan-SHA confirmations, post-delete verification, a fresh full audit, and a new coverage certificate.
