# Operational attempt history

This directory preserves failed, partial, superseded, and overcomplicated workflow attempts so future agents can search real code history instead of repeating the same mistakes.

## Safety boundary

- Historical code is stored only inside Markdown code blocks.
- Nothing here is a supported Python or PowerShell entrypoint.
- Nothing here authorizes VK or YouTube writes.
- Never copy a historical script into `scripts/` and run it without a new reviewed design, tests, and the current supported operator contract.
- Tokens, browser profiles, downloaded media, local ledgers, logs, and generated result files are excluded.

## What belongs here

Archive an attempt when it produced a meaningful failure, false conclusion, provider-contract discovery, unsafe pattern, or a useful intermediate design. Every archive must preserve:

1. chronological sequence;
2. exact source snapshot or exact commit/package digest;
3. intended goal;
4. observed result;
5. root cause;
6. misleading assumption or false conclusion;
7. permanent rule;
8. regression test or supported-code requirement.

## What does not belong here

Do not commit secrets, tokens, cookies, browser profiles, media files, private logs, mutable live snapshots, or full local `data/` directories. Do not use this archive as operational state. Fresh provider state is acquired only when a concrete operation needs it.

## Current archives

- [`legendary-poet-vk-clips-2026-08-03-04/`](legendary-poet-vk-clips-2026-08-03-04/) — progression from automated Shorts sync through native VK Clips upload and successive checkers.
- [`lord-god-strength-vk-audio-2026-08-03-04/`](lord-god-strength-vk-audio-2026-08-03-04/) — progression from one-file VK Audio canaries through playlist/metadata automation, read-only network probes, and reliable batch upload experiments.
