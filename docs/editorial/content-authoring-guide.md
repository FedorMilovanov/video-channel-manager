# Content Authoring Guide

## 1. Choose a factual angle

Use one documented angle that belongs to the specific work: composition history, first publication, manuscript history, textual structure, archival provenance, documented context, adaptation history, or performance history.

A strong fact contains names, dates, editions, manuscript states, documented circumstances, or a precise formal observation supported by a source. A weak fact can be pasted under any poem.

## 2. Map claims to sources

List every evidence source in `sources`, then place the supporting IDs in both top-level `source_ids` and `fact.source_ids`. Repository paths must be relative and may not escape the repository. URLs must be absolute HTTP(S) URLs.

Do not cite a source merely because it mentions the author. It must support the actual claim in the paragraph.

## 3. Write the heading

Use one contextual marker and a concrete noun phrase. Prefer “Две редакции одного морского текста” to “Великий шедевр Тютчева”. YouTube may add restrained emphasis; VK will remove that markup cleanly.

## 4. Write the question

Ask about something visible or audible in the material: a structural transition, a contrast, an image, a performance choice, or the relation between the documented context and the presented version.

Avoid “Понравилось ли вам?” and “Что вы думаете?”.

## 5. Select links

The project site and VK community are stable project routes. Add only links relevant to the work: the correct author playlist, a VK album, the primary text, the original work, or a full version. Do not add every available channel link to every record.

Keep labels compact. The URL must remain on the same line as its label in every rendered surface.

## 6. Assign variation and suitability

`variation_key` identifies the exact factual angle, not merely the author. Good keys include the work, angle, and revision, for example `tyutchev-night-sea-two-editions-nice-v3`.

Use `platform_suitability` to prevent a record from being rendered onto an inappropriate surface. Use `platform_targets` only for stable reviewed IDs; live target state still comes from a fresh snapshot.

## 7. Review before approval

An approved record requires `reviewed_at`. Preview both platforms, inspect mobile line shapes, validate URLs and sources, and compare the batch for duplicate variation keys and duplicate rendered text.
