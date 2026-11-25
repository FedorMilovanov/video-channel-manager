# LordChrist Telegram — editorial v2 acceptance (18 Nov 2026)

## Scope and boundaries

This is a **provider-inert** editorial revision to the existing 19 pending quote-v6 cards for @lordchrist, not a new queue or mass reschedule. The eleven already-published messages are immutable. The first restyle manifest and its digest remain historical evidence; the new versioned manifest is **quote-v6-pending-restyle-v2.json**, with prospective digest **sha256:13cac1b9630072b7929d8d96244153284779dc41961469d3f106e289df94eb0d**. The prior state digest is **sha256:62a15d4b19057509fb38023847ccbdbde319f9d428a9d6463074ae11b3940b03**.

## Reader-facing corrections

- Edwards #14: start at the self-contained statement about God's power, rather than "Из этих слов..." without its biblical antecedent. The excerpt is a verbatim, contiguous Russian source span.
- Ryle #18: lead with "Кто хочет понять природу подлинной святости..." rather than "Но существует и другая брань...", which refers to an unquoted prior comparison.
- Ryle #19: lead with "Павел смотрит вниз, на могилу..." rather than "В словах Писания, поставленных в начале этой главы..." without showing the chapter opening.
- Watson #22: retains "Во-первых, довольство — дар Божественный" because it **introduces a complete first definition** without requiring preceding enumerated items. Do not cut into a lowercase word or invent a new translation solely to remove "Во-первых". The reader sees the topic and complete explanation.
- Emphasis now follows meaning. The renderer supports one bold span, one italic span, or both. Author/work attribution remains italic, separate from body. No outer guillemets, no whole-message blockquote, no underscore hashtags. Eleven short excerpts and eight long spans in v1 are preserved except for three additional source-bound contextual reductions in v2.

## Verifications and limitations

- All 19 Russian excerpts are single contiguous spans of the fixed source-v6 Russian corpus. The Russian corpus SHA and English source reference remain unchanged; this establishes **lineage**, not translation correctness.
- All 19 source URLs were opened and their declared start/end English anchor passages found in independently retrieved page text on 18 November 2026. This is anchor matching, **not a complete bilingual clause-by-clause textual collation**.
- The v6 candidate itself still records rights_review_complete=false, responsible_editor_approval=false, and full_bilingual_review_complete=false. Those flags must not be treated as true.
- The [CCEL copyright policy](https://www.ccel.org/about/copyright.html) states that most base books are public-domain in the United States, but specific editions may contain protected components and law differs by country. Proof of provenance/ownership of the **Russian renderings**, and edition-specific rights records, remain outstanding. Neither URL access nor CI success provides a blanket license.
- A safe follow-up must verify the owner of each Russian translation (or commission and independently approve a fresh translation), document applicable publication territory/rights, and collate all selected text against each English source. Do not falsely close these gates as "certified".
- The new migration is strictly state-only: verify old v1 digest plus exactly 11 verified/19 pending, no intents/uncertain effects; rewrite only changed pending payload hashes plus global queue digest. Do not call Telegram provider send. If any item has published or entered an intent, fail closed and re-plan migration.

## Acceptance evidence

- 63 targeted tests passed locally before repository inventory/CI acceptance.
- A detached worktree of the actual protected state at commit 80dbc817 was migrated locally without pushing: 11 published unchanged; 19 pending preserved; 13 pending SHA values and 1 queue SHA updated; no Telegram provider calls.
- Final CI/merge and real state migration must each be verified independently; this document is **not** evidence that either has happened.
