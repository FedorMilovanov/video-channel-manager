# Two-project link audit — 2026-08-01

Updated after owner confirmation of The Legendary Poet website, VK identities, VK Clips route, and VK Video author-cabinet routes.

## Purpose

Verify the public identities and links for the two separate projects and identify repository places where aliases, historical URLs, operational URLs, or project links were mixed.

Status vocabulary:

- `verified` — confirmed by the owner, live project page, local provider account output, or current published project metadata;
- `compatibility` — currently published or historically used, but not the preferred new viewer-facing form;
- `operational-admin` — valid only for an authenticated operator workflow and forbidden in public output;
- `operational-history` — retained only to explain old artifacts and reports;
- `unverified` — do not place into a new executable plan until live-confirmed.

## Credential conclusions

### YouTube

Two separate OAuth aliases are correct:

- `fedor-milovanov` → current theological channel authorization, read-only on 2026-08-01;
- `legendary-poet` → The Legendary Poet, write-capable on 2026-08-01.

For theological-channel writes, reauthorize `fedor-milovanov` with `--write --force` and require exact channel ID `UCeSJsC6go2c9pdJCuUI1BYA`.

For a The Legendary Poet write, require exact channel ID `UC-78ys2S3cQ3lpqgXfo-SvQ`.

### VK

One shared user token for both communities is correct. The stored alias `legendary-poet` is only a credential label. It must not determine the target project.

Every VK operation must bind exact `project_key`, `community_id`, and `owner_id`.

## Project: Господь Бог — Сила Моя

| Surface | URL or ID | Status | Evidence/decision |
| --- | --- | --- | --- |
| YouTube | `https://www.youtube.com/@fedormilovanov` | verified | public inventory and local operational state |
| YouTube channel ID | `UCeSJsC6go2c9pdJCuUI1BYA` | verified | public inventory/source identity |
| VK community | `https://vk.ru/the_lord_god_is_my_strength` | verified | owner-confirmed canonical URL |
| VK compatibility | `https://vk.com/the_lord_god_is_my_strength` | compatibility | published in existing project descriptions |
| VK Video | `https://vkvideo.ru/@the_lord_god_is_my_strength` | verified | published in current project video descriptions |
| VK community ID | `60805374` | verified | local provider configuration and completed operations |
| VK owner ID | `-60805374` | verified | local provider configuration and completed operations |
| Website | `https://gospod-bog.ru/` | verified | active project site |
| Telegram | `https://t.me/lordchrist` | verified | published project route |
| Rutube | `https://rutube.ru/channel/1876662/` | verified | active project channel |
| Odnoklassniki | `https://ok.ru/christjesus` | verified/published | existing project metadata |
| Facebook | `https://facebook.com/groups/116164165395881` | verified/published | existing project metadata |

### Default compact footer

Use:

- `https://gospod-bog.ru/`
- `https://t.me/lordchrist`
- `https://vk.ru/the_lord_god_is_my_strength`
- `https://vkvideo.ru/@the_lord_god_is_my_strength`
- `https://rutube.ru/channel/1876662/`

Odnoklassniki and Facebook remain registered but are not included by default.

### Historical routes that are not canonical

- `https://vk.com/gospod_bog`
- `https://vk.com/video/@gospod_bog`
- `https://vk.com/clips/gospod_bog`

These may remain in postmortems, snapshots, or old reports as evidence. Do not insert them into new descriptions or comments without a fresh live check.

## Project: The Legendary Poet — Легендарный Поэт

| Surface | URL or ID | Status | Evidence/decision |
| --- | --- | --- | --- |
| YouTube | `https://www.youtube.com/@TheLegendaryPoet` | verified | local OAuth title/alias and published project references |
| YouTube channel ID | `UC-78ys2S3cQ3lpqgXfo-SvQ` | verified | resolved local OAuth identity and current code profile |
| Website | `https://thelegendarypoet.ru/` | verified | owner-confirmed project site |
| VK community | `https://vk.ru/thelegendarypoet` | verified | owner-confirmed canonical URL |
| VK compatibility | `https://vk.com/thelegendarypoet` | compatibility | owner-confirmed working route and existing published route |
| VK Clips | `https://vkvideo.ru/@thelegendarypoet/clips` | verified | owner-confirmed public clips route |
| VK community number | `club235216998` | verified | owner-provided VK community number |
| VK community ID | `235216998` | verified | numeric form of the confirmed community number |
| VK owner ID | `-235216998` | verified | VK API owner form for the confirmed community |
| Telegram | `https://t.me/thelegendarypoet` | verified/published | current project descriptions |
| Rutube | `https://rutube.ru/channel/74579453/` | verified | active project channel |
| VK Video dashboard | `https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet` | operational-admin | owner-confirmed author dashboard; never public |
| VK Video published clips view | `https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet?filterPreset=published&section=video_my_content&subsection=video_my_content_clips` | operational-admin | owner-confirmed filtered cabinet route; never public |

### Canonical public footer

Use only links required for the target surface:

- `https://thelegendarypoet.ru/`
- `https://t.me/thelegendarypoet`
- `https://vk.ru/thelegendarypoet`
- `https://rutube.ru/channel/74579453/`

For short-form promotion, this additional public route is allowed:

- `https://vkvideo.ru/@thelegendarypoet/clips`

The compatibility route `https://vk.com/thelegendarypoet` may remain in historical content or migration input, but new canonical output should prefer the `vk.ru` form.

The two `cabinet.vkvideo.ru` routes are operational only. They must never be rendered into public descriptions, comments, posts, footers, or promotion blocks.

## Repository findings

### Resolved in `main`

- Added a canonical two-project registry.
- Corrected the theological VK URL to the canonical `vk.ru` form.
- Documented two YouTube OAuth aliases and one shared VK user token.
- Replaced the old global editorial project-link model with project-specific profiles and cross-project rejection.
- Added regression coverage for separate project identities.
- Recorded The Legendary Poet website as verified.
- Recorded The Legendary Poet YouTube channel ID.
- Recorded The Legendary Poet canonical and compatibility VK URLs.
- Recorded The Legendary Poet VK community and owner IDs.
- Recorded the public VK Clips route.
- Classified VK Video cabinet URLs separately from public links.

### Remaining implementation synchronization

The canonical documentation now prefers `https://vk.ru/thelegendarypoet` and permits `https://vkvideo.ru/@thelegendarypoet/clips` for short-form promotion. Source-code allowlists and validators must be checked and synchronized before an executable plan uses those two newly confirmed routes.

The author-cabinet routes must not be added to public renderer allowlists.

### Documentation scope

The following documents are The Legendary Poet-specific despite generic-looking filenames:

- `docs/youtube-description-rendering-standard.md`;
- `docs/vk-description-rendering-standard.md`.

They must not be applied to Господь Бог — Сила Моя as generic defaults. Project-specific scope labels and the theological description profile remain mandatory.

## Fail-closed rules

1. Missing public identity is recorded as `unverified`, never guessed.
2. A credential alias is not a project identity.
3. A shared VK token never authorizes selecting a community without exact numeric guards.
4. A YouTube write token may be used only when the resolved channel ID equals the plan channel ID.
5. A description/comment may use only one project footer profile.
6. Exact playlist URLs must come from live membership, a reviewed plan, or named source evidence.
7. Public and operational/admin routes must remain separate.
8. `cabinet.vkvideo.ru` URLs are never valid public-footer links.
