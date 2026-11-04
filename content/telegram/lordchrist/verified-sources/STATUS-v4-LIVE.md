# Lordchrist Quote Queue v4 (live, 2026-10-28)

Active queue: `content/telegram/lordchrist/verified-30-posts.json` (30 posts, schema v3).
All sources anchored to **ccel.org / www.ccel.org / www.spurgeon.org / spurgeon.org** only, with contiguous verbatim English proof files (01–45 except the non-primary batch moved to `_superseded_nonprimary/`).

Authors represented: J. C. Ryle, C. H. Spurgeon, John Owen, John Calvin, Augustine, William Gurnall, Richard Baxter, Stephen Charnock, Andrew Murray, John Bunyan, Jonathan Edwards, Matthew Henry, Thomas Watson, John Flavel, George Whitefield, Abraham Kuyper, Herman Bavinck.

Format (per post): 2–3 contiguous quote paragraphs (each ≥80 chars) → `© Author, «Work»` → `#hashtags`. No editorial commentary, no out-of-context snippets.

Russian author-name transliterations verified against Russian Christian publishing/web sources (see session notes).

## Full-original re-verification (2026-10-29)

Every post was re-checked sentence-by-sentence against the **complete original books** (CCEL full texts, EEBO/Evans TCP first editions, publisher mirrors), not only against the recorded excerpts, including a surrounding-context read (±3.5k chars) to rule out out-of-context use.

- Confirmed verbatim in the full originals (≥94% sentence coverage; residue is punctuation/edition spelling only): sequences 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26. No context reversals found.
- Sequence 2 (Spurgeon): genuine; one synonym retouch in the recorded excerpt ("deservings" for "merits") — meaning unchanged.
- Sequence 27 (Bunyan): tightened — two paraphrased join sentences and the appended Revelation 21:4 tail were replaced with Bunyan's contiguous verbatim sentences; retranslated.
- **Sequences 28 (Kuyper), 29 (Bavinck), 30 (Whitefield): the previously recorded "verbatim" excerpts were synthesized paraphrases — not one sentence occurs in the books.** Replaced with contiguous verbatim passages from the full originals (Kuyper, *To Be Near Unto God*, Meditation I; Bavinck, *Philosophy of Revelation*, Lecture I; Whitefield, *The Extent and Reasonableness of Self-Denial*, sermon opening, Franklin 1740 / Evans N03789) and retranslated in full.

New queue digest after the first pass: `sha256:50fee0e0a5208495d36646bb9fb741c9769fe446679a7da2e1c5fc425d2ddefb`, superseded the same day by the second-pass digest below.

## Second pass: multi-source re-verification + editorial audit (2026-10-29)

Every post was re-checked against a **second, independently generated source** (CCEL ThML text dump, EEBO/Evans TCP first editions, deeproots Murray text, ochorus CCEL mirror) in addition to the Ecumenical-Christian-Library CCEL mirror — 60+ source documents consulted across both passes. One new defect found and fixed: **sequence 8 (Baxter)** — the recorded final paragraph ("Oh, what a thing is it, to have the charge of immortal souls…") does not occur in *The Reformed Pastor*; replaced with Baxter's contiguous continuation of the same Dedicatory Epistle ("Nor must we be silent while men are hastened by you to perdition…") and retranslated. Second-source sentence coverage: seq 28/29 = 100%, seq 27/30/25/21/22 ≥ 92%, seq 10/11 ≈ 89%; the residue is edition differences (EEBO spelling, Outler translation, punctuation).

Editorial audit of all 30 Russian texts (logic completeness, no dangling references, no duplicates, no banalities): fixed Gurnall transliteration (Герналл → Гарнелл, the form of the Russian Мирт edition, 2002; RSL catalogue), a typo in seq 15, a calque in seq 21, a case error in seq 23, a word form in seq 24, the duplicated Watson paragraph shared by seq 21/22 (removed from 22), and seq 1's tautological title. Sequence 22 now opens at "Holy contentment is a divine thing".

New queue digest: `sha256:a3e5bd757b49996f5db27d46427ce3e6909ce1cf8146d41f6bd316081a2065dd` (activation + schedule rebound).

Author-name transliteration audit (2026-10-29): Gurnall — Russian book tradition (Мирт 3-volume translation, 2002, RSL card; Russian Сперджена) gives «Гарнелл»; «Гурналл» occurs in one devotional edition, «Гёрналл»/«Герналл» in no Russian source — queue uses «Гарнелл». Кёйпер confirmed by Russian Wikipedia (издание Шандал's «Кайпер» is a cover variant); Бавинк confirmed by the same article. Seq 28 location now cites the Psalm by Synodal numbering (Пс. 72:28).

New queue digest: `sha256:a3e5bd757b49996f5db27d46427ce3e6909ce1cf8146d41f6bd316081a2065dd` (activation + schedule rebound).
