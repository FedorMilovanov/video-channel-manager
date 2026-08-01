# Project identity registry

Updated: 2026-08-01

This repository operates two separate media projects owned by Fedor Milovanov. They are not aliases of one project and must never be mixed in descriptions, comments, playlists, manifests, API writes, or operational reports.

Every provider operation must declare one `project_key` and use only the identities and links registered for that project. Account aliases are credential labels, not project identities.

## Project 1: Господь Бог — Сила Моя

- Project key: `lord-god-strength`
- Current operational project: **yes**
- Content: Scripture study, theology, sermons, translations, biographies, apologetics

### YouTube

- Project/channel currently shown by the local account listing as: `Fedor Milovanov`
- Handle: `@fedormilovanov`
- Channel: https://www.youtube.com/@fedormilovanov
- Long-form videos: https://www.youtube.com/@fedormilovanov/videos
- Shorts: https://www.youtube.com/@fedormilovanov/shorts
- Authoritative public channel ID: `UCeSJsC6go2c9pdJCuUI1BYA`
- Current local OAuth alias: `fedor-milovanov`
- Current local OAuth access as of 2026-08-01: `read-only`
- YouTube writes are forbidden until a write-capable token resolves to exactly `UCeSJsC6go2c9pdJCuUI1BYA`.

The separate YouTube alias `legendary-poet` resolves to `The Legendary Poet` and must never be used for this project.

### VK

- Community title: `† Господь Бог - Сила Моя! †`
- Canonical community URL: https://vk.com/the_lord_god_is_my_strength
- Historical/alternate vanity URL: https://vk.com/gospod_bog
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Historical browser video path: https://vk.com/video/@gospod_bog
- Historical browser Clips path: https://vk.com/clips/gospod_bog
- Community ID: `60805374`
- API owner ID: `-60805374`
- Current local VK user-token alias: `legendary-poet`

The VK alias name is misleading: it is a user token that can see multiple communities. It is not permission to select a community by name, list position, or remembered context. Every VK write for this project must confirm numeric community ID `60805374` and owner ID `-60805374`.

### Other canonical links

- Website: https://gospod-bog.ru/
- Telegram: https://t.me/lordchrist
- Rutube: https://rutube.ru/channel/1876662/
- Facebook group: https://facebook.com/groups/116164165395881

## Project 2: The Legendary Poet — Легендарный Поэт

- Project key: `legendary-poet`
- Current operational project: **no**
- Content: poetry, literary history, music, AI-assisted creative experiments

### YouTube

- Channel title: `The Legendary Poet`
- Handle used publicly: `@TheLegendaryPoet`
- Channel: https://www.youtube.com/@TheLegendaryPoet
- Long-form videos: https://www.youtube.com/@TheLegendaryPoet/videos
- Shorts: https://www.youtube.com/@TheLegendaryPoet/shorts
- Current local OAuth alias: `legendary-poet`
- Current local OAuth access as of 2026-08-01: `write`
- Numeric YouTube channel ID: not yet recorded in this repository. Resolve and record it before any new write plan.

### VK

- Community title: `The Legendary Poet - Легендарный Поэт`
- Community URL: https://vk.com/thelegendarypoet
- Historically recorded community ID: `235216998`
- Historically derived API owner ID: `-235216998`
- Current local VK user-token alias: `legendary-poet`

The numeric VK identity above must be re-read from the live account before a future write because the 2026-08-01 local account output showed the community name but did not print its numeric ID.

### Other canonical links

- Telegram: https://t.me/thelegendarypoet
- Rutube: https://rutube.ru/channel/74579453/
- Website: not recorded. Never substitute `https://gospod-bog.ru/` for this project.

## Current credential state

Recorded from the local CLI on 2026-08-01:

### YouTube OAuth accounts

| Alias | Access | Resolved channel |
| --- | --- | --- |
| `fedor-milovanov` | read-only | `Fedor Milovanov` |
| `legendary-poet` | write | `The Legendary Poet` |

There is currently no confirmed write-capable YouTube credential for `lord-god-strength`.

### VK user-token accounts

The stored alias `legendary-poet` belongs to user `Федор Милованов` and can see multiple communities, including both projects. Therefore the alias alone is never an adequate write guard.

## Mandatory project-isolation rules

1. Every plan, journal, report, backup, and manifest must include `project_key`.
2. Every YouTube operation must bind the exact expected channel ID, not only an OAuth alias or display title.
3. Every VK operation must bind the exact community ID and API owner ID, not only a token alias or vanity URL.
4. A plan for `lord-god-strength` may use only that project's link allowlist. A plan for `legendary-poet` may use only the poet project's link allowlist.
5. Cross-project promotion is forbidden by default. It requires an explicit reviewed per-operation exception.
6. Unknown or unregistered links fail closed. Do not guess a handle, Clips URL, site domain, or numeric ID.
7. Preflight must print the resolved project, YouTube channel ID, VK community ID, account alias, and link profile before showing `ready`.
8. The local alias `legendary-poet` must never be interpreted as proof that the target project is The Legendary Poet or Господь Бог — Сила Моя; inspect the resolved provider identity.
9. Current work is restricted to `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, VK community `60805374`.
10. No operation prepared for the current task may touch The Legendary Poet YouTube channel or VK community.

## Required live checks before the current API rollout

```powershell
video-manager youtube channels --account fedor-milovanov
video-manager vk communities --account legendary-poet
```

For the current project, continue only when the selected identities are exactly:

```text
project_key: lord-god-strength
YouTube channel ID: UCeSJsC6go2c9pdJCuUI1BYA
VK community ID: 60805374
VK API owner ID: -60805374
```

YouTube mutation requires a separately verified write-capable OAuth token for the same channel ID. The existing `legendary-poet` YouTube write token is for the other project and is prohibited for this rollout.
