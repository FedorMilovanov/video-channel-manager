# VK wall wave — August 2026

This workflow schedules the first editorial VK wall wave after the verified wall-content audit.

## Approved scope

- 12 unique videos;
- 12 postponed wall posts;
- no immediate posts;
- Moscow timezone;
- Monday and Wednesday at 19:30, Saturday at 13:00;
- first post: 2026-08-03;
- last post: 2026-08-29.

The source audit proved 88 videos unposted. This wave intentionally selects only 12 full or primary editorial versions across different poets. The 15 `wall_marker_only_review` records remain excluded.

## Safety model

The command defaults to dry-run. Remote writes require the explicit `-Execute` switch.

Before any write it verifies:

1. policy and every message SHA-256;
2. the exact source audit ZIP outer SHA and every manifest record;
3. the source audit self-digest and summary;
4. each selected video is exactly `unposted` in the source audit;
5. each live video is absent from published and postponed posts, or already has the exact approved post;
6. all ready publish dates remain safely in the future;
7. the required Lermontov article is deployed at its canonical URL;
8. the token manages community `235216998`.

Execution acquires the existing local VK write lock, repeats the complete live preflight, repeats the article check, and stops if anything changed.

After scheduling, the command rescans both the owner wall and the postponed queue. Every approved video must resolve to exactly one post with the approved message and date. A result is completed only after all 12 operations verify.

## Dry-run

```powershell
cd C:\Users\Fedor\Projects\video-channel-manager

git switch agent/vk-wall-wave-202608
git pull --ff-only

pwsh -File .\scripts\Invoke-VkWallWave.ps1 `
  -SourceAuditBundle ".\data\handoffs\vk-wall-content-audit-20260728-205938.zip"
```

## Apply

Run only after the article PR is merged and the canonical article URL is live:

```powershell
pwsh -File .\scripts\Invoke-VkWallWave.ps1 `
  -Execute `
  -SourceAuditBundle ".\data\handoffs\vk-wall-content-audit-20260728-205938.zip"
```

## Handoff

Dry-run:

```text
data\handoffs\vk-wall-wave-dry-run-YYYYMMDD-HHMMSS.zip
```

Apply:

```text
data\handoffs\vk-wall-wave-apply-YYYYMMDD-HHMMSS.zip
```

A failure also produces a diagnostic ZIP containing `ERROR.json`, all evidence available before the failure, and a SHA-256 manifest.
