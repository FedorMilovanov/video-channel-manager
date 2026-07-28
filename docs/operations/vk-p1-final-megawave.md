# VK P1 final all-in-one megawave

This is the only approved path for the remaining VK P1 migration.

## Exact scope

- 42 target descriptions rewritten into a unified VK-native format
- 3 misleading video titles corrected by explicit override
- 3 video-album titles normalized
- 32 missing positive video-album memberships added
- 77 guarded operations total
- 0 membership removals
- 0 video deletions
- 0 system-album mutations

## Description contract

Every target description is rebuilt from the verified final VK snapshot and contains:

- concise work-specific lead and format label;
- conservative evidence rule separating fact from interpretation;
- preserved poem-like blocks when they fit under the 5000-character VK limit;
- direct link to the full VK version for short videos;
- actual VK playlist URLs from the current collection `share_url` values;
- canonical `https://thelegendarypoet.ru` author, music, and home links where available;
- canonical VK, Telegram, RUTUBE, and YouTube project links;
- standardized project, author, work, AI-music, and short-video hashtags;
- rights notices and source links for modern copyrighted works where applicable.

Legacy arbitrary playlist links, obsolete footer blocks, unsupported biography, medical diagnosis, prophecy, and unsourced spiritual claims are not carried forward.

## Guarded execution

```powershell
pwsh -File .\scripts\Invoke-VkP1Megawave.ps1 `
  -Execute `
  -SourceApplyBundle ".\data\handoffs\vk-reviewed-correction-p1-pushkin-cloud-apply-20260728-034634.zip"
```

The runner independently verifies the Pushkin source apply and review bundle, rebuilds the exact plan, reads fresh VK state, performs a locked re-preflight, applies only before-state operations, rescans all VK state, and verifies:

- 111 video identities remain present;
- 17 collection identities remain present;
- all 69 non-target videos remain text-identical;
- all 42 target descriptions equal the exact after-state;
- the 3 target titles equal the exact after-state;
- the 3 album titles equal the exact after-state;
- the final membership set equals the original 294 identities plus exactly 32 planned additions, for 326 total identities;
- all VK playlist share URLs remain unchanged.

A successful run produces one file:

```text
data\handoffs\vk-p1-final-megawave-apply-YYYYMMDD-HHMMSS.zip
```

A failed run also produces one diagnostic ZIP with the completed journal and error report.

## Retired path

`content/policies/vk-p1-megawave-policy-20260728.json` is deliberately retired. The old descriptions-only implementation must not be used because it did not complete canonical links, VK playlists, titles, album names, or memberships.
