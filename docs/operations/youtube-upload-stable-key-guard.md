# YouTube upload stable-key guard

Status: repository/local safety model only. **YouTube provider upload execution is not present in this baseline.**

This document supersedes the unsafe execution design in draft PR #171 without merging its provider transport or stale Black Man upload spec.

## Why the old attempt was unsafe

The draft uploader keyed its durable journal by `intent_sha256`, while the intent digest included `created_at` and mutable metadata. Replanning the same exact MP4 could therefore create a different intent digest and a different journal path. A previous `may_exist` or `verified` attempt could be bypassed by generating a fresh plan.

The draft also carried `provider_write_authorized=false` as data but did not use that field as a hard execution boundary before the OAuth/upload path. That implementation is intentionally retired rather than patched in place.

## Stable identity

The local v2 model defines one upload identity as:

```text
upload_key_sha256 = SHA-256(canonical JSON {
  project_key,
  target_channel_id,
  media_sha256
})
```

The key intentionally excludes `created_at`, title, description, tags and other attempt metadata. A timestamped intent remains child provenance; it does not create a new provider identity for the same bytes and target.

Every v2 intent must also prove the repository's canonical YouTube triple:

```text
project_key + OAuth account alias + exact channel_id
```

The current v2 model accepts private-first planning only and always records:

```text
provider_write_authorized = false
provider_effect = not_dispatched
```

`validate_intent()` rejects any v2 intent whose authorization field is changed, even if its digest is recomputed.

## Durable journal semantics

The stable journal path is derived from `upload_key_sha256`, never `intent_sha256`.

- no journal: a local plan may be created;
- `planned / not_dispatched`: another plan for the same stable identity is blocked;
- `may_exist`: another plan is blocked;
- `verified`: another plan is blocked;
- `abandoned / confirmed_absent`: a new local plan may be created for the same bytes/target.

A planned journal may be marked abandoned only while its provider effect is still `not_dispatched` and its active intent digest exactly matches. This is the safe way to release a local plan for metadata revision without deleting durable state.

Old v1 intents/journals fail closed; they are not silently upgraded.

## Black Man status

The old PR #171 upload spec is deliberately not copied into current `main`. It contains metadata/timestamps from before the quality-master provenance work and must not be treated as a current final provider payload.

Historical evidence from that draft records the exact media SHA-256 `sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0`, target channel `UC-78ys2S3cQ3lpqgXfo-SvQ`, and an already-existing private target referenced by the later metadata audit. That history is a reason to reconcile existing remote state before any future upload, not a reason to start another upload.

## Future execution boundary

A future provider uploader, if explicitly authorized later, must be designed as a separate reviewed change on top of this stable-key model. Before any `videos.insert` it must at minimum:

1. load and validate the v2 intent;
2. prove canonical project/account/channel identity before credentials;
3. acquire the stable-key write lock;
4. re-read the stable journal under the lock;
5. refuse `may_exist`, `verified`, unknown or stale journal states;
6. persist dispatch intent under the stable key before provider mutation;
7. never create a second `videos.insert` to resolve an ambiguous first attempt;
8. reconcile/read back the exact provider result before marking `verified`.

None of those provider actions are implemented or authorized by the current guard.
