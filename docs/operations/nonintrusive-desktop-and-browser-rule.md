# Non-intrusive desktop and browser operation

This is the default operating contract for agents, operator scripts, local tools, and remote access working on the owner's Windows computer. It applies to **all project_keys**, including Milovi Cake and Legendary Poet. It does not grant provider-write authority.

## Default: the owner's desktop is hands-off

- The owner is actively using the machine. Treat the visible desktop, mouse, keyboard, clipboard, active window, browser tabs, logged-in profiles, notifications, and session state as **owner-owned, not automation infrastructure**.
- Do **not** open Chrome/Edge/Firefox windows or tabs, switch or focus windows, click/scroll/type in visible applications, move the pointer, inject keystrokes, attach DevTools/CDP to the owner's interactive browser, open a browser with `Start-Process`, or dismiss dialogs as a side effect of investigation.
- Do **not** use screen scraping, screenshots, global shortcuts, cookie/profile extraction, or foreground UI automation to work around missing API authorization. Existing `focus_*`, `click_*`, browser-probe and other ad-hoc scripts are **not** standing permission to run them.
- Do not automatically open File Explorer or another visible application as an output handoff convenience. Printing the verified exact file path is sufficient; the owner decides when to open it.
- Do not close, restart, kill, or reconfigure any owner browser or browser profile to finish an agent task. Do not create proliferating profiles, browser installations, logins, or account sessions.
- A tool being capable of acting on the desktop, an old successful browser session, or an earlier login instruction does not supersede this rule.

## Preferred transport, in order

1. **Official provider API / repository-owned CLI**, with exact target identity, least privilege, durable no-replay semantics and provider postflight.
2. Read-only HTTP/source inspection; GitHub/remote shell operations with bounded scope. Never consume another agent's mutable session or change the user's active workspace.
3. Headless browser tests **only in a truly isolated CI runner, container, or dedicated noninteractive desktop/session** with a new throwaway profile, no owner cookies, no foreground window, no focus changes, and bounded CPU/memory. An invisible/headless flag on the owner's interactive session is **not by itself** proof of isolation.
4. If a provider has no supported safe API, classify that operation as **blocked / owner-interaction-required**. Do not silently downgrade to interactive UI automation.

## Rare, explicit UI exception

Only a **fresh, explicit, task-specific request from the owner** to operate a particular GUI can permit visible browser automation. Before it starts, explain the exact account, page, intended actions, expected effect on the user's foreground desktop, and a bounded window. Obtain acceptance specifically for interruption; general instructions to "continue", "finish to zero" or old approvals do not qualify. Stop immediately if the owner resumes working or the page/target is uncertain. Keep interaction to one existing approved profile and one window; no credential capture or hidden CDP attachment. Verify the target and result; close only windows the agent itself created with consent, never the owner's windows.

If login, challenge, 2FA, or a new OAuth grant is required, offer **one** official URL or precise manual step, explain why, and then wait for the owner to complete it. Do not open it remotely or poll the visible browser. Never ask for passwords, session cookies, or verification codes.

## YouTube OAuth working-directory trap

When a program defaults to relative `./data`, **each current directory has its own token store**. OAuth can have write permission in one shell while a second shell sees only an older read-only token. The canonical signal is the **resolved token directory printed by `video-manager youtube accounts`**, the granted scope and exact channel ID, not the account alias or a remembered success message. For provider writes, set `VCM_DATA_DIR` to one verified **absolute path** (and `VCM_YOUTUBE_CLIENT_SECRET_FILE` to a verified absolute file if needed); do not copy, export, move or print credential files. Do not retroactively rewrite the user's credential stores or alter the project checkout to reconcile this without an explicit reviewed migration plan. No agent-opened OAuth/browser windows.

## Required preflight and reporting

- Record the transport as `official_api_read`, `official_api_write`, `local_only`, `internal_web_read`, `isolated_headless_test`, or `explicit_visible_ui`; prove whether it touches the interactive desktop.
- Before remote command execution, verify the selected device and avoid commands that start visible apps or manipulate focus. Keep agent work in an isolated worktree; never reset/clean the owner's dirty checkout.
- In an operational handoff, report separately: work completed without desktop interaction, actions needing explicit owner interaction, and any provider permissions still missing. A policy-imposed stop is not "zero", but it is preferable to hijacking the owner's workstation.
- Browser automation launched by a CI test is not permission to control the user's Windows desktop. Provider mutation still requires the repository's separate exact-operation write gate.

## Regression policy

When changing agent guidance or operator entrypoints, keep this rule linked from root `AGENTS.md` and `.github/copilot-instructions.md`. Test that both point to the same canonical contract. Do not copy stale screenshots, ephemeral account names, login links, or browser script filenames into the durable instructions.
