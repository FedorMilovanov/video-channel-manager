# MILOVI CAKE VK — read-only public wall audit using the owner's app service key

Owner issue: [#792](https://github.com/FedorMilovanov/video-channel-manager/issues/792).
Canonical target `project_key=milovi-cake`, community `68859909`, owner `-68859909`.

## Status and limitations

As of 2026-11-05, the owner explicitly reported **no postponed VK posts**. This is a user observation, **not** a provider readback. An anonymous browser navigation hit VK's robot challenge; no credential or CAPTCHA workaround was used.

The locally installed key `vk-milovi-cake-community-key` is genuine and has `wall` scope, but the standard Milovi wall reader requires a user token. VK currently returns group-auth error 27 for multiple read methods. **Do not** test the quarantined `default`, `legendary-poet` or legacy generic `VK_API_TOKEN` again. Their exact values were independently verified identical.

The owner's existing VK app ID is `54555649` (historical repository evidence). Its **service access key** is a separate, public-read-only credential. The app's developer settings may expose one; never mistake an app secret or community wall-publishing key for the service key. A service key may have API-version or method restrictions; actual success is established by this exact read attempt, not by documentation or possession of the key.

## First-time local configuration (no token in Git or terminal output)

On the operator's Windows machine, use the existing ignored local secret file:

`C:\Users\Fedor\Projects\mp3telegrambot\.env`

Add `VK_MILOVI_CAKE_SERVICE_KEY=<actual service access key from own VK app>`. Do not paste its value into issues, chats, source files, a shell command or screenshots. This is **not** the existing `VK_MILOVI_CAKE_API_TOKEN`, which remains reserved for group-authorized writes.

The script refuses a blank key or any key matching **any** other stored VK credential alias, including retired and quarantined tokens. It persists a new exact `token_type=service` alias `vk-milovi-cake-service-key` in the existing secret store, without changing other aliases. `wall.get` is dispatched via the existing official read-only VK API client with `max_attempts=1` and durable per-method VK code-9 flood protection. Provider writes: **0**.

```powershell
Set-Location 'C:\Users\Fedor\Projects\video-channel-manager'
.\.venv\Scripts\python.exe scripts\audit_milovi_school_vk_public_wall.py `
  --env-file 'C:\Users\Fedor\Projects\mp3telegrambot\.env' `
  --output 'C:\Users\Fedor\Projects\video-channel-manager\operator-output\milovi-school-vk-public-wall-audit.json'
```

The output is created only once; an existing output path is not overwritten. The scanner is bounded to 3,000 current public owner posts, requires a stable exact total and owner identity, and rejects truncated, inconsistent, duplicate or unexpectedly empty pages. It collects **no postponed/admin/private/native Articles**. It compares all ten canonical Milovi School article URLs in text, links and repost history, and returns exact public wall post IDs for matches.

## Execution gate after this read

Even a full public wall snapshot showing zero matches **does not prove** the absence of a scheduled, VK-native Article, video or administratively hidden object. It does **not** authorize `wall.post`. A reviewer must separately inspect the exact admin `Отложенные` queue (user currently reports empty), the Article surface, and check that no concurrent publisher changed state. Only after a reviewed single-post canary with frozen payload/date, per-community mutex, a durable journal and postflight can any publication be scheduled.

Do not automatically publish all ten posts. Continue preserving the 12 historically migrated restricted Clips `-68859909_456239225…456239236` without reuploads or privacy changes.
