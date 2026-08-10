# Lordchrist legacy quote editorial rotation

Owner: Issue #238  
Project: `lord-god-strength`  
Telegram target: `@lordchrist`

## Why this policy exists

The reviewed 30-post source queue is intentionally immutable evidence, but its source array is grouped by author. That ordering is useful for source review and provenance and is not suitable as a reader-facing publication sequence.

The original live selector treated source order as publication order. As a result, Telegram messages `1470`, `1472`, `1473`, and `1474` were four consecutive John Bunyan / «Путешествие Пилигрима» publications even though the same reviewed queue already contained Spurgeon, Calvin, Owen, Watson, Edwards, and Gill.

## Immutable source versus editorial publication order

`content/telegram/lordchrist/verified-30-posts.json` remains the canonical reviewed source queue. Its exact text, source proofs, per-post payload SHA-256 values, sequence fields, and queue digest are not rewritten by this policy.

The publication selector may choose a different pending item for editorial diversity. Dispatch envelopes still carry the original immutable `sequence`, payload SHA-256, queue digest, and exact source text. Provider verification and durable ledger identity therefore remain bound to the reviewed source material.

## Rotation rule

The selector preserves legacy strict source order until durable publication history proves that the live feed has already produced two consecutive verified publications by the same author. Once such a repetition exists, editorial rotation remains active for the rest of that ledger.

Active rotation builds a deterministic author round-robin from the immutable queue:

1. authors are ordered by their first appearance in the source queue;
2. posts within each author preserve their original source sequence;
3. one post per author is taken per round while that author has remaining material;
4. already `published` or `skipped` items are ignored at selection time;
5. any unresolved/non-terminal provider state blocks the whole rotated selection rather than being bypassed.

With the durable history recorded at the start of Issue #238, the first future pending selection becomes:

```text
lordchrist-spurgeon-putting-away-sin
```

The next reviewed authors then rotate through Calvin, Owen, Watson, Edwards, Gill, and subsequent rounds instead of exhausting the remaining Bunyan block first.

## Safety invariants

- no Telegram provider write is part of implementing this policy;
- published messages and their message IDs are historical evidence and are never rewritten;
- the production ledger is not replaced or reinitialized;
- queue digest and source payload identities remain unchanged;
- unresolved `dispatching` / `unknown` / other non-terminal states fail closed;
- target preflight, daily quota, verified manual canary, current-main CI gate, durable intent-before-send, rendered-payload verification, archived provider outcome, and zero blind mutation retry remain unchanged;
- research-v2 is not activated or mixed into this legacy campaign by this policy.

## Regression expectation

A ledger representing the four verified Bunyan publications through Telegram message `1474` must preview Spurgeon next. After that Spurgeon entry is marked verified, the next preview must be Calvin; after Calvin, Owen. A pending rotated candidate must never allow an unresolved provider effect elsewhere in the campaign to be bypassed.
