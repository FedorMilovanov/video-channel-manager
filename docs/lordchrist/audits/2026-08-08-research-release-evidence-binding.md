# 2026-08-08 research release evidence-binding audit

## Finding

The research evidence queue itself was strongly bound: body digests, claim metadata, source IDs, source-registry digest, and queue digest were validated before a generic release was built.

However, the generic release adapter previously copied only `post.payload_sha256` into `GenericReleaseItem.source_sha256`. An already-built release therefore proved the post/claim payload but did not independently identify the exact source-registry and research-queue versions used during fact-checking.

This was a provenance gap, not a provider-write bypass. The research profile remained write-disabled and no research release had been activated.

## Fix

Every research release item now binds an evidence capsule with:

- `research_queue_sha256`;
- `source_registry_sha256`;
- `post_payload_sha256`.

The resulting SHA-256 becomes the generic release item's `source_sha256`.

Any change to verification metadata, source registry, claims, body, or post payload therefore changes the generic candidate digest and forces a new exact review.

## Exact new candidate

For the unchanged target and publication windows 2026-08-10/12/14/16/18 19:17 Europe/Moscow, specialized read-only CI reproduced:

`sha256:dbd4bc71e7a2a4e1320beb51843f0553f853dab34f2bd04d1800b787c2433653`

The former candidate `sha256:0f25f23fc87665b03df0b8486d6f336e8e405b6213457772ead6ce2a363cd07d` is intentionally obsolete and must never be approved.

## Invariant

A reviewed research release must prove both things independently:

1. the exact Telegram provider payload that will be sent;
2. the exact evidence contract that justified that payload.

Provider-write authorization remains a separate execution gate.
