# LordChrist quote-v4 — source-bound editorial amendments (5 November 2026)

**Scope:** `@lordchrist`, prospective quotation series only. This is a read-only editorial addendum to [issue #762](https://github.com/FedorMilovanov/video-channel-manager/issues/762) and the merged [PR #764](https://github.com/FedorMilovanov/video-channel-manager/pull/764), not a new publication queue. It does not modify any published post, original quote or protected ledger.

## Input identity and non-publication contract

- Original candidate index: `docs/audits/2026-11-04-lordchrist-30-quote-editorial-candidate-index.json`, Git blob `46333d8aa7e143bf2b3926449ae72994d04bd59c`.
- Ten further redrafts: `docs/audits/2026-11-04-lordchrist-remaining-10-contiguous-redrafts.json`, Git blob `72418abc451162ccb081a1c31e4dbaaf7f38dfbf`.
- Safety hold: `content/telegram/lordchrist/quote-v4-editorial-safety-hold.json`, Git blob `64ecc7e9eb858319ea89a46ae17bb1bb8df2650e`.
- **Editorial approval: NO. Full bilingual source review: NOT COMPLETE. Translation / jurisdictional rights review: NOT COMPLETE. Provider write authorization: NONE. Release ID/digest: NONE.**
- Never use this document as an approval signal, never alter signed old queue hashes, and never replay the superseded 30 pending depth-v3 entries.

## Corrections grounded in the primary source

### Card 2 — Charles H. Spurgeon, *Salvation — All of Grace*

Primary source: https://www.spurgeon.org/sermons/salvation-all-of-grace

The retained preview has the conspicuous Russian collocation `единственный наш клик`. The author uses *shoutings*, not a click. Proposed exact literary correction: **`единственный наш возглас`**. For a reader-facing attribution, render **`Чарльз Г. Сперджен, «Спасение — всё от благодати»`**; keep the sermon’s English title and bibliographic number in its evidence metadata.

Status: precise language/source correction proposed; no certification of the entire translation.

### Card 3 — Spurgeon, *Divine Sovereignty*

Primary source: https://www.spurgeon.org/sermons/divine-sovereignty (sermon No. 77, 4 May 1856).

The original candidate index ends its English source anchor with `It is God upon the throne whom we trust.`, which (i) drops **his** from the original and (ii) excludes the next two sentences that are **already translated** in the revised Russian preview. The primary source reads `It is God upon his throne whom we trust.` and continues with singing **this morning** and speaking of God on his throne **in this discourse**.

Proposed source-bound `anchor_end`, exact original segment: **`and it is God upon his throne of whom we shall speak in this discourse.`**. Preserve in Russian: `о Боге на престоле мы пели сегодня утром и о Боге на престоле будем говорить в этой проповеди`. Do not truncate the Russian text to conform to the erroneous old anchor.

Status: source anchor and translation-context correction proposed; full bilingual certification pending.

### Card 4 — John Owen, *Of the Mortification of Sin in Believers*

Primary source: https://ccel.org/ccel/owen/mort/mort.i.v.html

The linked edition’s actual displayed heading is **`Chapter II.`**; therefore `глава I` in the source location is incorrect. Proposed exact new source location: **`глава II (Кол. 3:5; 1 Кор. 9:27)`**. Reader-facing title: `Джон Оуэн, «Об умерщвлении греха в верующих»`.

The Russian passage is substantive and worth preserving; this metadata correction does **not** certify every biblical quotation or every English/Russian clause.

### Card 7 — William Gurnall, *The Christian in Complete Armour*

Primary source: https://ccel.org/ccel/gurnall/armour/files/gurnal07b.htm, `Division Third`, application `Use Second`, `Argument 1`.

The existing newly drafted Russian quote claims a continuous source span between `Cold prayer is no more prayer than painted fire is fire.` and the closing `a flame of fire.` but **omits source imagery within that span**. Specifically the original makes an explicit comparison about a **flea or fly versus the sun** (judged by possession of life), and says that an angel’s comprehension is faster and zeal stronger than a human’s. The current draft jumps from moving fountain water to hierarchy of creatures, and from the hierarchy to angelic fervor, without translating those premises. These omitted comparisons are not inconsequential to the logic of the extended analogy.

Proposed editorial repair **before any release**: retain the full chosen source interval and insert these two translated elements at their natural positions:

> `В этом отношении даже блоха или муха считаются более благородными созданиями, чем солнце: ведь у них есть подлинная жизнь.`

> `Ангел постигает быстрее человека, и ревность его сильнее.`

Also revise the current ambiguous `ты открываешь кран` to contextually clear `ты открываешь кран, но вода не идёт: сосуд замёрз` if a literary editor confirms this accurately represents the metaphor `Thou drawest the tap, but the vessel is frozen.`

**Important:** A complete word-by-word collation is still needed after the inserts. A few targeted additions do not automatically make the full quotation `contiguous_complete_no_omissions`.

### Card 24 — George Whitefield, *The Almost Christian*

Primary source: https://ccel.org/ccel/whitefield/sermons/sermons.xlv.html.

The CCEL rendering contains a modern editor’s bracketed gloss `[cow?]` inside the original anchor span concerning Pharaoh’s lean cattle. This square-bracket gloss is **not authorial quoted prose**; record it separately as an edition artifact, rather than silently presenting it as part of Whitefield’s sermon or altering the Russian to imitate the gloss. Full source-interval fidelity remains pending.

### Card 29 — Herman Bavinck, *Philosophy of Revelation*, Lecture 1

Primary source: https://ccel.org/ccel/bavinck/revelation/revelation.ii.html, final section of Lecture 1.

The present revised Russian excerpt begins by translating the preceding sentence `For, since all historical and psychological research...` but the candidate index’s English `anchor_start` begins only at `Belief in such a special revelation...`, **after the first Russian sentence**. Conversely the index’s `anchor_end` is `commend it to the consciences of men.`, substantially **after** the last sentence currently translated in Russian. The source contains a detailed intervening list of theological tasks; a claim of full contiguous translation across the old anchors is incorrect.

If retaining the **existing revised Russian text**, propose these exact-boundary changes:

- `anchor_start`: **`For, since all historical and psychological research into the origin and essence of the religion of Israel and Christianity`**
- `anchor_end`: **`the science of the revelation of God and of our knowledge concerning him.`**

This bounds the actual translated passage from the rhetorical question through the introduction of theology’s glorious task, **without** claiming that the following detailed exegesis/defense list was translated. Verify punctuation and paragraph transition against the chosen edition when producing the release-specific bilingual evidence.

### Card 30 — George Whitefield, *The Extent and Reasonableness of Self-Denial*

Primary source: https://ccel.org/ccel/whitefield/sermons/sermons.xxxi.html.

The candidate source `anchor_start` incorrectly reads `Whoever reads the Gospel with a single eye, and sincere intention, will find`. The actual selected CCEL source starts **`Whoever reads the gospel with a single eye, and sincere intentions, will find,`** (lowercase `gospel`, plural `intentions`, and trailing comma). Proposed exact replacement: that latter string, without silently normalizing the historical source. This is a bibliographical fidelity amendment, not a retranslation.

## Remaining closure criteria for issue #762

The current new 30-card deck comprises **20 candidate redrafts + 10 provisionally retained texts**, yet all 30 remain awaiting complete bilingual collation and edition/translation-rights approval. These focused corrections are additional source-bound evidence, not a claim that those tasks are complete. To close #762 responsibly, reconcile all 30 against source spans, review theological semantics and Russian prose, document rights, create and approve a **new** versioned exact-digest release, retire the hold through the existing reviewed contract, and prove one provider-visible Telegram send plus a matching durable receipt and subsequent scheduled continuity.

No Telegram, Telegra.ph, VK or protected-state mutation was performed in this audit.
