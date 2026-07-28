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

## Resumable migration states

Each of the 42 video-text operations records three exact guarded states:

1. the verified Pushkin Cloud source description;
2. the exact descriptions-only intermediate state previously applied by decision set `p1-all-remaining-megawave-20260728`;
3. the final VK-native description.

A live video is writable only when it exactly matches state 1 or state 2. This permits safe completion after the earlier partial megawave without accepting arbitrary text drift.

## Managed and system VK albums

Positive album IDs are user-managed playlists and are compared by exact membership identity. The final managed set must equal the verified source managed set plus exactly 32 planned additions.

Negative album IDs are VK system albums. They are never mutated. The runner verifies their collection counts and verifies that system album `-2` still contains all 111 videos, while permitting identity churn inside the automatically updated recent-video album `-13`.

## Guarded execution

```powershell
pwsh -File .\scripts\Invoke-VkP1Megawave.ps1 `
  -Execute `
  -SourceApplyBundle ".\data\handoffs\vk-reviewed-correction-p1-pushkin-cloud-apply-20260728-034634.zip"
```

The runner independently verifies the Pushkin source apply and review bundle, rebuilds the exact plan, reads fresh VK state, performs a locked re-preflight, applies only accepted before-states, rescans all VK state, and verifies:

- 111 video identities remain present;
- 17 collection identities remain present;
- all 69 non-target videos remain text-identical;
- all 42 target descriptions equal the exact final after-state;
- the 3 target titles equal the exact after-state;
- the 3 album titles equal the exact after-state;
- managed memberships equal the verified 133 managed identities plus exactly 32 planned additions, for 165 managed identities;
- system album counts remain `-2: 111` and `-13: 50`;
- total membership identities equal 326;
- all VK playlist share URLs remain unchanged.

A successful run produces one file:

```text
data\handoffs\vk-p1-final-megawave-apply-YYYYMMDD-HHMMSS.zip
```

A failed run also produces one diagnostic ZIP with the completed journal and error report.

## Retired path

`content/policies/vk-p1-megawave-policy-20260728.json` is deliberately retired. The old descriptions-only implementation must not be used because it did not complete canonical links, VK playlists, titles, album names, or memberships.

## CI

GitHub Actions run `30352060107` passed on Python 3.11, 3.12, and 3.13. Dependency audit, compilation, Ruff correctness, Ruff formatting, mypy, all tests, and final job conclusions are green.
