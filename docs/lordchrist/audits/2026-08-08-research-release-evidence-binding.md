# 2026-08-08 research release evidence-binding audit

## Finding

The research evidence queue itself was strongly bound: body digests, claim metadata, source IDs, source-registry digest, and queue digest were validated before a generic release was built.

However, the generic release adapter previously copied only `post.payload_sha256` into `GenericReleaseItem.source_sha256`. An already-built release therefore proved the post/claim payload but did not independently identify the exact source-registry and research-evidence versions used during fact-checking.

This was a provenance gap, not a provider-write bypass. The research profile remained write-disabled and no research release had been activated.

The live source sweep also found two evidence-mapping defects before activation:

1. the true `3,600+` MacArthur archive claim pointed to a GTY history page plus a MacArthur Center page that currently says `3,500`, rather than the exact current Grace to You archive source stating `more than 3,600 sermons`;
2. the 2011 completion claim attributed a `42 years` description to sources that did not make that exact statement. It is now expressed from the exact dated first sermon (9 February 1969), exact dated final Mark sermon (5 June 2011), and Grace Community Church's official June 2011 New Testament completion record.

A further architecture pass caught a coupling bug before merge: the first evidence capsule used the complete research queue digest, which also includes mutable `staged → armed` canary state. A successful canary would therefore have changed the evidence identity despite no factual change.

## Fix

`ResearchQueueV2` now exposes two identities:

- `digest` — complete queue identity including activation/canary state;
- `evidence_digest` — immutable editorial/fact-check identity excluding activation state.

Every research release item binds an evidence capsule with:

- `research_evidence_sha256`;
- `source_registry_sha256`;
- `post_payload_sha256`.

Changing verification metadata, source registry, source mapping, claims, body, or post payload changes the generic candidate and forces a new review. Changing only verified activation metadata changes the complete queue digest but leaves evidence identity stable.

The validator also requires the research fact-check date to cover the bound registry check date and locks the `3,600+` claim to its exact checked GTY source.

## Final audited evidence identity

- source count: `30`;
- source registry: `sha256:5873c269cb749d972e8edca981336ac058f228298f9332f8c33f410c0d960665`;
- complete staged queue: `sha256:201ba2a2ba8337c4b408e9ece645f16707ceafaba9eeebbc2ae6ce17a632a212`;
- immutable evidence contract: `sha256:16ec016426c908df26af944774b35f54d806952dff77676e159ee6588457392e`;
- exact target-bound candidate: `sha256:2eb3825390b8f4e70b847d9d1b328ea4e203bce0f1c88e036ea97ae667809cd0`.

All earlier candidate identities are intentionally obsolete and must never be approved.

## Invariant

A reviewed research release must prove both things independently:

1. the exact Telegram provider payload that will be sent;
2. the exact immutable evidence contract that justified that payload.

Operational canary/arming state must not rewrite factual evidence identity. Provider-write authorization remains a separate execution gate.
