# YouTube upload stable-key guard

Status: repository/local safety model plus read-only existing-target adoption. **YouTube provider upload execution is not present in this baseline.**

This document supersedes the unsafe execution design in draft PR #171 without merging its provider transport or stale Black Man upload spec.

## Why the old attempt was unsafe

The draft uploader keyed its durable journal by `intent_sha256`, while the intent digest included `created_at` and mutable metadata. Replanning the same exact MP4 could therefore create a different intent digest and a different journal path. A previous `may_exist` or `verified` attempt could be bypassed by generating a fresh plan.

The draft also carried `provider_write_authorized=false` as data but did not use that field as a hard execution boundary before the OAuth/upload path. That implementation is intentionally retired rather than patched in place.

A later explicitly authorized historical execution of that draft exposed two additional verifier defects:

- YouTube returned the exact intended tags in another order, while the old verifier compared `snippet.tags` as an ordered list;
- `status.containsSyntheticMedia=true` was accepted by write requests but was omitted from the observed `videos.list` status payload even after a successful update, while YouTube Studio showed AI use `Yes`.

Those incidents are evidence only. They do not make PR #171 executable again.

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

- no journal: a local plan may be created only when no separately known remote target already occupies that stable identity;
- `planned / not_dispatched`: another plan for the same stable identity is blocked;
- `may_exist`: another plan is blocked;
- `verified`: another plan is blocked;
- `abandoned / confirmed_absent`: a new local plan may be created for the same bytes/target.

A planned journal may be marked abandoned only while its provider effect is still `not_dispatched` and its active intent digest exactly matches. This is the safe way to release a local plan for metadata revision without deleting durable state.

All local stable-key journal mutations use one shared atomic lock implementation. The journal is re-read only after that lock is acquired. An already-present lock blocks mutation rather than assuming it is stale; after an interrupted process, an operator must inspect the journal/lock before manually clearing anything.

If journal persistence fails while creating a plan, the newly written operator intent is removed before the command fails, so the planner does not hand off an intent that lacks its durable collision guard.

Old v1 intents/journals fail closed; they are not silently upgraded.

## Existing remote target adoption/reconciliation

A stable local journal is not allowed to “forget” a provider object merely because that object was created through historical code before the stable-key model existed.

Current main provides a separate read-only release-state entrypoint:

```text
python -m video_channel_manager.youtube_release_cli adopt-existing \
  --evidence <immutable-live-state.json> \
  --data-dir <runtime-data-dir> \
  --output <immutable-adoption-result.json>
```

The operation:

1. validates the non-authorizing live-state evidence and canonical project/account/channel identity **before** loading client-secret/token material;
2. computes the exact stable upload key from project/channel/media SHA-256;
3. reads the exact supplied video ID through the official API without enumerating or fuzzily matching uploads;
4. proves exact video ID, channel ID and evidence-declared title/privacy where those fields are present;
5. persists a `verified` stable journal entry containing the adopted video ID, provider revision and source-evidence digest;
6. initializes the release child-state model with both `existing-target` and `upload` verified as an adopted existing object, so upload is skipped rather than replayed;
7. refuses to overwrite a planned, ambiguous, different-remote or otherwise incompatible stable journal;
8. is idempotent for the same already-adopted video;
9. performs provider reads only and records `provider_writes=0` in immutable result evidence.

For the Black Man album, the historical media identity

```text
project_key = legendary-poet
target_channel_id = UC-78ys2S3cQ3lpqgXfo-SvQ
media_sha256 = sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0
```

has provider target `x-puy27S2qs`, recorded in `black-man-youtube-live-state-2026-08-09.json` and the release retrospective. The repository evidence can now be adopted into the stable journal by the read-only command above. Adoption is not upload, replacement or re-publication.

## Durable release child state

`video_channel_manager.youtube_release_state` defines ordered children:

```text
existing-target reconciliation
→ upload
→ processing/private readback
→ metadata/description
→ thumbnail
→ playlist memberships (exact IDs, in declared order)
→ visibility/publication
→ top-level comment
→ manual pin evidence
```

Each child stores an immutable payload digest before provider effect can become `may_exist` or `verified`. Effects are one of:

```text
not_dispatched / confirmed_absent / may_exist / verified
```

A `may_exist` child blocks all later work until read-only reconciliation. A `verified` parent cannot be downgraded or silently rebound to another remote ID/evidence digest. Existing-target `confirmed_absent` is the only absence state that permits the upload child to become eligible.

The state model is provider-agnostic and provider-free in tests. Issue #232 remains open for the concrete mutation/resume transport on top of these durable semantics.

## Provider-semantic normalization

Provider postconditions must compare values in their actual semantic domain rather than raw JSON presentation.

### Tags

`snippet.tags` is treated as an unordered collection with multiplicity preserved. Provider reordering is not a mismatch. Repository code should use the pure semantics in `video_channel_manager.youtube_provider_semantics.tags_equivalent()` rather than list equality.

### Optional boolean readback

For fields such as `status.containsSyntheticMedia`, an omitted key is `unobserved`, not `false`. Exact false/true values remain comparable when returned. A field-specific proof policy may require separate UI/operator evidence when the provider API does not expose the expected value.

### Accepted mutation followed by empty readback

An accepted provider mutation plus one empty/non-converged read is `may_exist`, never `confirmed_absent`. Preserve any returned remote object ID, poll only within a bounded read-only convergence window, and stop for reconciliation if the object is still not observable.

For playlist membership specifically, verification must fully enumerate the target playlist with pagination and match exact video ID via `contentDetails.videoId` or `snippet.resourceId.videoId`. One immediate filtered read must not be promoted to proof of absence after an accepted insert.

## Local CLI surfaces

The upload planner remains deliberately provider-inert:

```text
python -m video_channel_manager.youtube_upload_plan_cli plan ...
python -m video_channel_manager.youtube_upload_plan_cli status ...
python -m video_channel_manager.youtube_upload_plan_cli abandon ...
```

Read-only existing-target adoption is a separate release surface:

```text
python -m video_channel_manager.youtube_release_cli adopt-existing ...
```

There is no provider `execute` command in this baseline.

## Black Man status

The old PR #171 upload spec is deliberately not copied into current `main`. It contains metadata/timestamps from before the quality-master provenance work and must not be treated as a current final provider payload.

Historical release evidence records media SHA-256 `sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0`, target channel `UC-78ys2S3cQ3lpqgXfo-SvQ`, and provider video `x-puy27S2qs`, verified public at the end of the 2026-08-09 release session.

That provider success does **not** convert the old MP4 into current-policy artifact proof: Issue #154 still requires regeneration from the exact accepted seven quality masters under the post-#213 provenance contract when those bytes are available to the executing environment.

## Future execution boundary

Issue #232 owns the next layer: concrete current-main provider mutation/resume transport on top of the stable key, adoption and child-state model. Before any future `videos.insert` it must at minimum:

1. load and validate the v2 intent;
2. prove canonical project/account/channel identity before credentials;
3. acquire the same stable-key lock;
4. re-read the stable journal under the lock;
5. reconcile/adopt known existing provider targets;
6. refuse `may_exist`, `verified`, adopted-existing, unknown or stale journal states;
7. persist the exact child payload digest before provider mutation;
8. never create a second `videos.insert` to resolve an ambiguous first attempt;
9. reconcile/read back the exact provider result before marking `verified`;
10. keep thumbnail, playlist membership, publication and comment as separately journaled child operations rather than replaying upload as recovery.

None of those provider mutations are implemented or authorized by the adoption layer.
