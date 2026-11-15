# Lord God Instagram: independent native Reel receipts, 13?21 Nov 2026

## Authority
The only Reel publisher is the pre-existing Windows task at 19:00 Moscow. The new script `scripts/instagram/lord_god_reels_windows_readback_20261113.py` is **strictly GET-only** and reuses the exact protected cloud proof (`lord_god_reels_readback_cloud_20261112.py`). It cannot create containers, upload bytes, publish, or retry terminal records.

## Schedule and verified result
Install exactly one Windows Task Scheduler job `VideoChannelManager-Instagram-LordGod-Reels-Readback-Late-20261113-21`, with 18 one-time triggers: Nov 13?21 at 20:10 and 20:45 MSK. Use interactive `Fedor`, `IgnoreNew`, `WakeToRun`, `StartWhenAvailable`. The wrapper refuses scheduled operation outside these dates or 20:05?21:15 MSK. Manual `--preflight` is GET-only, with no publication claim, and is safe anytime.

The original proof checks exact Page/IG account, 12-row plan SHA, source/caption digest, Meta media product REELS, exact Moscow day, numerical `media_id` and HTTPS Instagram permalink. Returns exit 0 ONLY on real provider receipt; exit 2 for missing/unproven result or error. Logs are appended in the isolated release's `operator-logs/reel-readback-YYYY-MM-DD.log`. Keep cloud scheduled readback as secondary GET-only evidence; GitHub cron was delayed by hours on Nov 12.

## Deployment
Merge via protected CI/Gitleaks. Add the exact new wrapper and protected readback engine to the existing isolated `E:\VideoChannelManager\Instagram\LordGod\20261113-photo-schedule` release; atomically replace ONLY its executor registry with protected main bytes, preserving photo writer and photo readback files and schedules. Validate SHA-256 of both reusable engines, the 12-row readback manifest, registry and credential helper, then execute only `--preflight`. Register the one new readback job and verify its 18 dates, state Ready and exact action path. Never manually trigger scheduled publishing or replay Nov 10?12 terminal keys.

## Blockers
Meta rupload returned `1363008 OIL FILE_NOT_FOUND`, with zero recorded uploaded bytes, even though local MP4 SHA and codec checks passed. This monitor does not repair Meta's upload. Public video_url transport requires deliberate, secure, rights-reviewed media hosting and an exclusive publisher cutover; no public GitHub Release uploads are authorized by this change.

## Readback drift and immutable v2 cutover, 15 November 2026

The initial deployment instructions above describe the original installation. A subsequent correction for delayed GitHub cron was merged into `main`, but the active `20261113-photo-schedule` readback code was still pinned to older hashes. The Desktop Commander Node.js process held the active `wave-executors.json` open with Windows nonsharing semantics. The attempted direct CAS replacement failed and was **fully rolled back**; closing that process or forcing partial file replacement would be unsafe.

The stable recovery procedure is to stage the exact **nine-file** readback bundle from one protected `main` commit in a *new* root: both GET-only wrappers, both readback engines, the frozen quote/Reel manifest files, quote credential helper, protected quote-source proof and the single executor registry. Verify SHA-256 of every source entry and both frozen plan hashes; run both `--preflight` checks using the exact native task interpreter. Then export original Windows readback task XML/action receipts, move the immutable bundle to `E:\\VideoChannelManager\\Instagram\\LordGod\\readback-20261115-v2`, and change **only** those two GET-only Task Scheduler action paths. Preserve each task's original principal, exact one-shot triggers, next-run date/time, `IgnoreNew` settings and all publication ownership. If either action fails its postflight contract, restore both actions from backup.

Actual 15 November cutover: both readback tasks returned `Ready` with the same next runs (photo 14:05 and Reel 20:10 Moscow), and both active-root `--preflight` invocations returned 0 with GET-only Meta. The photo publisher, Reel publisher, and MILOVI CAKE writer tasks were **not changed**. The old shared registry remained byte-identical; the new isolated registry is a distinct frozen file. This corrects *readback version drift* but does not repair historical Meta `1363008` / `OIL FILE_NOT_FOUND` Reel ingestion or authorize any replay.
