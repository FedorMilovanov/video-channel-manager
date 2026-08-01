# Two-project link audit — 2026-08-01

## Purpose

Verify the public identities and links for the two separate projects and identify repository places where aliases, historical URLs, or project links were mixed.

Status vocabulary:

- `verified` — confirmed by the owner, live project page, local provider account output, or current published project metadata;
- `compatibility` — currently published or historically used, but not the preferred new viewer-facing form;
- `operational-history` — retained only to explain old artifacts and reports;
- `unverified` — do not place into a new executable plan until live-confirmed.

## Credential conclusions

### YouTube

Two separate OAuth aliases are correct:

- `fedor-milovanov` → current theological channel authorization, read-only on 2026-08-01;
- `legendary-poet` → The Legendary Poet, write-capable on 2026-08-01.

For theological-channel writes, reauthorize `fedor-milovanov` with `--write --force` and require exact channel ID `UCeSJsC6go2c9pdJCuUI1BYA`.

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
| YouTube numeric channel ID | not recorded | unverified | run `youtube channels` before any new write plan |
| VK community | `https://vk.com/thelegendarypoet` | verified/published | current Rutube project descriptions |
| VK.ru equivalent | not recorded | unverified | do not infer automatically |
| VK Video | not recorded | unverified | do not construct from the community handle without a live check |
| VK numeric community/owner IDs | not recorded in current CLI output | unverified | live `vk communities` output required |
| Telegram | `https://t.me/thelegendarypoet` | verified/published | current Rutube project descriptions |
| Rutube | `https://rutube.ru/channel/74579453/` | verified | active project channel |
| Website | `https://thelegendarypoet.ru/` | unverified externally | repository legacy allowlist only; confirm ownership and availability before a new mass rollout |

### Temporary compact footer

Until missing identities are confirmed, use only:

- `https://vk.com/thelegendarypoet`
- `https://t.me/thelegendarypoet`
- `https://rutube.ru/channel/74579453/`

Do not substitute the theological website or theological VK route.

## Repository findings

### Fixed directly in `main`

- Added a canonical two-project registry.
- Corrected the current theological VK URL to `vk.ru`.
- Documented two YouTube OAuth aliases and one shared VK user token.
- Updated root agent instructions, current state, operations index, and project-memory changelog.

### Code defect identified

The unified editorial validator used one global `APPROVED_PROJECT_URLS` set containing only The Legendary Poet links. This caused two risks:

1. theological records could not use their own project links through the generic pipeline;
2. simply adding all links to one union would allow cross-project mixing.

A guarded code change is being prepared in `agent/project-link-profiles` to:

- resolve `project_key` from the explicit record and registered channel ID;
- use exactly one project link profile;
- reject a URL registered to the other project even when placed in a source ledger;
- retain compatibility for existing poet records;
- add regression tests for both profiles.

### Documentation ambiguity identified

The following documents are The Legendary Poet-specific despite generic-looking filenames:

- `docs/youtube-description-rendering-standard.md`;
- `docs/vk-description-rendering-standard.md`.

They must not be applied to Господь Бог — Сила Моя as generic defaults. Project-specific scope labels and a theological description profile are required.

## Fail-closed rules

1. Missing public identity is recorded as `unverified`, never guessed.
2. A credential alias is not a project identity.
3. A shared VK token never authorizes selecting a community without exact numeric guards.
4. A YouTube write token may be used only when the resolved channel ID equals the plan channel ID.
5. A description/comment may use only one project footer profile.
6. Exact playlist URLs must come from live membership, a reviewed plan, or named source evidence.
