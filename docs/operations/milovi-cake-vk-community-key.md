# Milovi Cake VK community key — safe first-time access

Issue: [#792](https://github.com/FedorMilovanov/video-channel-manager/issues/792).
Project identity is **`milovi-cake`**, community ID **`68859909`**, wall/video owner ID **`-68859909`**.
The shared `default` / `legendary-poet` VK *user* token is quarantined. Never probe or replay it.

## One-time creation in VK (human administrator)

1. Sign in at [Milovi Cake](https://vk.com/club68859909) as its authorized administrator.
2. Open **Управление → Дополнительно → Работа с API → Ключи доступа → Создать ключ**.
3. Grant **доступ к записям на стене (`wall`)**. Add **photos** only if the approved publisher actually needs to upload photographs. Do not grant messages, documents, stories or broad management privileges just for wall posts.
4. Complete VK's required confirmation. The administrator must not paste the key into an issue, chat, screenshot, Git log, shell history or repository-tracked file.

## Import using the repository's official client

On the operator Windows machine, in a PowerShell window with an interactive terminal:

```powershell
Set-Location 'C:\Users\Fedor\Projects\video-channel-manager'
.\.venv\Scripts\python.exe -m video_channel_manager vk community-key-login --account vk-milovi-cake-community-key --community 68859909
```

When prompted, paste the **new community key**; input is hidden.
The `community-key-login` command deliberately ignores the global `VK_ACCESS_TOKEN` user-token fallback. It validates `groups.getTokenPermissions` with `wall` and `groups.getById` exact community binding **before** storing the key under a new alias. Never use `--force` on a quarantined alias.

If an authorized local secret-file workflow is preferred, use the existing `--token-file` option only with a locally protected, untracked file, and remove that transient file after successful import. Do not place it under a committed path.

Check the exact saved key after import:

```powershell
.\.venv\Scripts\python.exe -m video_channel_manager vk community-key-capabilities --account vk-milovi-cake-community-key --community 68859909
```

This is a **read-only two-method check**. Do not repeat it automatically on error 9 or use it to reset any quarantined token circuit.

## Deliberate capability boundary

- Community `wall` permission provides the basis for a separately authorized **wall read / postponed publishing** workflow, subject to fresh provider readbacks and its own reviewed execution gate. An imported key itself never authorizes a publication.
- Official `video.get` and `video.edit` are user-token methods; a community key does **not** prove the admin visibility/privacy state of the 12 previously uploaded clips. Exact video owner-side UI review or a newly, legitimately consented user OAuth key is a separate task.
- VK-native Articles and VK-video uploads are **not** implied by wall-access validation.
- Before any wall post: current full-enough published + postponed inventory, exact URL/content deduplication, rights review, source and owner verification, one small scheduled canary, durable journal, exact provider postflight.
- For the 12 #323 native Clips `-68859909_456239225…456239236`: public direct clients returned a manager-restriction message. Do not re-upload, unhide, reschedule or edit until exact admin-state reconciliation establishes a reviewed action.

As of 2026-11-05 the new key has **not** been supplied or validated. Provider writes: **0**.
