# Lordchrist multi-lane editorial portfolio

Owner: Issue #240.

This document is an editorial planning contract. It does **not** authorize Telegram provider writes and does not replace any existing release, target, ledger, canary, state, or execution gate.

## Why this exists

The first live Lordchrist campaign is a strong source-verified quote corpus, but a channel can still feel repetitive even when every individual post is good. The first correction rotated authors inside that queue. The next correction is broader: separate **source review order** from **reader-facing editorial variety across content classes**.

The machine-readable source of this portfolio is:

`content/telegram/lordchrist/editorial-portfolio-v1.json`

## Current lanes

### 1. Legacy quotes — live now

The immutable 30-post primary/public-domain queue remains the only currently `live_ready` lane. Its queue bytes and approved digest are unchanged. Runtime author rotation prevents one author block from monopolizing the next posts.

Reader-facing role: a compact primary-source devotional voice.

### 2. Historical preaching research-v2 — next activation target

Five original Russian evidence-backed posts are already present and fact-check accepted:

1. `Не рекорд, а мера труда` — why Calvin/Spurgeon/MacArthur headline sermon counts are not directly comparable;
2. `Перо, стенографист и магнитная лента` — how preaching survived across manuscript, print and recording eras;
3. `Учиться у тех, кто жил до нас` — influence across generations without turning one preacher into the final standard;
4. `Один текст — три манеры проповедовать` — three patterns of exposition;
5. `Невидимая дисциплина` — the preparation rhythm behind the pulpit.

This is already a qualitatively different feed from the quote lane: comparison, historical analysis, archival/media history and ministry practice. It remains provider-inert until its independent execution/canary gate is completed.

### 3. «Серия Сердце» — first expansion family

The current Research authority records an 85-source closure, strong primary/open/official/academic coverage, merged Site implementation and verified production ancestry. That makes it a much better next adaptation family than starting another random web-search batch.

Recommended first Telegram-native mini-series:

1. `Что значит родиться свыше?` — compact biblical/theological explainer;
2. `Четыре почвы: почему одинаковое Слово даёт разный плод?`;
3. `Две борьбы: борьба возрождённого и борьба без новой жизни`;
4. `Сердце и Слово: почему одного слышания недостаточно`;
5. `Фарисей и ученик: как можно знать текст и не покоряться ему`;
6. `Созерцая славу Христа: как меняются желания`;
7. `Христос Откровения: не уменьшенный Иисус, а Царь и Судья`.

These must be **new Telegram-native bodies**, not copied article paragraphs. Each body needs local claim/evidence binding, fact-check and rights review before immutable release review.

### 4. Deep Bible-study adaptations — valuable, but currently HOLD

Recent Research work on 1 Corinthians 11 is especially suitable for future variety because it combines Greek, archaeology/social history, Roman ritual background and modern scholarship. Current authority explicitly says `RESEARCH-ONLY / PUBLICATION-HOLD`, so none of it is live eligible yet.

Future post candidates after that hold is removed:

- `Покрывало или только волосы? Что действительно спорно в 1 Кор 11`;
- `Почему объяснение про храмовых проституток слишком простое`;
- `capite velato: что римский ритуал объясняет — и чего не объясняет`;
- `Что означает «власть» на голове женщины в 1 Кор 11:10?`;
- `Ангелы в 1 Кор 11:10: где заканчивается текст и начинается реконструкция`.

The point is not to turn a developing scholarly corpus into Telegram prematurely. The point is to reserve a high-value lane for it once publication authority catches up.

### 5. Genesis / Enoch hard texts — HOLD

The Research backend already has site-ready work around Jude, 2 Peter, 1 Peter, 1 Enoch and manuscript evidence. Current authority still imposes publication/rights boundaries for this corpus. Candidate role after clearance: manuscript-aware difficult-text explainers.

### 6. Pulpit and church history — HOLD / active research

Two large families can later break up the feed further:

- `Обратная сторона кафедры` — bounded pastoral lessons and faithful responses, only where current authority permits publication and avoids unresolved allegations;
- `Баптисты России` — archive-backed biographies, events, documents and history after archive/rights gates are closed.

### 7. Biblical Atlas — active research

This is the visual/context lane: geography, archaeology, route questions and historical context. It is intentionally not live-ready while primary-source strengthening and image-rights work continue.

## Desired reader-facing rhythm

The goal is **not** a random shuffle. A useful mature cadence is closer to:

`quote → research/history → quote → biblical/theological explainer → quote → research/history → quote → deep study/context`

When a desired lane is not eligible, the planner may fall back to another eligible lane, but it must never treat a HOLD as permission to publish. Once at least two lanes are eligible, avoid adjacent use of the same lane when an alternative exists.

Inside the quote lane, the existing author round-robin still applies. Across the whole portfolio, the ideal variation therefore becomes two-dimensional:

- author diversity;
- content-kind diversity.

## Practical rollout order

1. **Now:** keep the repaired quote author rotation. The next material should not return immediately to Bunyan.
2. **Next:** complete one exact research-v2 provider canary under its own authority. If verified, activate the remaining research-v2 items into the mixed lane scheduler.
3. **Then:** adapt the first 4–7 «Серия Сердце» topics into new Telegram-native evidence-backed posts and review them as a separate immutable release.
4. **After that:** admit deep-study, church-history and atlas families only as their own current publication authorities allow them.

## Example mature 14-slot editorial pattern

This is a **pattern**, not a provider schedule and not a promise of dates:

1. Spurgeon / quote
2. research-v2 / historical comparison
3. Calvin / quote
4. Heart / born again explainer
5. Owen / quote
6. research-v2 / archival history
7. Watson or Edwards / quote
8. Heart / four soils explainer
9. Gill or another eligible quote author / quote
10. research-v2 / generations and influence
11. another rotated quote author / quote
12. Heart / heart and the Word
13. rotated quote / quote
14. deep-study/context lane, **only if its publication hold has been explicitly removed**

Until research-v2 is independently activated, positions belonging to non-live lanes do not cause provider publication. The current live quote workflow remains authoritative.

## Invariant

A richer feed is not permission to lower evidence standards. The portfolio exists so that future automation can ask two separate questions:

1. **Would this improve editorial variety?**
2. **Is this exact lane independently authorized and evidence-ready for publication?**

The second question always wins.
