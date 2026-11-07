# Lord God YouTube: evidence-led description repair

This is the durable operating guide for the lord-god-strength YouTube project. It does not grant standing provider write permission. Resolve the user's current request and the exact operation's authorization first. Owning legacy-description issue: https://github.com/FedorMilovanov/video-channel-manager/issues/795. Older issue comments are evidence, never current state.

## Exact target and identity

- Project key and link profile: lord-god-strength.
- Owner YouTube channel ID: UCeSJsC6go2c9pdJCuUI1BYA.
- OAuth alias: fedor-milovanov. Verify the exact returned channels.list(mine=true) ID and granted write scopes; the alias alone proves neither.
- One video per signed description plan. Metadata-only descriptions: do not reupload video, rewrite the title or visibility, change audio/captions, or touch other channels.
- A clean count based only on absence of old shelf_id links does not certify source rights, factual accuracy, contact cleanup or SEO. Never report a historical or estimated count as a new owner-API scan.

## Recurring agent bugs and their fixes

**Raw versus prefixed SHA-256:** Python hashlib.sha256(text.encode("utf-8")).hexdigest() returns 64 hexadecimal characters. The signed-plan helper video_channel_manager.platforms.youtube.copy_plan.sha256_text(text) returns the literal prefix "sha256:" plus those characters. Validate archival raw digests using hashlib; validate signed plan before_sha256 and after_sha256 using sha256_text. Never disable hashes to overcome a representation mismatch.

**Script restart:** Before anything, inspect exact plan IDs, existing immutable backups, terminal receipts and active processes. A stopped script that signed 20 plans but did not write must resume from those exact validated plans, not sign over them. After any provider dispatch, reconcile each video by an independent owner GET before resuming. An ambiguous or rolled-back write is not authorization for another PUT.

**Windows UTF-8:** Non-ASCII PowerShell here-strings sent over remote transport may turn Cyrillic into literal question marks. Write a UTF-8 Python/JSON file, verify the file content and SHA locally, then run python -X utf8. A malformed console display is not evidence that the underlying source document is corrupt.

## Editorial source retention

Study the exact original video title and owner description and a meaningful portion of its transcript. Do not invent Bible references, historical quotes, timecodes or speakers from a few keyword hits. When reading an old historical sermon, distinguish its original author from a modern narrator or translator.

The Lord God project presentation gate now calls the pure function source_preservation_issues(before, after) before provider OAuth. It fails closed if any of the following old, non-obsolete evidence disappears from the proposed new description:

- Original chapter lines and their exact question/topic labels, including stamps in h:mm:ss format.
- Original translation, attribution, copyright, or primary-recording/source-credit lines.
- Primary-source links, independent video URLs, specific Telegram posts and other non-retired references.
- Original YouTube playlist IDs even if the URL scheme or query parameter ordering changes.

This is a preservation gate, not a rights grant. Original links must still be checked for relevance, availability and licensing. Actual playlist owner and exact video membership must be verified by official API, including several valid playlists in one video. Playlist mismatch or source uncertainty is a HOLD; do not silently delete an unverified link or invent membership.

The only automatically exempt links are proven obsolete owner channel shelf/navigation URLs, retired personal contact URLs and retired donation endpoints. Every other URL needs preservation or a documented editorial decision. All third-party source/media rights remain separately reviewable.

## Bounded, evidence-led big waves

1. GET-only owner inventory. Reconcile the exact original cohort; exclude already-clean, ambiguous-write, rollback and special-source/title/playlist-held IDs. Do not depend on an old list without checking fresh live state.
2. Choose 20-50 distinct candidates by popularity, related series and transcript quality. Read the source evidence and prepare individual descriptions. Keep all source material, working links and existing chapter timestamps.
3. Fresh official owner preflight: channels.mine, videos.list in up to 50 IDs per call, owner/public/current title, exact original-before raw SHA, and every archived playlist's channel ownership and actual membership. A title or SHA drift blocks that video.
4. For each approved video generate one signed v3 plan, exact current before/after text and hashes, unique immutable backup and receipt filenames. Run the project presentation and source preservation validators.
5. Dry-run ALL approved plans before the first mutation. Require Ready: 1 and no unexpected revision drift. Do not relax the rules to force a green run.
6. Execute only one video at a time using official protected CLI. On ReadTimeout, ambiguous outcome or failed postflight STOP. Independently reconcile exact after, exact safe-original rollback or never-attempted state. Never blindly repeat a timed-out upload/write.
7. Independently read back all attempted IDs and the full original video cohort; report observed clean/dirty, old shelf link occurrences, old operator contacts, missing IDs, unexpected clean IDs, regressions and remaining editorial holds. A wave is complete only after reconciliation.

## Agent handoff and branches

Use the current supported main code in a clean isolated worktree. Do not modify other agents' shared Windows checkout. For a code or documentation fix, use one focused PR, run tests, merge and retire the ephemeral work ref. Keep machine reports and signed plans on the authorized E: work area or the operator's explicitly selected folder; cite exact file paths and digests in the owning issue. Local scratch scripts alone are not a durable repository fix.

Regression tests (offline, no provider calls):

    python -m pytest -q tests/test_lord_god_presentation.py tests/test_lord_god_source_preservation.py
