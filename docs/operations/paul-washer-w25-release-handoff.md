# Paul Washer W25 — local handoff and release-boundary checklist

Scope: issue [#894](https://github.com/FedorMilovanov/video-channel-manager/issues/894), media prepared outside this repository on the owner's Windows PC. This is a *case-specific handoff* for agents, not a provider implementation, approved copyright license, mutable release ledger, or replacement for `AGENTS.md`. Baseline verified 2026-11-14; always re-read the current local files before acting.

## Exact source and owner-facing copy

- **Authoritative local source:** `E:\VideoChannelManager\Paul_Washer_DoYouTrulyKnow_20261109\deliverables\`
- **Derived media package:** `WASHER_MEDIA_W25_20261112\`
- **Full review MP4:** `Paul_Washer_Do_You_Truly_Know_RU_W25_SUBTITLE_REVIEW.mp4` (stored one level above the derived package).
- **Current human-gate snapshot:** `WASHER_MEDIA_W25_20261112\W25_EDITORIAL_RELEASE_GATES.json`.
- **Review-only metadata:** `WASHER_MEDIA_W25_20261112\YOUTUBE_RELEASE_PLAN_SOURCE_CORRECTED_REVIEW_ONLY_20261113.json`.
- **Handoff requested by owner:** `C:\Users\Fedor\Downloads\Пол Вошер - Знаете ли вы Господа (полная проповедь и 10 роликов)\` (one readable copy, not a relocated canonical source).

The owner-facing folder was verified to contain **11 MP4 / 30 files / 683,387,048 bytes**, including full (~51:28) + six vertical Shorts + three horizontal thematic clips + one highlights compilation, accompanying SRTs, technical evidence and a README. Four `H01`–`H04` intermediate render parts are not four additional scheduled videos.

The copy operation checked **29 file-by-file source/destination SHA-256 pairs** and produced one README. Original E: files were retained. The original QA/metadata JSON still refers to absolute E: paths, so copying the JSON does **not** make the review plan portable or an executable upload spec. Do not rename, delete, overwrite or recode the E: masters in a user-facing handoff. Do not change media identities based on pretty display names.

### Windows export regression prevention

- A requested user-facing Downloads destination overrides the default `operator-output` path for that particular handoff; it does not change the repository's persistent outbox rules for unrelated work.
- Explicitly distinguish **copy**, **move** and NTFS `hardlink`/`junction`. Different physical drives cannot share a file hardlink. If owner-readable physical copies are requested, check available space first, copy once, compare SHA-256 for each selected file, verify final file count, and retain original evidence.
- A previous remote PowerShell invocation failed on `Get-FileHash`. Confirm the command exists in that shell, or use `System.Security.Cryptography.SHA256` with properly disposed streams. Do not claim success after partial output. The subsequent .NET-based verification completed.
- Remote Windows output may display Cyrillic as question marks; inspect the actual NTFS Unicode file name or code points before declaring that a filename was corrupted.
- Do not duplicate the full media set in Git or in `operator-output`. The case handoff is intentionally outside Git.

## Provenance: distinguish recording, uploader, rehost and rights owner

The **actual input video** is [YouTube `ObjG_dr3lrU`](https://youtu.be/ObjG_dr3lrU), uploaded by **Turrettini Pizza** on **2013-12-07**; this is an uploader, not a proven rights grantor. The HeartCry/SermonAudio [alternate record](https://www.sermonaudio.com/sermons/619181111312/a) is a separate archival reference, not the physical video-bytes source and not a downstream redistribution license.

A contemporary eyewitness link and historic campus filename suggest **2013-10-09** at The Master's College chapel, but **the event date is not finally verified**. The `2016-06-12` SermonAudio date cannot be the date of an already-public December 2013 recording; it must not be advertised as the sermon date. Likewise, the old `© 2016` assertions were removed from the corrected review-only copy. The legacy `pw-2016-...` release keys remain in **11 old review records**; they are *historical identifiers, not date evidence*. Before changing them, prove there is no durable plan/journal binding; never reset upload identity to bypass idempotency.

Written rights **remain unverified**, including the original recording/underlying visual rights, translation/dubbing, edited excerpts and thumbnails. HeartCry was contacted; The Master's University was separately asked to establish ownership and license scope. Neither attribution nor non-monetization nor a private YouTube upload replaces the needed license.

## Different status sources are not interchangeable

The W25 engineering audit reports 51-minute and ten-clip decode PASS, 13 derived SRTs PASS, and preserved original video/RU AAC/EN AAC streams. It is **not** editorial/publishing approval.

The newer `W25_EDITORIAL_RELEASE_GATES.json` records owner listening verdicts of **PASS** for 31:51 and 43:45 post-AAC excerpts; older engineering reports correctly preserve earlier historical `PENDING` snapshots. Do not rewrite immutable old QA or assume newest timestamp wins: record the later gate verdict with witness SHA and explicit chronology.

Still **OPEN**: full ~51-minute human listening, review of all ten clips' ends/content and 9:16 framing (pay attention to S03 tracked crop jumps), 21 RMS *pause candidates* requiring human triage (not 21 proven defects), approved final cover, verified licenses and publisher-write authorization.

## Correct release sequencing (do not skip)

1. Freeze exact original media SHA values, source identifiers, approved captions and editor-reviewed statements. Derive each public title/description from the **actual clip**, not an automatically inherited source-credit block; use normal Russian grammar, the canonical channel's title separator, substantive first two description lines, and accurate source/rights attribution. Keep `permission unconfirmed`, `REVIEW_ONLY_NO_UPLOAD` and other internal gate text **out of public metadata**.
2. Verify **`project_key=lord-god-strength`**, exact YouTube channel `UCeSJsC6go2c9pdJCuUI1BYA`, credential alias `fedor-milovanov`, live owner identity and a fresh read-only duplicate scan. Do not route this series to The Legendary Poet.
3. When and **only when** editorial and written-rights gates pass, produce fresh `video-manager.youtube-video-upload-spec` **v2** inputs from the separately reviewed source. The ad-hoc W25 `SOURCE_CORRECTED_REVIEW_ONLY` JSON **is not** a canonical v2 upload spec or executable release approval. Its old November 13–22 tentative slots are not valid; compute a new future schedule in Europe/Moscow only after clearance.
4. Use current-main repository-owned guarded writer and durable per-video upload key, not a temporary Python/PowerShell HTTP writer. Create and validate the intent, release plan and child-specific execution authority separately. Begin with the supported private-only upload process **after licensing**, reconcile any ambiguous response read-only, and verify remote IDs, metadata, thumbnail, playlist and actual schedule individually.
5. Keep the audit state explicit: `LOCAL_MEDIA_ENGINEERING_PASS`, `HUMAN_EDITORIAL_PENDING`, `RIGHTS_UNVERIFIED`, `PROVIDER_NOT_DISPATCHED`. A successful copy into Downloads or a pretty preview never promotes these gates.

## Related sources

- [Video Manager issue #894](https://github.com/FedorMilovanov/video-channel-manager/issues/894) (primary W25 evidence and task owner)
- [Video Manager operator handoff rules](operator-output-handoff-rule.md)
- [Video Manager YouTube upload spec](../../src/video_channel_manager/youtube_upload_plan.py) and [canonical release plan](../../src/video_channel_manager/youtube_release_plan.py)
- [MP3Bot direct dubbing](https://github.com/FedorMilovanov/mp3telegrambot/blob/main/docs/agent_direct_dubbing/README.md) and [Shorts/Downloads guidance](https://github.com/FedorMilovanov/mp3telegrambot/blob/main/docs/agent_direct_dubbing/CLIPS_SHORTS_AND_HANDOFF.md)
- MP3Bot [handoff/presentation PR #457](https://github.com/FedorMilovanov/mp3telegrambot/pull/457) already covers general Russian-file naming and video descriptions; do not duplicate that unfinished PR in another unrelated branch.

No action in this checklist is standing authorization for uploading or changing YouTube content.


## Owner verification checkpoint — 2026-11-15 (after prior publication)

This section is a later read-only snapshot, not a retroactive modification of W25's original publication hold or approval ledger. The user's direct request was to audit the already published video and repair metadata where safe.

- Exact owner: YouTube UCeSJsC6go2c9pdJCuUI1BYA / account alias fedor-milovanov.
- **Public** Russian/postmixed video: Ba-1IHVz3H8, 51:28, file size 332187297; 19 source-anchored chapters recognized publicly; custom thumbnail present; Russian and en-US localized title/description exist.
- **Unlisted** predecessor: 5bQDzxVM40g, 51:28, separate English-audio-serving upload; do not confuse or overwrite either URL.
- Owner captions.list returned **one auto-generated ru ASR track** on the public release and **one auto-generated en ASR track** on the unlisted predecessor. **No uploaded, human-edited RU SRT or other language track** was reported on the public release. contentDetails.caption=false does not supersede caption-track API evidence.
- The ten derived W25 clips remain local; no exact filename/title match was found among the owner inventory of 1870 videos on Nov 14. Do not infer publication or permission from an old tentative schedule.
- Three owner playlists contain both video IDs: Проповеди, Открой глаза, Пол Вошер | Paul Washer. Removing the unlisted predecessor from public playlists is a separate owner mutation, requiring an exact guarded plan and readback; never delete the source video by default.
- **Cross-speaker metadata bug:** the public Paul Washer video retained 25 tags, including irrelevant John MacArthur / Shepherds Conference entries. Its license was creativeCommon despite no documented onward relicensing authority. The narrowly scoped scripts/youtube_exact_video_metadata_repair.py can fix only that one existing video's frozen tags/license, without touching title, description, 19 chapters, privacy or localizations. It requires exact source state, dry run, local lock, immutable backup and verified provider readback. Standard YouTube license is a platform setting and **does not confer or establish source rights**.
- W25 human review, SRT QA, original/translation rights, ten-clip listening and full-bleed visual checks remain distinct release gates. **Do not upload new W25 media or multilingual subtitle tracks solely to make a dashboard show zero.** Refer to MP3Bot AGENTS.md and docs/agent_direct_dubbing/README.md for the editorial lock.

Never print OAuth secrets, automate the owner's interactive browser or silently promote REVIEW_ONLY artifacts to public-ready.
