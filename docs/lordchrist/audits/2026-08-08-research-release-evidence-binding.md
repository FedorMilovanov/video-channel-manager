# 2026-08-08 research release evidence-binding audit

## Finding

The research evidence queue itself was strongly bound: body digests, claim metadata, source IDs, source-registry digest, and queue digest were validated before a generic release was built.

However, the generic release adapter previously copied only `post.payload_sha256` into `GenericReleaseItem.source_sha256`. An already-built release therefore proved the post/claim payload but did not independently identify the exact source-registry and research-queue versions used during fact-checking.

This was a provenance gap, not a provider-write bypass. The research profile remained write-disabled and no research release had been activated.

A second fact-check pass also found one evidence-mapping defect: the `3,600+` MacArthur archive claim was true, but its manifest pointed to a GTY history page plus a MacArthur Center page that currently says `3,500`. The claim is now bound to the exact current Grace to You archive source that states `more than 3,600 sermons`.

## Fix

Every research release item now binds an evidence capsule with:

- `research_queue_sha256`;
- `source_registry_sha256`;
- `post_payload_sha256`.

The resulting SHA-256 becomes the generic release item's `source_sha256`.

Any change to verification metadata, source registry, claims, body, or post payload therefore changes the generic candidate digest and forces a new exact review.

Current audited evidence identity:

- source registry: `sha256:23f4521f1406dfcd775533bc435a8ba913d7e41405c8df8bbe23ea7d431f3ec8`;
- research queue: `sha256:1b934d6acd95c42457dd3bee60fb6958291722e491979cd682324af3d4bd1271`;
- target-bound candidate: `sha256:b87b69332a05fbf968e1d04b4f24543d89e7619113a8d076e8f81d20d7f69515`.

The former candidates `sha256:0f25f23fc87665b03df0b8486d6f336e8e405b6213457772ead6ce2a363cd07d` and `sha256:dbd4bc71e7a2a4e1320beb51843f0553f853dab34f2bd04d1800b787c2433653` are intentionally obsolete and must never be approved.

## Invariant

A reviewed research release must prove both things independently:

1. the exact Telegram provider payload that will be sent;
2. the exact evidence contract that justified that payload.

Provider-write authorization remains a separate execution gate.
