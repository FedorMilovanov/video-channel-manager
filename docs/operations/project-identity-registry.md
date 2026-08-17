# Project identity registry

Updated: 2026-08-17

This repository operates three separate media projects owned by Fedor Milovanov. They are never aliases of one project and must not be mixed in descriptions, comments, playlists, manifests, API writes, reports, ledgers, results, or public footer links.

Every provider operation declares one `project_key` and binds exact provider identities. Credential aliases are labels, not project identities.

## Credential model

### YouTube

YouTube uses channel-specific local OAuth aliases:

| Project | OAuth alias | Exact channel ID |
| --- | --- | --- |
| `lord-god-strength` | `fedor-milovanov` | `UCeSJsC6go2c9pdJCuUI1BYA` |
| `legendary-poet` | `legendary-poet` | `UC-78ys2S3cQ3lpqgXfo-SvQ` |
| `milovi-cake` | `milovi-cake` | `UCMDnxfGZiBqcDzgUV1zjFpw` |

Every scan or write verifies the exact returned channel ID. Reauthorizing one alias never substitutes another project.

### VK

VK uses one user access token for all managed communities. The current local token alias is `legendary-poet`, but that alias only names the stored credential belonging to user `Федор Милованов`. It is not a project selector and does not mean each group needs a separate token.

The same rule applies to browser authentication. The same already-authorized VK browser profile/session may be reused across all VK communities currently registered in this repository because they are managed by the same owner/admin account. In particular, a working VK session previously used for The Legendary Poet may also be used for Milovi Cake; a separate browser profile is not required merely to isolate projects.

A browser profile/session is authentication context, not target identity. Prefer reusing a known-working authorized profile instead of creating another profile or forcing another VK login. Before any `browser_ui_write`, still prove the exact `project_key`, `community_id`, and `owner_id` in the active target surface before file selection or any provider mutation. If the session lacks management rights or exact target proof fails, stop before the write.

Project isolation requires exact:

- `project_key`;
- `community_id`;
- `owner_id`;
- project link profile;
- manifest, plan, journal, result, and postflight.

Never select a community by VK alias, browser profile, display order, remembered context, or vanity route alone.

## Project 1: Господь Бог — Сила Моя

- Project key: `lord-god-strength`
- Content: Scripture study, theology, sermons, translations, biographies, apologetics

### YouTube

- Handle: `@fedormilovanov`
- Public channel: https://www.youtube.com/@fedormilovanov
- Videos: https://www.youtube.com/@fedormilovanov/videos
- Shorts: https://www.youtube.com/@fedormilovanov/shorts
- Channel ID: `UCeSJsC6go2c9pdJCuUI1BYA`
- OAuth alias: `fedor-milovanov`

A guarded write requires write scope and exact resolution to `UCeSJsC6go2c9pdJCuUI1BYA`. Alias `legendary-poet` must never be substituted.

### VK

- Community: `† Господь Бог - Сила Моя! †`
- Canonical public URL: https://vk.ru/the_lord_god_is_my_strength
- Compatibility URL: https://vk.com/the_lord_god_is_my_strength
- VK Video: https://vkvideo.ru/@the_lord_god_is_my_strength
- Community ID: `60805374`
- API owner ID: `-60805374`
- Shared VK credential alias: `legendary-poet`

Historical `gospod_bog` routes are operational references, not canonical viewer-facing links, unless freshly verified and registered.

### Other registered links

- Website: https://gospod-bog.ru/
- Telegram: https://t.me/lordchrist
- Rutube: https://rutube.ru/channel/1876662/
- Odnoklassniki: https://ok.ru/christjesus
- Facebook: https://facebook.com/groups/116164165395881

Default compact footer: website, Telegram, canonical VK, VK Video, and Rutube only.

## Project 2: The Legendary Poet — Легендарный Поэт

- Project key: `legendary-poet`
- Content: poetry, literary history, music, AI-assisted creative experiments

### YouTube

- Handle: `@TheLegendaryPoet`
- Public channel: https://www.youtube.com/@TheLegendaryPoet
- Videos: https://www.youtube.com/@TheLegendaryPoet/videos
- Shorts: https://www.youtube.com/@TheLegendaryPoet/shorts
- Channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- OAuth alias: `legendary-poet`

Every write binds exactly `UC-78ys2S3cQ3lpqgXfo-SvQ`. The Lord God alias/channel must never be substituted.

### VK

