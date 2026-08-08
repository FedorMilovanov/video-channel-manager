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

The machine-bound source registry contains primary/direct testimony, institutional archive material, and scholarly cross-checks. The wider editorial research record preserves the 76-page verification pass; the machine manifest currently binds 30 checked sources supporting the public claims.

## Immutable bindings

- every public `.txt` body has a SHA-256 digest;
- the source registry has its own canonical SHA-256 digest;
- every post payload digest binds publication identity, title, body digest, release offset, and claims;
- the complete research queue digest also binds mutable activation/canary state;
- a separate `evidence_digest` binds the immutable editorial/fact-check contract and deliberately excludes activation state;
- every generic release item binds `evidence_digest`, source-registry digest, and post payload digest in its `source_sha256` evidence capsule.

Current audited identities:

- source registry: `sha256:5873c269cb749d972e8edca981336ac058f228298f9332f8c33f410c0d960665`;
- complete staged queue: `sha256:201ba2a2ba8337c4b408e9ece645f16707ceafaba9eeebbc2ae6ce17a632a212`;
- immutable evidence contract: `sha256:16ec016426c908df26af944774b35f54d806952dff77676e159ee6588457392e`;
- exact target-bound candidate for the current five windows: `sha256:2eb3825390b8f4e70b847d9d1b328ea4e203bce0f1c88e036ea97ae667809cd0`.

Changing factual evidence invalidates the generic candidate even if public Telegram text did not change. Changing only verified `staged → armed` activation metadata changes the complete queue identity but must not rewrite the factual evidence identity of an already reviewed release.

## Locked measurement boundaries

The validator/tests fail closed if:

- Calvin `4–5 thousand` stops being an **estimate of sermons preached**;
- Spurgeon `3,563` stops being the **exact published-corpus count** and is misrepresented as all sermons preached;
- MacArthur `3,600+` stops being a **lower-bound recorded-archive count** and is misrepresented as an exact lifetime total;
- the MacArthur `3,600+` claim stops being tied to the exact checked Grace to You archive source;
- research verification predates the bound source-registry check;
- the 1969→2011 completion claim loses its exact first-sermon, final-sermon, and Grace Community Church completion evidence;
- activation metadata changes the immutable evidence digest.

## Relative editorial schedule

The staged evidence queue preserves:

- post 1 — `T+0`;
- post 2 — `T+2`;
- post 3 — `T+4`;
- post 4 — `T+6`;
- post 5 — `T+8`.

This relative schedule is an editorial contract, not yet a provider schedule. The generic `telegram-release-queue` uses absolute timezone-aware `scheduled_at` values, so a reviewed release adapter resolves the offsets only after a real publication window is selected.

## Production proof is complete

On 2026-08-08 the existing Lordchrist quote publisher produced the first verified autonomous scheduled post:

- publication: `lordchrist-bunyan-fire-grace`;
- workflow run: `31245659459/1`;
- Telegram `message_id=1472`;
- result: `published / verified`.

The immutable proof is `docs/lordchrist/proofs/2026-08-08-first-scheduled-proof.md`.

## Target identity is production-proven

The same scheduled run performed the full legacy read-only target preflight before provider mutation: `getMe`, `getChat` by numeric id, `getChat` by public username, and `getChatAdministrators`. The durable dispatch envelope preserves the resulting exact `TargetProof`.

The canonical binding is:

- path: `content/telegram/channels/lordchrist-target-binding.json`;
- profile digest: `sha256:0de6ac7a664b4a7bfad6815f543357a2c78809b776f1c6a054cf2aaf9ef01ba6`;
- binding digest: `sha256:4d4bd46405080512aaf31b4ee4bbeeca22eb1703642b585efc656b8f95e15bcd`;
- chat id: `-1001295216957`;
- bot id: `8716602202`;
- bot username: `preaching_mp3_bot`;
- evidence time: `2026-08-08T07:13:09.125496Z`;
- `provider_write_performed=false` for the target-proof operation.

The manual generic discovery workflow remains available for future revalidation/rotation. The channel-profile identity digest deliberately excludes `provider_writes_authorized`; execution authority remains a separate runtime gate.

## Generic provider boundary

Research-v2 feeds the generic multichannel runtime:

- `telegram_channel_profile.py` — channel identity and policy;
- `telegram_target_binding.py` — exact bot/chat binding;
- `telegram_multichannel_release.py` — reviewed immutable release and exact scheduled items;
- `telegram_multichannel_state.py` / CLI — durable strict-order ledger and intent;
- `telegram_multichannel_transport.py` — provider call, zero mutation retries, exact receipt/entity/link verification, with verified receipt time captured only after the checked provider response.

Research-v2 must not reimplement intent persistence, provider mutation, retry semantics, or reconciliation.

## Remaining activation sequence

1. Merge the final evidence-bound research adapter and fact-check corrections.
2. Review/authorize exactly `sha256:2eb3825390b8f4e70b847d9d1b328ea4e203bce0f1c88e036ea97ae667809cd0` only after exact-head CI.
3. Initialize its isolated durable ledger.
4. Run one exact research canary inside the first immutable publication window.
5. Require a verified Telegram receipt and durable outcome; no blind retry on `may_exist`.
6. Record canary evidence / arm operational state without changing `evidence_digest`.
7. Let the generic scheduler publish the strict-next remaining items only when their windows become eligible.

## CI boundary

`.github/workflows/lordchrist-research-v2-validate.yml` remains read-only:

- `permissions: contents: read`;
- no Telegram secret;
- no provider mutation command;
- validator/tooling compilation;
- manifest/source/body/profile/binding integrity checks;
- source-registry, queue, evidence, and candidate digest diagnostics;
- exact candidate digest reproduction;
- provider-inert review regression;
- explicit proof that the research evidence queue remains `staged` and `live_eligible=false`.

Provider activation belongs in a separate reviewed release/canary change. This keeps factual evidence, operational activation, and provider authority independently auditable.
