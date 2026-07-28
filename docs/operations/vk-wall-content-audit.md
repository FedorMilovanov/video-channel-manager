# VK wall content audit

This workflow determines which VK videos have already appeared on the community wall, which are already scheduled, and which are confirmed unposted.

## Safety boundary

The audit is read-only. It calls VK inventory and wall-read methods only. It does not create, edit, delete, pin, repost, or schedule any wall post.

A missing `wall_post_id` on a video is not treated as proof that the video was never posted. The audit scans the complete owner wall and postponed queue and searches for video identities in:

- native video and clip attachments;
- VK and VK Video links in post text;
- repost and `copy_history` content.

Anything ambiguous is marked for review rather than classified as unposted.

## Run

```powershell
cd C:\Users\Fedor\Projects\video-channel-manager

git switch agent/vk-wall-content-audit
git pull --ff-only

pwsh -File .\scripts\Invoke-VkWallContentAudit.ps1
```

The default account is `legendary-poet`, and the default community is `235216998`.

## Output

The command writes one handoff ZIP:

```text
data\handoffs\vk-wall-content-audit-YYYYMMDD-HHMMSS.zip
```

Contents:

- complete current VK video inventory;
- complete published owner-wall response;
- complete postponed-wall response;
- structured per-video classification;
- human-readable review report;
- SHA-256 manifest.

Possible per-video states:

- `published` — found on the published owner wall;
- `scheduled` — found in the postponed queue;
- `unposted` — absent from both scans and has no unresolved wall marker;
- `wall_marker_only_review` — VK video metadata references a wall post that the scan did not resolve;
- `published_and_scheduled_conflict` — the same video appears in both published and postponed records.

Only `unposted` records are eligible for a future scheduling plan. Scheduling is a separate guarded write workflow and is not authorized by this audit.
