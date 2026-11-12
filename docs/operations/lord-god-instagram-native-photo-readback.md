# Lord God Instagram - native independent IMAGE receipts (13-15 November 2026)

This GET-only monitor fixes a separate weakness from photo publishing. GitHub scheduled workflows were delayed by many hours on 12 November 2026, including independent photo receipt workflows. The publisher moved to one protected native Windows job in PR #907. This monitor adds no publishing authority.

## Exact behavior
Calling scripts/instagram/lord_god_quote_windows_readback_20261113.py with --preflight verifies source SHA, the frozen owner-approved plan, exact Page and Instagram account and the current Meta feed, using only GET. It does not consume a publication attempt or write to SQLite.

Scheduled invocation takes no arguments and is permitted from 14:00 Moscow on the approved dates 13, 14, 15 November 2026. Register exactly one job with three one-time triggers, 14:05 Moscow each day. It invokes the previously audited independent script scripts/instagram/lord_god_quote_receipt_readonly_20261112.py with its SHA-256 pinned in scripts/wave-executors.json. The original readback checks IMAGE, exact caption, Moscow day, numeric media ID and Instagram HTTPS permalink. Exit 0 proves the Meta image; exit 2 means missing or error.

The wrapper imports the verified dedicated Page token reader and source integrity checks from PR #907, refuses GitHub Actions environments and writes local append-only daily logs. Tokens are neither printed nor committed. All Meta calls use GET, with no publication retries.

## Protected deployment
1. Merge the PR after CI and Gitleaks.
2. Copy the exact merged new wrapper and pinned independent readback source to the isolated E:/VideoChannelManager/Instagram/LordGod/20261113-photo-schedule release. Update only the executor registry inside that release folder. Do not modify the shared development tree.
3. Recheck SHA-256 including existing photo publisher and frozen plan, then run --preflight with zero provider writes.
4. Register one Windows Task Scheduler job named VideoChannelManager-Instagram-LordGod-Photo-Readback-20261113-15, interactive Fedor session, three enabled one-shot triggers (13,14,15 November at 14:05 Moscow), MultipleInstances IgnoreNew, WakeToRun and StartWhenAvailable.
5. Inspect state Ready, exact dates and next run; do not start scheduled mode manually.

The existing late cloud readback remains GET-only but is not the authoritative on-time check. A missing receipt must be investigated before any new manually approved slot. The computer must stay on and logged in for native tasks; this is not cloud high availability.
