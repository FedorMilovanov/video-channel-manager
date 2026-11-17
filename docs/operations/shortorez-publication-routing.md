# SHORTOREZ: adaptive clip publication routing — Issue #940

Status: **provider-inert planning only**, and no publication authority. This module does **not** render media; separately verified MacArthur local cuts were created in later operator work recorded in [Issue #940](https://github.com/FedorMilovanov/video-channel-manager/issues/940). This is an adapter plan to existing provider writers, not a second uploader.

**For direct AI-agent cutting of an already finished video from a chat URL, start at [shortorez-chat-workflow.md](shortorez-chat-workflow.md), NOT this platform planner or Telegram Bot `/mode`.** The historical offline/no-media notes below reflect the November 14 checkpoint and were superseded by November 15 real local renders; publication authorization and final hearing/rights review remain separate.

## Exact first source

Project `lord-god-strength`, owner YouTube channel `UCeSJsC6go2c9pdJCuUI1BYA`, video `5nKCs4bkoxE`, «Познание Божьей воли без тайн (Джон МакАртур)». Full URL: https://www.youtube.com/watch?v=5nKCs4bkoxE. Do not invent cut boundaries from the title. The media/master and authoritative Russian speech transcript need actual readback and listening.

## Distinct surfaces

- VK native Clip: `<= 180s`, native Clips publisher/Creator surface only. Never substitute ordinary VK Video or `video.publish`, and never silently create a wall duplicate.
- Telegram native video: no arbitrary three- or five-minute maximum in this planning module. Separate transport file-size and duration checks stay with the existing Telegram publisher.
- Instagram Reels through Meta API: `<= 900s`. The `<=180s` discoverability preference is editorial, NOT a provider limit. The official Meta spec and actual account/quota must be rechecked before any provider effect.
- TikTok: future, no implementation, account, token or publisher in this wave.

`shortorez_routing.py` takes exact millisecond semantic boundaries and proposes one route per surface; it does **not** render, upload, schedule, edit, or send. Sped-up VK proposals use the smallest allowed rate 1.05/1.10/1.15/1.20 that fits the fully preserved interval, only with opt-in. Telegram and Instagram keep 1.00x by default. Projected runtime is NOT the final measured runtime. Ineligible is a real stop, not a request to cut an argument or quietly raise the rate. Audio pitch preservation and tempo must be proven on the rendered file.

## Preview without any platform call

After genuine RU source listening fixes the millisecond boundaries, prepare a preview:

```powershell
python -m video_channel_manager.shortorez_routing --youtube-id 5nKCs4bkoxE --start-ms <verified-start> --end-ms <verified-end> --allow-speedup
```

This prints `provider_write_performed=false`, `release_authorized=false` and proposed independent routes. CLI cut values MUST be observed, never guessed; `<verified-start>` and `<verified-end>` above are placeholders, not real video times.

## Required staged handoff

1. Reconcile exact rights, approved local master + SHA256, and any already-produced full Russian mixed audio.
2. Extract exact candidate words from that master and verify RU spoken timing, including 3–8s of context around boundaries.
3. Reuse MP3Bot's existing selection/audio/subtitle engineering and its **merged local provider-inert SHORTOREZ export modules** (`services/shortorez_export.py` for the reviewed 177–300s RU-postmix interval gap, `services/shortorez_vk_variant.py` for optional VK speed variants). They are narrow media operators, **not** a general URL-to-clip automation. Never launch the user-facing Telegram Factory `/mode` as an agent background publisher or change its 1.00x production rules. Use the chat workflow for semantic discovery and exact boundary review.
4. Produce approved 9:16 files in the operator-output handoff location, with readable faces and subtitles outside platform safe-zone overlays. Preserve both participants in horizontal Q&A rather than cropping a speaker out.
5. Check start/end syllables, scriptural references, theology, postmix language, pitch/tempo, visual sample frames, FFprobe, bytes and SHA-256. A 1.20x file requires listening to the **final encoded MP4**, not an ASR-only verdict.
6. Prepare separate captions per platform with an **exact HTTPS YouTube watch URL and explicit Russian label** immediately before it (for example, «Полная проповедь: https://www.youtube.com/watch?v=…»). Bare URLs and lookalike video IDs/hosts fail routing handoff. Instagram caption links may be unclickable; verify a real profile/Story link route rather than promising a click.
7. Respect exact project/account/native-media-type binding, real target readback, stable source/interval/variant IDs, lock + journal, prior publishing queues, approval and separate write authority in Video Manager. A passing `validate_render_handoff` is NOT release authorization. No blind retries.
8. TikTok only after later owner consent, rights and independently verified account/API capability.

## Limit evidence checked 2026-11-14

VK official: https://vk-video.production.vklanding.ru/ (native Clips at most 3 minutes)
Meta official: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api (Reels API 3s–15min)
TikTok official: https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide (conditional max by account; future only)

## Known materialization gap and final-duration acceptance

The existing MP3Bot `SHORTS FACTORY MAX` produces 35–177s semantic Shorts and 5–14:57 long-highlight candidates. It does **not** automatically discover 3–5-minute semantic candidates. MP3Bot PR #470 merged the reviewed **177–300-second manual-interval local exporter**, and #473 merged the optional VK native speed derivative; neither is an automatic semantic candidate finder or a second engine. A Video Manager route for 3:30 is a proposal until a source-bound, editor-reviewed interval is handed to the local exporter and its actual MP4 passes QA. Do not alter Factory's Telegram delivery path as a shortcut.

`validate_render_handoff` rejects a final MP4 duration deviating by more than 1.5 seconds from the planned complete interval after its approved speed transform. This is a data-integrity guard, not listening proof: the reviewer must still check both ends for exact Russian words and all transitions. An actually required longer dubbing tail must be represented by a corrected, reviewed interval/render plan; never remove the tail to satisfy a duration assertion.

VK Video officially supports a Clip-linked full VK video with a native **«Перейти к полному видео»** action. Use that only if a read-only, exact-ID VK full-video match is present and approved. Preserve the original YouTube full-version attribution in the caption; never guess a VK remote ID. Source: https://vk-video.production.vklanding.ru/.

## Historical 2026-11-14 checkpoint — no longer live operational state

At this earlier checkpoint `DESKTOP-O3FDOA4` was offline and this workstream had no source-bound render. The later Issue #940 comments document the **actual November 14–15 local MacArthur cuts**: three 1.00x pieces and three VK review variants, eventually remade with full-bleed static-per-source-shot cropping. Check that exact latest owner-local manifest, source SHA, current device state, listening/rights status and actual provider receipts independently. **Six locally rendered MP4s do not mean six published or rights-approved clips.** For current chat cutting, follow [shortorez-chat-workflow.md](shortorez-chat-workflow.md).
