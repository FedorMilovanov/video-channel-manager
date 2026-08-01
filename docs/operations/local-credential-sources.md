# Local credential sources

Updated: 2026-08-01

This file records local credential locations and usage rules without storing any secret value.

## VK user access token

- Local source file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`
- Environment key in that file: `VK_API_TOKEN`
- Token model: one VK user token is shared by both managed projects and communities.
- Current Video Channel Manager token-store alias: `legendary-poet`

The alias is only a credential label. Every VK operation must still bind exact `project_key`, `community_id`, and `owner_id`.

## Required behavior

1. Never copy the token value into this repository, documentation, command history, issue, pull request, log, report, plan, or ZIP.
2. Never print the token or include it as a command-line argument.
3. Do not ask the operator to paste a VK token manually when the external `.env` file exists and contains `VK_API_TOKEN`.
4. Normal VK scans and guarded writes use the already imported local token-store alias `legendary-poet`; they do not need the `.env` file on every run.
5. If the local VK token must be imported or replaced, the CLI should read `VK_API_TOKEN` silently from the external `.env` file.
6. The external file remains outside this repository and must never be copied into `data`, an operational package, or Git history.
7. Missing, empty, unreadable, or invalid external token input must fail without displaying the secret and without silently selecting another credential.
8. A shared token never selects a community. Exact numeric provider guards select the target.

## Planned configuration behavior

The application settings layer should use this precedence for VK token import:

1. explicit process/local project setting `VCM_VK_ACCESS_TOKEN`;
2. existing encrypted/ignored Video Channel Manager token-store entry for the requested alias;
3. external file `C:\Users\Fedor\Projects\mp3telegrambot\.env`, key `VK_API_TOKEN`, when an import/login operation needs token material;
4. interactive hidden prompt only when all configured non-interactive sources are absent.

The external source path may be overridden with `VCM_VK_SHARED_ENV_FILE` on another machine. The default resolves to `%USERPROFILE%\Projects\mp3telegrambot\.env`, which equals the path above on the current Windows workstation.

## YouTube OAuth

YouTube does not use `VK_API_TOKEN`. It keeps two separate local OAuth aliases:

- `fedor-milovanov` — Господь Бог — Сила Моя;
- `legendary-poet` — The Legendary Poet.

OAuth browser authorization and locally ignored token files remain separate from the shared VK token source.
