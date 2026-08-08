# 2026-08-08 research release evidence-binding audit

## Finding

The research evidence queue itself was strongly bound: body digests, claim metadata, source IDs, source-registry digest, and queue digest were validated before a generic release was built.

However, the generic release adapter previously copied only `post.payload_sha256` into `GenericReleaseItem.source_sha256`. An already-built release therefore proved the post/claim payload but did not independently identify the exact source-registry and research-queue versions used during fact-checking.

This was a provenance gap, not a provider-write bypass. The research profile remained write-disabled and no research release had been activated.

The live source sweep also found two evidence-mapping defects before activation:

1. the true `3,600+` MacArthur archive claim pointed to a GTY history page plus a MacArthur Center page that currently says `3,500`, rather than the exact current Grace to You archive source stating `more than 3,600 sermons`;
2. the 2011 completion claim attributed a `42 years` description to sources that did not make that exact statement. It is now expressed from the exact dated first sermon (9 February 1969), exact dated final Mark sermon (5 June 2011), and Grace Community Church's official June 2011 New Testament completion record.

The public Telegram copy did not need to change; the evidence claims and source mappings were corrected.

## Fix

Every research release item now binds an evidence capsule with:

- `research_queue_sha256`;
- `source_registry_sha256`;
- `post_payload_sha256`.

The resulting SHA-256 becomes the generic release item's `source_sha256`.

Any change to verification metadata, source registry, source mapping, claims, body, or post payload therefore changes the generic candidate digest and forces a new exact review.

The validator also requires the research fact-check date to cover the bound registry check date and locks the `3,600+` claim to its exact checked GTY source.

## Final audited evidence identity

- source count: `30`;
- source registry: `sha256:5873c269cb749d972e8edca981336ac058f228298f9332f8c33f410c0d960665`;
- research queue: `sha256:9ee025da63f13e2363bb4bb3f9e0af430b46399c69eeca068da10f9cd24e1fa1`;
- target-bound candidate: `sha256:779fd3bd41633b2f9ffe0052723d50fdb0593b27dff71bbed56ca7119c6acc13`.

Former candidates `0f25…`, `dbd4…`, and `b87b…` are intentionally obsolete and must never be approved.

## Invariant

A reviewed research release must prove both things independently:

1. the exact Telegram provider payload that will be sent;
2. the exact evidence contract that justified that payload.

Provider-write authorization remains a separate execution gate.