- Community: `The Legendary Poet - Легендарный Поэт`
- Canonical public URL: https://vk.ru/thelegendarypoet
- Compatibility URL: https://vk.com/thelegendarypoet
- Public Clips route: https://vkvideo.ru/@thelegendarypoet/clips
- Community ID: `235216998`
- API owner ID: `-235216998`
- Shared VK credential alias: `legendary-poet`

Operational/admin routes are not public links:

- https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet
- https://cabinet.vkvideo.ru/dashboard/@thelegendarypoet?filterPreset=published&section=video_my_content&subsection=video_my_content_clips

### Other registered links

- Website: https://thelegendarypoet.ru/
- Telegram: https://t.me/thelegendarypoet
- Rutube: https://rutube.ru/channel/74579453/

Default public footer: website, Telegram, canonical VK, and Rutube. Add the public Clips route only when the target text specifically promotes short-form material. Never put `cabinet.vkvideo.ru` in public output.

## Project 3: Milovi Cake

- Project key: `milovi-cake`
- Content: author cakes, bento cakes, wedding/children's/3D cakes and handmade desserts
- Exact provider identity was re-proved by a read-only operator snapshot on 2026-08-10 under Issue #257.

### YouTube

- Handle: `@milovi_cake`
- Public channel: https://www.youtube.com/@milovi_cake
- Channel ID: `UCMDnxfGZiBqcDzgUV1zjFpw`
- OAuth alias: `milovi-cake`

The read-only provider snapshot returned channel title `Milovi Cake`, `customUrl=@milovi_cake`, and exact channel ID `UCMDnxfGZiBqcDzgUV1zjFpw`. A handle must never substitute the exact channel ID in operational identity.

### VK

- Community: `Milovi Cake - Торты и Десерты - Санкт-Петербург`
- Canonical public URL: https://vk.ru/milovi_cake
- Compatibility URL: https://vk.com/milovi_cake
- Community ID: `68859909`
- API owner ID: `-68859909`
- Shared VK credential alias: `legendary-poet`

The shared VK credential is only authentication. The target is selected by `project_key=milovi-cake`, `community_id=68859909`, and `owner_id=-68859909`.

The same VK browser session used for the other registered Fedor-managed communities is valid for Milovi Cake when that session has the required admin rights. Do not require a Milovi-specific browser login/profile solely because the target project is Milovi; prove the exact Milovi target immediately before any UI mutation instead.

### Other registered links

- Website: https://milovicake.ru/
- Telegram: https://t.me/MiloviCake
- Dzen: https://dzen.ru/milovicake.ru

Only cake content belongs to Milovi cake-transfer queues. Personal/family/non-cake channel material is always out of scope unless a separate reviewed operation explicitly says otherwise.

## Mandatory isolation rules

1. Every plan, journal, report, backup, and manifest includes `project_key`.
2. Every YouTube operation binds exact expected channel ID, not only alias/title.
3. Every VK operation binds exact community and owner IDs, not token alias, browser profile, or vanity URL.
4. Each plan uses only the selected project's registered link profile.
5. Cross-project promotion is forbidden by default and requires an explicit per-operation exception.
6. Unknown links, handles, routes, or IDs fail closed.
7. Preflight prints resolved project, YouTube channel, OAuth alias, VK community/owner, and link profile.
8. The shared VK alias `legendary-poet` and any shared VK browser session never determine the project.
9. Public and admin routes remain distinct.
10. Source-code profiles and validators stay synchronized with this registry; documentation alone never authorizes writes.
11. Only one exact project-bound owning issue may authorize the next operation.
12. Milovi Cake read-only reconciliation is owned by Issue #257; that issue does not authorize provider writes or deletion.
13. Reuse of an already-authorized VK browser profile is preferred over creating per-project browser profiles; exact target proof remains mandatory before every browser write.

## Required identity checks

Lord God:

```text
project_key: lord-god-strength
YouTube OAuth alias: fedor-milovanov
YouTube channel ID: UCeSJsC6go2c9pdJCuUI1BYA
VK community ID: 60805374
VK owner ID: -60805374
```

Legendary Poet:

```text
project_key: legendary-poet
YouTube OAuth alias: legendary-poet
YouTube channel ID: UC-78ys2S3cQ3lpqgXfo-SvQ
VK community ID: 235216998
VK owner ID: -235216998
```

Milovi Cake:

```text
project_key: milovi-cake
YouTube OAuth alias: milovi-cake
YouTube channel ID: UCMDnxfGZiBqcDzgUV1zjFpw
VK community ID: 68859909
VK owner ID: -68859909
```

One shared VK token and one shared authorized VK browser session may serve all three registered communities; exact numeric IDs and `project_key` decide the target. Any mismatch stops without scanning or writing.
