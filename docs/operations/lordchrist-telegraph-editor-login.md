# Telegraph: personal EDIT access without changing publication

**Scope:** `@lordchrist` Telegraph L3 articles, the existing `LORDCHRIST_TELEGRAPH_ACCESS_TOKEN` account. No new account, no browser automation, no impact on scheduled or manual article publishing.

## One-time setup (private owner only)

1. In Telegram, open a direct private dialog with **the exact bot already used by `LORDCHRIST_TELEGRAM_BOT_TOKEN`**, and send `/start`. A channel chat is not suitable.
2. Determine the Telegram numeric ID of **your private dialog** with that bot (not the channel ID). Do not put the ID in source files or PRs. If you do not have it, obtain it using a user-ID service you trust, or from the existing bot's private-chat updates where operationally supported; do not modify the publishing bot to discover IDs.
3. Save the ID as the GitHub Actions **repository secret** `LORDCHRIST_TELEGRAPH_EDITOR_CHAT_ID` in `FedorMilovanov/video-channel-manager`.
4. Keep the existing secrets `LORDCHRIST_TELEGRAPH_ACCESS_TOKEN` and `LORDCHRIST_TELEGRAM_BOT_TOKEN` unchanged. Do **not** create a second Telegraph account or rotate/revoke the original token.

## Login to a browser — only when you want EDIT

Go to **Actions → Lordchrist Telegraph editor login (private on demand) → Run workflow**, select `main` and enter `AUTHORIZE_EDITOR_DEVICE`.

The workflow verifies that the requester is the repository owner, that the recipient is a pinned private chat, and that the existing Telegraph account can edit the already published `Rabstvo-svobody-11-11` page. It then asks Telegraph for its `auth_url` and delivers that **one-use, five-minute** URL to the private chat; neither URL nor access tokens enter GitHub logs, outputs or artifacts.

Open the link on the **same browser/device where you want EDIT** (on a phone, select your preferred external browser rather than Telegram's embedded webview). Afterwards you can open normal article links, including `https://telegra.ph/Rabstvo-svobody-11-11`, and use **EDIT → PUBLISH**. The public article URL does not change. Repeat only for another browser, after browser data is cleared, or when the browser's Telegraph session is otherwise lost. This is **not** triggered by article publishing, agents, or a schedule.

The delivery may fail if the bot does not have a private dialog with you. In that case the link is **not** shown in logs; start the bot and run a **new explicit** authorization workflow only when needed. Never retry an in-progress run.

## Publishing remains exactly the same

Existing `lordchrist-telegraph-poster.yml` and its staged single-send ledger continue unchanged. Agents and phone-triggered GitHub Actions publish as before. They do not open/register browsers or require an editor session. The new workflow cannot post to `@lordchrist` or create/edit a Telegraph page.

**Manual corrections are live changes outside Git.** Editing an article in Telegraph does not rewrite the Git Markdown/JSON or the separate Telegram channel message. Before an agent is *explicitly* asked to edit a previously published Telegraph page via `editPage`, it must first read the current page and reconcile manual edits. The existing one-shot staged publisher **creates** pages rather than updating an already published page, and its durable ledger prevents a blind second send.

Security: never share an `auth_url` or access token, copy it into GitHub, attach it to a PR, or expose it through public workflow logs. Whoever opens the fresh auth URL first may acquire access to the Telegraph account.
