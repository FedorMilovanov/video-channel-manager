# LordChrist historical editorial workflow

This directory is the canonical, provider-inert production system for evidence-backed historical Telegram posts for `@lordchrist`.

The goal is repeatability: a new three-week cycle should be created by adding research data and post records, not by inventing another publishing path.

## Safety invariants

- Historical cycles are **provider inert** while they live here.
- `provider_writes_authorized` is always `false` in editorial data.
- `live_eligible` is always `false` during preflight.
- Schedule backfill is `none`; a missed historical slot is not silently replayed.
- Images are not transport-ready merely because a source page exists. A production-ready image additionally requires a reviewed direct media URL, expected MIME type and SHA-256 of the exact bytes.
- Historical description, participant position and editorial theological evaluation remain separate fields.
- A direct quotation requires an exact locator and grade-A primary/critical/archive evidence.
- A material non-editorial historical claim requires at least two independent evidence groups and at least one grade-A source.

## Canonical layout

```text
historical-editorial/
├── README.md
└── v1/
    ├── theology-profile.json
    ├── source-catalog.json
    ├── sources/
    │   └── <topic-shard>.json
    └── cycles/
        └── <cycle>/
            ├── manifest.json
            └── posts/
                ├── 01-....json
                └── 09-....json
```

### Theology profile

`theology-profile.json` is bound to an exact commit of `FedorMilovanov/gb-is-my-strength/about/index.html`.

Do not silently rewrite the profile when the source repository changes. Review the new source commit, update the profile deliberately, then reseal any future cycle that should use it. Existing sealed cycles remain reproducible against their original digest.

### Source catalog

The source catalog is sharded by topic. A shard is intentionally small enough for human review and may be reused by many cycles.

Accepted production grades are only:

- `A` — primary document, critical edition, official/university archive, or an institutional collection that actually exposes primary evidence;
- `B+` — peer-reviewed scholarship, academic monograph, serious institutional collection or archive guide.

Search results, unsourced biographies, SEO pages and social posts may be useful during discovery, but they do **not** become production sources merely because they were reviewed.

For the first cycle:

- `reviewed_urls = 69` records the research pass;
- the sealed catalog contains `52` accepted A/B+ sources.

Those numbers must remain separate. Reviewed URLs measure research breadth; catalog size measures evidence that survived editorial acceptance.

### Source binding identity

A queue or scaffold records both the artifact that is physically bound and the semantic registry produced from it:

- `source_binding_kind` is `registry` for a direct registry JSON or `catalog` for a sharded catalog manifest;
- `source_binding_path` points to that exact bound artifact;
- `source_binding_sha256` seals the canonical persisted JSON at that path;
- `source_registry_sha256` seals the materialized `HistoricalSourceRegistry` used for claim validation.

These two digests are independent by contract for **both** binding kinds. With the current direct-registry schema they normally have the same value, because the persisted registry has no hydration-only defaults. Code must not depend on that equality: a future schema default may legitimately change the semantic model digest without changing the sealed persisted artifact. The loader therefore verifies the artifact hash first and the materialized registry hash separately.

For a `catalog` binding the distinction is visible already: the catalog digest identifies the manifest and shard graph, while the registry digest identifies the fully materialized evidence set.

Do not point a `source_binding_path` at a catalog and label it as a registry. Direct-registry preflight accepts only `source_binding_kind=registry`; catalog-bound cycles must go through `telegram_historical_bundle` so shard seals and the catalog seal are verified before the registry is materialized.

### Independence groups

`independence_group` is an evidence-control field, not a domain-name counter.

Two pages from the same archive, author, institutional project, sermon corpus or derivative dataset can belong to the same independence group. A claim only satisfies the two-group gate when the evidence is genuinely independent enough to cross-check the claim.

## Creating the next cycle

Start from a sealed prior manifest so the next scaffold inherits the reviewed catalog and theology bindings:

