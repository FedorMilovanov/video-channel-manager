# Project identity registry

Updated: 2026-08-01

This repository operates two separate media projects owned by Fedor Milovanov. They are not aliases of one project and must never be mixed in descriptions, comments, playlists, manifests, API writes, operational reports, or public footer links.

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
- Authoritative numeric channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- Local OAuth alias: `legendary-poet`
- Current access as of 2026-08-01: `write`

Every YouTube write plan for this project must bind exactly channel ID `UC-78ys2S3cQ3lpqgXfo-SvQ`. The theological alias and channel ID must never be substituted.

### VK public identity

- Community title: `The Legendary Poet - Легендарный Поэт`
- Canonical community URL confirmed by the owner: https://vk.ru/thelegendarypoet
- Compatibility community URL confirmed by the owner: https://vk.com/thelegendarypoet
- Public VK Clips route confirmed by the owner: https://vkvideo.ru/@thelegendarypoet/clips
- Community number shown by VK: `club235216998`
- Community ID: `235216998`
- API owner ID: `-235216998`
- Shared local VK user-token alias: `legendary-poet`

Do not infer a different VK Video root, Clips handle, or vanity route. Use only the exact public routes above unless a fresh live check adds another route to this registry.

### VK Video author-cabinet routes

These are operational/admin routes. They are never public footer links and must not be inserted into descriptions, comments, posts, manifests intended for viewers, or cross-platform promotion blocks.

- Author dashboard: https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet
- Published clips view: https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet?filterPreset=published&section=video_my_content&subsection=video_my_content_clips

### Other verified project links

- Website: https://thelegendarypoet.ru/
- Telegram: https://t.me/thelegendarypoet
- Rutube: https://rutube.ru/channel/74579453/

The website, VK community routes, VK numeric IDs, VK Clips route, and author-cabinet routes were owner-confirmed on 2026-08-01 and are no longer `unverified`.

### Current canonical footer profile

Use only links required for the target surface. The standard public project footer is:

- Website: https://thelegendarypoet.ru/
- Telegram: https://t.me/thelegendarypoet
- VK: https://vk.ru/thelegendarypoet
- Rutube: https://rutube.ru/channel/74579453/

Optional public route when the target text specifically promotes short-form material:

- VK Clips: https://vkvideo.ru/@thelegendarypoet/clips

The compatibility route `https://vk.com/thelegendarypoet` is valid migration input, but new canonical output should prefer `https://vk.ru/thelegendarypoet`.

The `cabinet.vkvideo.ru` URLs are operational only and are forbidden in public footers.

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
11. Public and operational/admin URLs are different classes. `cabinet.vkvideo.ru` routes must never enter public output.
12. Source-code link profiles and validators must remain synchronized with this canonical registry; a documentation update does not by itself authorize a provider write.

## Required live checks before provider writes

For the current theological project:

```powershell
video-manager youtube channels --account fedor-milovanov
video-manager vk communities --account legendary-poet
```

Continue only when the selected identities are exactly:

```text
project_key: lord-god-strength
YouTube channel ID: UCeSJsC6go2c9pdJCuUI1BYA
VK community ID: 60805374
VK API owner ID: -60805374
```

For a future The Legendary Poet operation, continue only when the selected identities are exactly:

```text
project_key: legendary-poet
YouTube channel ID: UC-78ys2S3cQ3lpqgXfo-SvQ
VK community ID: 235216998
VK API owner ID: -235216998
```

For YouTube mutation on the theological project, reauthorize the same project alias with write scope:

```powershell
video-manager youtube login --account fedor-milovanov --write --force
```

After browser authorization, the command must print exactly channel ID `UCeSJsC6go2c9pdJCuUI1BYA`. Otherwise stop without scanning or writing.
