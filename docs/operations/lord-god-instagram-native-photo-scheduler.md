# Lord God Instagram: native photo release authority, 13?15 November 2026

The owner-approved Instagram Charnock quote on 12 November did not publish: the GitHub 12:45/13:10 Moscow schedule events were delivered at 20:44/21:10, after the hard release window. We do not automatically replay 12 November.

## Single writer and protected cutover

The only program performing Meta photo POST remains scripts/instagram/lord_god_quote_cloud_20261111.py. It uses the exact four-JPEG manifest protected by whole-file SHA-256, exact Page/Instagram account, provider-media preflight, caption check, processing-state poll, and final media-ID/permalink receipt.

GitHub workflow lord-god-instagram-quote-cloud-20261111.yml must have NO schedule event after cutover. It remains workflow_dispatch preflight only. The publisher additionally rejects legacy scheduled mode within GitHub Actions, including delayed scheduled events from an older workflow revision.

The sole photo writer for the remaining approved 13, 14, 15 November dates is the Windows native task invoking scripts/instagram/lord_god_quote_windows_runner_20261113.py. It has exactly two one-shot triggers each day at 12:45 and 13:10 Moscow, six total; allow wake and start when available, but the publisher rejects running before 12:45 or after 14:00.

## Durable single-attempt claim

After offline manifest/image SHA checks, Page token identity, and exact provider feed readback, the publisher atomically inserts a claim in the existing C:/Users/Fedor/Projects/video-channel-manager/data/video_manager.db SQLite database using BEGIN IMMEDIATE and the unique primary key (account_id, publication_day). This happens BEFORE the first Meta POST. No later task invocation is allowed to POST again for a claimed date even if the previous result was ambiguous; manual forensic reconciliation is mandatory. A verified Meta media ID and permalink advances the claim to VERIFIED. Tokens are never stored in SQLite.

The native wrapper checks the protected source SHA-256 in scripts/wave-executors.json, uses ONLY the dedicated already-existing Lord God token from the local private .env file, refuses any GitHub Actions environment, and records the result in an append-only daily operator log. It accepts no arbitrary date or caption arguments.

## Deployment and rollback

1. Merge the protected PR with all required CI jobs and Gitleaks SUCCESS.
2. Atomically stage the exact merged Python, manifest and execution registry bytes in an isolated directory on drive E, separate from the active dirty development worktree.
3. Verify SHA-256 and run the wrapper with --preflight: it must complete all four GET-only image/account checks with PREFLIGHT_OK_NO_POST and must NOT make any provider POST or SQLite claim.
4. Verify the original GitHub workflow no longer has schedule triggers. Register only ONE native Windows scheduled task, limited to the six one-time triggers, under the existing interactive Fedor user. Do not add a second publishing writer or modify the separate existing Reel tasks.
5. Check one task, six exact triggers, working entrypoint, user context, no existing same-day photo claim, and native task status Ready.
6. Rollback must first disable the sole Windows photo task. Do not re-enable GitHub scheduled writer without a coordinated exclusive-ownership handoff and explicit owner approval. Any claimed day requires evidence reconciliation, never a blind retry.

The native task depends on the computer being powered on and the user session being available; it is not an HA cloud system. A later cloud migration requires reliable hosted scheduling, a secret store, durable distributed ledger, stable HTTPS media assets, independent provider readback and an exclusive transition from this writer.

Owner-approved photo captions and images, local video Reels, and six unapproved carousels remain unchanged. Missed 12 November content needs a newly approved date; no unauthorized reschedule.