```bash
python -m video_channel_manager.telegram_historical_bundle scaffold-next \
  content/telegram/lordchrist/historical-editorial/v1/cycles/2026-09-cycle-01/manifest.json \
  --cycle-id history-cycle-2026-10-01 \
  --start-on 2026-10-01 \
  --output content/telegram/lordchrist/historical-editorial/v1/cycles/2026-10-cycle-01/scaffold.json
```

The scaffold computes the next Monday/Wednesday/Saturday dates in `Europe/Moscow`, starting at or after `--start-on`. It does not backfill missed dates and cannot authorize provider writes.

Then:

1. Research candidate topics broadly.
2. Add genuinely reusable evidence to an existing topic shard or a new shard.
3. Recompute/seal the affected shard and `source-catalog.json` before binding a new cycle.
4. Create one post record per slot. Keep claims atomic enough that their evidence can be reviewed independently.
5. For controversies, bind participant evidence separately from synthesis. If opposing primary evidence is unavailable, record the limitation instead of pretending balance was achieved.
6. For martyrdom material, record testimony proximity (`contemporary`, `near_contemporary`, or `later_tradition`) rather than flattening all accounts into equal certainty.
7. Keep theological evaluation in `theology_review.editorial_evaluation`, with Scripture references, instead of presenting it as a statement from the historical source.
8. Add image plans only after provenance and rights review. Leave `production_ready=false` until exact bytes are pinned.
9. Seal the cycle manifest with the catalog, theology and post digests.
10. Run preflight and tests before any canary discussion.

## Preflight

```bash
python -m video_channel_manager.telegram_historical_bundle preflight \
  content/telegram/lordchrist/historical-editorial/v1/cycles/2026-09-cycle-01/manifest.json
```

A successful report is machine-readable JSON and includes source counts, evidence-group counts, claim counts, controversy/martyrdom counts, image readiness, queue digest and the explicit provider-inert state.

Preflight success means **the editorial bundle is internally consistent**. It does not mean Telegram publishing is authorized.

## Rich-document contract

The same sealed posts are materialized into the existing `HistoricalEditorialQueueV1` and then passed to `build_historical_rich_document()`.

This is deliberate: there is no second bespoke renderer for historical posts. The historical workflow produces the same `RichArticleDocument` abstraction used by the Telegram rich stack.

Repository tests require every sealed post to build successfully as a real rich document.

## Image activation

Historical images have two different readiness states:

1. **Editorial provenance ready** — source page, depicted subject, intended use, rights basis and attribution have been reviewed.
2. **Transport ready** — direct media URL, expected MIME and SHA-256 for the exact bytes are also pinned.

Only the second state may set `production_ready=true`.

Never fetch an arbitrary current image from a source page at send time. The bytes used by a canary must be the bytes that were reviewed.

## Canary and activation

The editorial repository does not perform live provider activation.

After merge and green CI, a separate operator-controlled step may prepare one verified rich canary. That step must still verify:

- exact merged commit;
- exact manifest/queue digest;
- exact media bytes if images are enabled;
- correct destination channel;
- no duplicate publication id;
- current Telegram/provider transport gates.

Only after the canary is explicitly reviewed should any future scheduler integration be considered.

## Review checklist

Before opening a PR for a cycle:

- [ ] exactly nine posts for the three-week v1 cycle;
- [ ] release offsets are `0, 2, 5, 7, 9, 12, 14, 16, 19`;
- [ ] all publication IDs and claim IDs are unique;
- [ ] every material historical claim has two independent evidence groups;
- [ ] every material historical claim has at least one grade-A source;
- [ ] all direct quotes, if any, have exact locators;
- [ ] controversy sides are represented honestly and limitations are explicit;
- [ ] martyrdom testimony proximity is explicit;
- [ ] theological description and editorial evaluation are separate;
- [ ] source binding kind/path/artifact digest and semantic registry digest are consistent;
- [ ] image rights/provenance are reviewed;
- [ ] no image falsely claims transport readiness;
- [ ] `provider_writes_authorized=false`;
- [ ] `backfill_policy=none`;
- [ ] bundle preflight passes;
- [ ] end-to-end rich-document tests pass;
- [ ] PR head is based on current `main` before merge.
