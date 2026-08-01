# Project identity registry

Updated: 2026-08-01

This repository operates two separate media projects owned by Fedor Milovanov. They are not aliases of one project and must never be mixed in descriptions, comments, playlists, manifests, API writes, or operational reports.

Every provider operation must declare one `project_key` and use only the identities and links registered for that project. Account aliases are credential labels, not project identities.

## Credential model

### YouTube

YouTube uses two separate local OAuth aliases because each authorization resolves to one selected YouTube/Brand Account channel.

| Project | Local OAuth alias | Current access | Resolved title |
| --- | --- | --- | --- |
| `lord-god-strength` | `fedor-milovanov` | read-only | `Fedor Milovanov` |
| `legendary-poet` | `legendary-poet` | write | `The Legendary Poet` |

Reauthorizing an alias with `--force` replaces only that alias. For guarded writes, use `--write` and verify the exact returned channel ID after browser authorization.

### VK

VK uses one user access token for both communities. The current local token alias is `legendary-poet`, but that alias is only the stored credential name. It belongs to user `Федор Милованов` and can see multiple communities.

A shared VK token is expected and does not mix projects by itself. Isolation is provided by exact numeric target guards in every operation:

- `community_id`;
- `owner_id`;
- `project_key`;
- selected project link profile.

Never select a VK community by token alias, display order, or remembered context.

## Project 1: Господь Бог — Сила Моя

- Project key: `lord-god-strength`
- Current operational project: **yes**
- Content: Scripture study, theology, sermons, translations, biographies, apologetics

### YouTube

- Handle: `@fedormilovanov`
- Channel: https://www.youtube.com/@fedormilovanov
- Long-form videos: https://www.youtube.com/@fedormilovanov/videos
- Shorts: https://www.youtube.com/@fedormilovanov/shorts
- Authoritative public channel ID: `UCeSJsC6go2c9pdJCuUI1BYA`
- Local OAuth alias: `fedor-milovanov`
- Current access as of 2026-08-01: `read-only`

YouTube writes are forbidden until this alias is reauthorized with write scope and the CLI confirms exactly channel ID `UCeSJsC6go2c9pdJCuUI1BYA`.

The separate YouTube alias `legendary-poet` resolves to `The Legendary Poet` and must never be used for this project.

### VK

- Community title: `† Господь Бог - Сила Моя! †`
- Canonical community URL confirmed by the owner: https://vk.ru/the_lord_god_is_my_strength
- Published compatibility URL found in existing channel descriptions: https://vk.com/the_lord_god_is_my_strength
- VK Video URL confirmed by published project descriptions: https://vkvideo.ru/@the_lord_god_is_my_strength
- Community ID: `60805374`
- API owner ID: `-60805374`
- Shared local VK user-token alias: `legendary-poet`

Do not use `https://vk.com/gospod_bog`, `https://vk.com/video/@gospod_bog`, or `https://vk.com/clips/gospod_bog` as canonical viewer-facing links. They are historical operational references and must be live-verified before any future use.

### Other verified project links

- Website: https://gospod-bog.ru/
- Telegram: https://t.me/lordchrist
- Rutube: https://rutube.ru/channel/1876662/
- Odnoklassniki: https://ok.ru/christjesus
- Facebook group: https://facebook.com/groups/116164165395881

### Current canonical footer profile

Use only links actually required for the target surface. The standard cross-platform project footer is:

- Website: https://gospod-bog.ru/
- Telegram: https://t.me/lordchrist
- VK: https://vk.ru/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Rutube: https://rutube.ru/channel/1876662/

Odnoklassniki and Facebook are registered project links but are not part of the default compact footer.

## Project 2: The Legendary Poet — Легендарный Поэт

- Project key: `legendary-poet`
- Current operational project: **no**
- Content: poetry, literary history, music, AI-assisted creative experiments

### YouTube

- Channel title: `The Legendary Poet`
- Handle: `@TheLegendaryPoet`
- Channel: https://www.youtube.com/@TheLegendaryPoet
- Long-form videos: https://www.youtube.com/@TheLegendaryPoet/videos
- Shorts: https://www.youtube.com/@TheLegendaryPoet/shorts
- Local OAuth alias: `legendary-poet`
- Current access as of 2026-08-01: `write`
- Numeric YouTube channel ID: not yet recorded in this registry; resolve it with the CLI before any new write plan.

### VK

- Community title: `The Legendary Poet - Легендарный Поэт`
- Published project URL confirmed in current Rutube descriptions: https://vk.com/thelegendarypoet
- `vk.ru` equivalent: not yet independently confirmed; do not invent it in executable plans.
- VK Video URL: not yet independently confirmed.
- Numeric community ID and API owner ID: not yet confirmed by the 2026-08-01 CLI output.
- Shared local VK user-token alias: `legendary-poet`

Historical numeric IDs previously mentioned in project notes are not authoritative until a live `vk communities` read confirms them.

### Other verified project links

- Telegram: https://t.me/thelegendarypoet
- Rutube: https://rutube.ru/channel/74579453/

### Unverified or absent links

- The repository previously treated `https://thelegendarypoet.ru/` as an approved project URL, but the current public check did not verify an active site. It is not canonical until ownership and availability are confirmed.
- No default poet-project website link may be inserted while the site remains unverified.

### Current canonical footer profile

Until the missing identities are live-confirmed, use only:

- Telegram: https://t.me/thelegendarypoet
- VK: https://vk.com/thelegendarypoet
- Rutube: https://rutube.ru/channel/74579453/

YouTube playlist links are allowed only when they are exact memberships or explicitly reviewed links for the target video.

## Mandatory project-isolation rules

1. Every plan, journal, report, backup, and manifest must include `project_key`.
2. Every YouTube operation must bind the exact expected channel ID, not only an OAuth alias or display title.
3. Every VK operation must bind the exact community ID and API owner ID, not only the shared token alias or a vanity URL.
4. A plan for `lord-god-strength` may use only that project's link allowlist. A plan for `legendary-poet` may use only the poet project's link allowlist.
5. Cross-project promotion is forbidden by default. It requires an explicit reviewed per-operation exception.
6. Unknown or unregistered links fail closed. Do not guess a handle, Clips URL, site domain, or numeric ID.
7. Preflight must print the resolved project, YouTube channel ID, VK community ID, credential alias, and link profile before showing `ready`.
8. The shared VK alias `legendary-poet` never determines the project. The operation's exact numeric community target determines it.
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

For YouTube mutation, reauthorize the same project alias with write scope:

```powershell
video-manager youtube login --account fedor-milovanov --write --force
```

After browser authorization, the command must print exactly channel ID `UCeSJsC6go2c9pdJCuUI1BYA`. Otherwise stop without scanning or writing.
