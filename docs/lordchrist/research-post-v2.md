# Lordchrist research-post v2 contract

This path is deliberately separate from the production quote queue.

## Why it exists

The existing `telegram-quote-queue` is intentionally narrow: thirty public-domain primary-source quotations with one source proof per post. Historical comparison and analysis need a different evidence model. Weakening the quote contract to accommodate them would reduce safety for the working production path.

`telegram_research.py` therefore defines a parallel, read-only research queue contract. It has no provider mutation command and no Telegram token handling.

## Evidence model

Every public post is original Russian editorial copy. Every factual statement that matters to the argument is represented as a claim with:

- a stable `claim_id`;
- a claim kind (`numeric`, `historical`, `influence`, `method`, `interpretation`);
- a certainty label (`exact`, `estimate`, `lower_bound`, `archive_count`, `interpretation`);
- one or more evidence source IDs;
- a measurement scope for every numeric claim.

The machine-bound source registry contains primary/direct testimony, institutional archive material, and scholarly cross-checks. The wider editorial research file records the full 76-page verification pass; the v2 queue binds the sources actually needed to support its public claims.

## Immutable bindings

Research copy and evidence are separate files, but the manifest binds both cryptographically:

- every public `.txt` body has a recorded SHA-256 digest;
- the source registry has its own canonical SHA-256 digest;
- every post payload digest binds publication identity, title, body digest, release offset and claim records;
- the queue digest binds verification metadata, staged schedule, source-registry digest and all five post payload digests.

Changing a post or evidence registry without explicitly updating the corresponding digest therefore fails validation.

Current staged queue digest: `sha256:7478aa03b3862f80d8f92702b3a968255c81f9edadcdfbe399370efc53d773df`.

## Locked measurement boundaries

The validator fails closed if the series changes these three headline measurements into misleading equivalents:

- Calvin `4–5 thousand` remains an **estimate of sermons preached**.
- Spurgeon `3,563` remains the **exact published corpus count**, not all sermons preached.
- MacArthur `3,600+` remains a **lower-bound count of recorded sermons in the current Grace to You archive**, not a lifetime total.

## Delayed-release model

The five posts are loaded with relative release offsets:

- post 1: `T+0`;
- post 2: `T+2 days`;
- post 3: `T+4 days`;
- post 4: `T+6 days`;
- post 5: `T+8 days`.

`T` is intentionally undefined while the queue is staged. Exact calendar dates must not be baked in before the first existing scheduled-production proof and a separate research-post canary.

The checked-in queue has `schedule.state = staged`. A staged queue is never live-eligible and may not contain activation or canary evidence. An armed queue must contain all three: a timezone-aware activation timestamp, the exact research canary publication ID, and a positive verified Telegram message ID.

## CI boundary

`.github/workflows/lordchrist-research-v2-validate.yml` is read-only:

- `permissions: contents: read`;
- no Telegram secret is referenced;
- no provider mutation command exists in the research CLI;
- it compiles the validator, validates the manifest, runs fail-closed regression tests and proves the PR queue remains `staged` and `live_eligible=false`.

The regression suite includes explicit failures for changing the Calvin estimate to exact, dropping the published-corpus scope from Spurgeon's 3,563, turning MacArthur's 3,600+ into an exact lifetime total, inventing an unknown source, altering the source-registry digest, or claiming canary evidence while staged.

## Activation sequence

1. Observe and record the first clean scheduled publication from the existing quote pipeline.
2. Merge post-proof hardening chosen in issue #168 without weakening the durable intent model.
3. Validate and preview this research queue with the read-only research-v2 CI.
4. Publish exactly one independently authorized research canary.
5. Record the canary's verified Telegram message ID and exact publication ID.
6. Arm the research schedule in a reviewed change.
7. Only then connect a research dispatch adapter to the existing durable state/transport safety model.

No step in the current research-v2 PR sends a Telegram message.
