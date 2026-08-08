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

## Target identity is already production-proven

The same scheduled run performed the full legacy read-only target preflight before the provider mutation: `getMe`, `getChat` by numeric id, `getChat` by public username, and `getChatAdministrators`. The durable dispatch envelope preserves the resulting exact `TargetProof`.

Research-v2 accepts that verified legacy dispatch as target-binding evidence instead of requiring a redundant second network discovery. The canonical binding is:

- path: `content/telegram/channels/lordchrist-target-binding.json`;
- profile digest: `sha256:0de6ac7a664b4a7bfad6815f543357a2c78809b776f1c6a054cf2aaf9ef01ba6`;
- binding digest: `sha256:4d4bd46405080512aaf31b4ee4bbeeca22eb1703642b585efc656b8f95e15bcd`;
- chat id: `-1001295216957`;
- bot id: `8716602202`;
- bot username: `preaching_mp3_bot`;
- evidence time: `2026-08-08T07:13:09.125496Z`;
- `provider_write_performed=false` for the target-proof operation.

The manual generic discovery workflow remains available as a future revalidation/rotation tool; it is no longer a prerequisite for this already-proven target.

The channel-profile identity digest deliberately excludes `provider_writes_authorized`. Therefore switching the execution gate later does not silently invalidate a previously verified channel/bot identity; the provider mutation path still checks the write gate independently at execution time.

## Generic provider boundary

Current `main` contains a stronger generic multichannel Telegram runtime:

- `telegram_channel_profile.py` — channel identity and policy;
- `telegram_target_binding.py` — exact bot/chat binding from read-only evidence;
- `telegram_multichannel_release.py` — reviewed immutable release and exact scheduled items;
- `telegram_multichannel_state.py` / CLI — durable strict-order ledger and intent;
- `telegram_multichannel_transport.py` — provider call, zero mutation retries, exact receipt/entity/link verification.

Research-v2 must feed this runtime. It must **not** reimplement intent persistence, provider mutation, retry semantics, or reconciliation.

## Remaining activation sequence

1. Merge the provider-inert research evidence/release adapter and production-proven target binding.
2. Convert the five validated research posts into a generic immutable release candidate with absolute Moscow-time windows.
3. Review/authorize the exact candidate and initialize its isolated durable ledger.
4. Run one exact research canary inside the first immutable publication window.
5. Require a verified Telegram receipt and durable outcome; no blind retry on `may_exist`.
6. Let the generic scheduler publish the strict-next remaining items only when their windows become eligible.

## CI boundary

`.github/workflows/lordchrist-research-v2-validate.yml` remains read-only:

- `permissions: contents: read`;
- no Telegram secret;
- no provider mutation command;
- validator/tooling compilation;
- manifest/source/body/profile/binding integrity checks;
- regression tests;
- explicit proof that the research evidence queue remains `staged` and `live_eligible=false`.

Provider activation belongs in a separate reviewed release/canary change. This keeps content research and provider authority independently auditable.
