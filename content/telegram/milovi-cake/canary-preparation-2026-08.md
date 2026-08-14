# Milovi Cake Telegram — exact canary preparation

Status: **provider-inert / execution blocked**  
Owning issue: #353  
Candidate: `milovi-cake-canary-001`

This document prepares one future canary. It does not authorize or perform a Telegram mutation.

## Why the first canary is a photo

The current Milovi visual archive contains both WebP photographs and WebM videos. The reviewed Telegram Bot API contract is friendlier for a first photo mutation:

- a multipart-uploaded photo may be up to 10 MB;
- the photo caption may contain up to 1024 characters after entity parsing;
- photo dimensions still need to satisfy Telegram's total-dimension and aspect-ratio constraints;
- Telegram documents MPEG4 as the video format supported by clients for `sendVideo`, while other formats may be sent as documents.

The current Milovi videos are `.webm`. A canary is the wrong place to silently discover whether a planned native video becomes a document or receives different provider treatment. Therefore the first canary candidate is a finished-work photo; WebM-backed editorial slots remain editorially valid but transport-blocked for native video until a separate conversion/readiness lane exists.

## Exact candidate

The machine-readable source of truth is `canary-candidate-2026-08.json`.

Selected finished-work media:

- media ID: `p18`;
- source repository: `FedorMilovanov/Milovi_Cake`;
- source commit: `c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370`;
- source path: `img/gallery/gallery-18-hd.webp`;
- source Git blob: `3574f726b233583a77b8a6db885f91b49e5189d8`;
- repository-reported byte size: `195742` bytes;
- gallery identity: `Премиальный торт с золотом`.

The file is far below the reviewed 10 MB multipart photo limit, but byte size alone is not enough to mark transport readiness.

## Exact candidate caption

The candidate intentionally avoids prices, availability, delivery timing, customer context and claims about the photographed cake that are not in the gallery source.

> Milovi Cake — торты и десерты в Санкт-Петербурге.
>
> Здесь — реальные работы Milovi Cake, красивые детали и подборки, полезные подсказки перед заказом и короткие истории французской кондитерской культуры из Milovi School.
>
> Основатель и кондитер — Виктория Милованова.
>
> https://milovicake.ru/

The location, founder/pastry-chef identity and primary site are bound to the pinned `Milovi_Cake/llms.txt` source. The caption is intentionally plain text: no hashtag wall, no hidden link syntax, no first-person Victoria voice, no fake scarcity and no claim of production/BTS access.

## Why `p18`

This is a technical canary, not a declaration that `p18` is permanently the first editorial slot. The selection is deliberately conservative:

- finished-work photo, not production footage;
- one clear premium Milovi visual;
- no need to explain a customer story;
- no dependence on seasonal availability;
- no video compatibility/conversion question;
- no need for a rich multi-item album to prove the first provider mutation path.

After a successful verified canary, editorial order can still follow the reviewed 30-slot sequence. Canary success proves the exact transport/identity path; it does not rewrite the editorial strategy.

## Transport preparation boundary

`media-delivery-readiness-2026-08.json` intentionally leaves `transport_ready=false` because the repository metadata currently proves the source blob and byte size, but the canary file has not yet been materialized and decoded in the publishing environment.

Before authorization, a pre-dispatch media probe must:

1. materialize the exact `p18` bytes from the pinned Milovi_Cake commit, not from a moving branch without verification;
2. compute a byte-level SHA-256 and freeze it in the reviewed candidate/release artifact;
3. decode the WebP and record width/height;
4. prove width + height is within the reviewed Bot API limit and aspect ratio is within the reviewed limit;
5. prove the selected upload code path treats the file as photo media;
6. refuse dispatch if the actual bytes, type, dimensions or digest differ from the reviewed candidate.

Do not weaken this to "the image opens in a browser". Provider dispatch should use the exact bytes that were reviewed.

## Target preparation boundary

The candidate deliberately has no numeric target yet.

Before authorization, a **new** Milovi discovery run must execute from current `main`; rerunning the old failed GitHub Actions run is not equivalent because GitHub reruns execute the original workflow SHA.

The fresh read-only proof must establish:

- project `milovi-cake`;
- channel `@MiloviCake`;
- one exact negative numeric `chat_id`;
- round-trip numeric resolution to the same public channel;
- bot id `8716602202` / username `@preaching_mp3_bot`;
- exact membership status `administrator` or `creator`;
- `can_post_messages=true`;
- the profile digest used to build the immutable target binding.

Only after review is that exact proof frozen into the candidate's immutable target binding. Username-only sending is not an acceptable replacement.

## Authorization boundary

Even after target and media readiness are complete, the candidate remains provider-inert until the owner explicitly authorizes **one exact canary mutation**.

Authorization must identify the exact candidate/release digest and exact target binding. It must not be interpreted as permission for:

- a second post;
- pinning;
- scheduled posting;
- invite-link creation;
- bulk archive fill;
- Dzen/VK cross-posting;
- automatic retries after an unknown provider outcome.

## Post-dispatch verification boundary

If the canary is later authorized and dispatched, the operation is not complete merely because the HTTP request returns.

The outcome must be archived and reconciled against the exact expected channel, bot, message/media shape and text. If the transport outcome is unknown or provider evidence is incomplete, replay is blocked until the original mutation is reconciled.

Only a verified canary outcome can become evidence for a subsequent separately reviewed rollout step.

## Video lane after photo canary

Do not use `sendDocument` as a silent fallback for the current WebM files just to make them "postable". The product intent is native visual media.

A later video-readiness lane should deterministically create Telegram-native outputs from the exact source videos and record at minimum:

- source media ID/blob;
- output MP4 byte SHA-256;
- video codec/container;
- width/height;
- duration;
- file size;
- poster/thumbnail decision;
- source-to-output provenance;
- exact editorial slot(s) allowed to use that output.

That conversion work remains separate from the first canary and must not alter the original Milovi_Cake gallery files.
