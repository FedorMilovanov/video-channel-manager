# Lordchrist research-post v2 contract

Research-post v2 remains deliberately separate from the production quote queue at the **editorial/evidence layer**. Provider delivery, however, must reuse the repository's generic multichannel Telegram release/state/transport layer rather than create a third state machine.

## Why it exists

The existing `telegram-quote-queue` is intentionally narrow: public-domain primary-source quotations with a source proof per post. Historical comparison and analysis need a richer evidence model. Weakening the quote contract to accommodate them would reduce safety for the working production path.

`telegram_research.py` therefore defines the research evidence contract. It remains provider-inert: no Telegram token handling, no `sendMessage`, no state-branch writer.

## Evidence model

Every public post is original Russian editorial copy. Every factual statement that matters to the argument is represented as a claim with:

- stable `claim_id`;
- claim kind (`numeric`, `historical`, `influence`, `method`, `interpretation`);
- certainty (`exact`, `estimate`, `lower_bound`, `archive_count`, `interpretation`);
- one or more evidence source IDs;
- explicit measurement scope for every numeric claim.

The machine-bound source registry contains primary/direct testimony, institutional archive material, and scholarly cross-checks. The wider editorial research record preserves the 76-page verification pass; the machine manifest binds the 28 sources actually supporting current public claims.

## Immutable bindings

- every public `.txt` body has a SHA-256 digest;
- the source registry has its own canonical SHA-256 digest;
- every post payload digest binds publication identity, title, body digest, release offset, and claims;
- the research queue digest binds verification metadata, schedule state, source registry, and all five post payloads.

Current staged research digest: `sha256:7478aa03b3862f80d8f92702b3a968255c81f9edadcdfbe399370efc53d773df`.

## Locked measurement boundaries

The validator fails closed if:

- Calvin `4–5 thousand` stops being an **estimate of sermons preached**;
- Spurgeon `3,563` stops being the **exact published-corpus count** and is misrepresented as all sermons preached;
- MacArthur `3,600+` stops being a **lower-bound recorded-archive count** and is misrepresented as an exact lifetime total.

## Relative editorial schedule

The staged evidence queue preserves:

- post 1 — `T+0`;
- post 2 — `T+2`;
- post 3 — `T+4`;
- post 4 — `T+6`;
- post 5 — `T+8`.

This relative schedule is an editorial contract, not yet a provider schedule. The generic `telegram-release-queue` uses absolute timezone-aware `scheduled_at` values, so a reviewed release adapter must resolve the relative offsets only after a real publication window is selected.

## Production proof is complete

The previous freeze condition is satisfied. On 2026-08-08 the existing Lordchrist quote publisher produced the first verified autonomous scheduled post:

- publication: `lordchrist-bunyan-fire-grace`;
- workflow run: `31245659459/1`;
- Telegram `message_id=1472`;
- result: `published / verified`.

The immutable proof is `docs/lordchrist/proofs/2026-08-08-first-scheduled-proof.md`.

## Generic provider boundary

Current `main` contains a stronger generic multichannel Telegram runtime:

- `telegram_channel_profile.py` — channel identity and policy;
- `telegram_target_binding.py` — read-only discovered exact bot/chat binding;
- `telegram_multichannel_release.py` — reviewed immutable release and exact scheduled items;
- `telegram_multichannel_state.py` / CLI — durable strict-order ledger and intent;
- `telegram_multichannel_transport.py` — provider call, zero mutation retries, exact receipt/entity/link verification.

Research-v2 must feed this runtime. It must **not** reimplement intent persistence, provider mutation, retry semantics, or reconciliation.

## Remaining activation sequence

1. Port the research evidence contract onto current `main` and keep it read-only.
2. Obtain a fresh provider-free generic Lordchrist target binding (`getMe + getChat + getChatAdministrators`).
3. Convert the five validated research posts into a generic immutable release candidate with absolute Moscow-time windows.
4. Review/authorize the exact candidate and initialize its isolated durable ledger.
5. Run one exact manual research canary inside the first immutable publication window.
6. Require a verified Telegram receipt and durable outcome; no blind retry on `may_exist`.
7. Let the generic scheduler publish the strict-next remaining items only when their windows become eligible.

## CI boundary

`.github/workflows/lordchrist-research-v2-validate.yml` remains read-only:

- `permissions: contents: read`;
- no Telegram secret;
- no provider mutation command;
- validator compilation;
- manifest/source/body integrity checks;
- regression tests;
- explicit proof that the research evidence queue remains `staged` and `live_eligible=false`.

Provider activation belongs in a separate reviewed release/canary change after exact target binding. This keeps content research and provider authority independently auditable.
