# Milovi Cake Telegram — v12 first new native-video candidate

Scope: #809. Provider-inert review only. Zero Telegram sends or scheduling.

## Source and target

- Exact target: @MiloviCake, chat -1002215328390, @preaching_mp3_bot id 8716602202.
- Official read-only target discovery SUCCESS: GitHub Actions run 42108264699, can_post_messages=true.
- Source repository: FedorMilovanov/Milovi_Cake, gallery data.js blob SHA1 63abde1e044b767ef556d868401a57475a1b28dd.
- Owned source: img/gallery/videos/video-12-wedding-heart.webm; SHA256 ae0b07734b86433ede54494096de05f4794bc5801d2a3fffe7ea62e4ced19cb3, 740815 bytes, 10.008 seconds, 720x1282 VP9/Opus.
- Telegram-ready accepted MP4: protected ref agent/milovi-video-accepted-73c578eff825, commit f4f5512d7b60f1b9c61c293c07620b128536df27, artifacts/milovi-telegram/video/milovi-v12.mp4, SHA256 8ebdd2f5b9747399acf6559f1642327ac736ff585007c6c5d54102f90ef3997c, 2367134 bytes.
- Source site wedding landing https://milovicake.ru/svadebnye-torty/ returned HTTP 200 on 2026-11-05.

## Duplicate evidence

The bounded public archive at https://t.me/s/MiloviCake yielded 21 distinct visible messages through #26, last on 2026-08-18. Among eight messages with video-related markers, #6, #9, #11 and #14 are VK link previews, not native Telegram videos. The four native-video posts are #13 (48s), #16 (59s), #19 (28s) and #20 (21s).

A contact sheet of their public video thumbnails against five frames of our 10s v12 source shows different subjects. Different durations also exclude an exact byte-identical v12 video among these four public native posts. This does not prove absence of private/deleted or inaccessible historical items.

Local read-only evidence (not committed):
- operator-output/milovi-telegram-dup-evidence-20261106/all8-contact-sheet.jpg
- operator-output/telegram-milovi-lordchrist-public-readonly-20261105.json, SHA256 9c927d80479c6428326605159bb1edbe9bac3cea091dfd1ba154b795df648eaf

## New proposed provider-inert bundle

Publication ID: milovi-feed-20261107-001, proposed 2026-11-07 10:30 Moscow.
Content: v12 video, factual concise caption, real wedding landing, two topical hashtags.
Exact files:
- content/telegram/milovi-cake/november-first-video-candidate-20261107.json
- content/telegram/milovi-cake/releases/milovi-feed-20261107-001-runtime.json
- content/telegram/milovi-cake/releases/milovi-feed-20261107-001-video.json
- content/telegram/milovi-cake/releases/milovi-feed-20261107-001-execution-authority.json

Repository validator: valid=true, payload_kind=video. Release_authorized=false, execution_authorized=false, provider_mutation_allowed=false. State not initialized, no provider write.

## Remaining gates, not bypassed

- Final visual/copy and audio-rights review (an owned video does not automatically establish a background-music licence).
- Specific owner sign-off binding publication ID, caption, exact media and execution time.
- New release and execution authorization for this ID, guarded state initialization, current-main and exact target proof.
- Single supported Milovi permanent feed workflow, 09:00–21:00 Moscow, durable intent before one Telegram attempt, verified remote message ID/readback.
- Recurring posting schedule requires separate content-reviewed releases; neither #809 nor this document activates one.

No edits to active Milovi Instagram/VK branches, config, tokens, state refs or historical release approvals.