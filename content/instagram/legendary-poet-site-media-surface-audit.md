# The Legendary Poet — site media surface audit for Instagram

Status: provider-inert  
Source repository: `FedorMilovanov/TheLegendaryPoet`  
Source commit reviewed: `d59cceccb0c49af59b1be38d4c547a6240b3005a`

## Finding

The current site repository is **not the exhaustive video archive** of the project. It is an editorial/library source with images, canonical text/provenance data and three local published audio masters. The checked source tree does not contain a local MP4/WebM library corresponding to the YouTube channel.

Therefore “move every Short/Reel/full video to Instagram” must not be implemented as a site-file copy loop. Correct coverage is:

```text
site/editorial authority
+ current YouTube read-only inventory
+ frozen YouTube↔VK exact-ID mapping
+ project-owned clean media archive
→ Instagram Reel intake
```

The site is authoritative for what it actually owns; the YouTube channel inventory is authoritative for the remote video estate; the clean-master archive is authoritative for media bytes.

## Exact site-owned music masters

The current `src/data/library/musicTracks.ts` exposes exactly three published playable tracks.

| Track | Duration | Exact local master | SHA-256 | Instagram status |
| --- | ---: | --- | --- | --- |
| Сергей Есенин — «Я усталым таким ещё не был» | 280.241633 s | `/audio/yesenin-ya-ustalym-takim-eshche-ne-byl.tlp-2026.mp3` | `2f5b7c0a9b83be4685d0d83728e5896c8adde78b75b46dad361eddfb28356381` | strong Reel source; video/vertical render required |
| Александр Пушкин — «Туча» | 263.904 s | `/audio/pushkin-tucha.tlp-2026.mp3` | `1d4f77fb01ccd31a4fe8934281fc7771157b7f9a0373529ca97ad0aafa86ff30` | strong Reel source; video/vertical render required |
| Александр Блок — «Россия» | 257.664 s | `/audio/blok-rossiya.tlp-2026.mp3` | `feb6d1607278fce8621000a542e76e075cca5a6b44cf63c0a9db67603b943c9d` | strong Reel source; video/vertical render required |

The site itself states that the musical interpretation/master belongs to The Legendary Poet, that the poem text is public domain for these releases, and that generative music technology was used. That disclosure must survive Instagram rendering.

## What “published on the site” means operationally

The site music catalog has explicit helpers for:

- `availability === 'published'`;
- playable only when a published item has `audioUrl`;
- published/playable counts;
- total duration;
- featured track;
- adjacent/related tracks.

This means the site can be treated as a clean **audio release registry** for these three works, but not as proof of a clean video master for the corresponding YouTube upload.

## Reel conversion from site-owned audio

Each exact audio master should yield a small set of genuinely different vertical productions rather than many arbitrary cuts:

1. one performance-first Reel after waveform/listening review;
2. one source/form Reel;
3. one visual/editorial Reel;
4. one transparency/provenance or full-work bridge Reel.

That is the 12-slot site-audio contribution already enumerated in `legendary-poet-reels-factory-plan.md`.

No start/end timings are frozen here because the current repository evidence gives the whole master, not reviewed best-span decisions.

## Site articles as Reel source authority

The current site also supports non-performance Reel families whose authority is the article/library source rather than an existing YouTube ID:

- Лермонтов — `Выхожу один я на дорогу…`: chronology, source-vs-myth, close reading;
- Пушкин — `Евгений Онегин`: 1823 start, Mikhailovskoye work, Boldino completion;
- Маяковский: public futurism / ROSTA / LEF / vulnerable lyric / anti-single-cause 1930 treatment;
- current poet/library records and essay media for further art-first Reels after exact source review.

These are legitimate Instagram sources even when there is no exact YouTube video ID. They must be labelled as `site_editorial_rebuild`, not disguised as remasters of a nonexistent video.

## What was deliberately not inferred

- no local video file ⇒ **not** proof that no clean video master exists elsewhere;
- a YouTube ID ⇒ **not** proof that the site owns the YouTube delivery bytes as a reusable master;
- a short runtime ⇒ **not** proof of YouTube Shorts classification;
- a portrait/article image ⇒ **not** automatic permission to animate it into a historical “real scene” without provenance framing;
- a poem title ⇒ **not** permission to quote arbitrary remembered text; canonical edition/span still applies.

## Result

The site contributes three exact hashed audio masters and a large editorial source corpus. The whole-video migration must be driven by the channel inventory, not by pretending the site contains files it does not contain.