# Milovi Cake Telegram

Owning issue: #353.

This directory contains **provider-inert editorial and canary-preparation material only**. It is not a scheduler queue and is not consumed by the Telegram publisher runtime.

Current artifacts:

- `launch-pack-2026-08.md` — reviewed-source launch corpus for editorial preparation;
- `editorial-asset-contract-2026-08.md` — current source-availability constraint for what the launch corpus may actually promise or show;
- `media-source-map-2026-08.json` — machine-readable mirror of the verified 46-item Milovi Cake finished-work gallery source (30 photos + 16 videos), bound to its source blob;
- `school-source-shortlist-2026-08.json` — exact Milovi School catalog/deep-content binding for the three educational launch topics, with conservative Telegram claim boundaries and mandatory pre-publication revalidation;
- `editorial-sequence-30-posts-2026-08.json` — provider-inert 30-slot launch sequence with exact finished-media IDs, exact School article IDs and a 0% production-BTS share;
- `editorial-operating-plan-2026-08.md` — channel-quality, reuse, caption, cadence and acquisition rules while production footage is unavailable;
- `media-delivery-readiness-2026-08.json` — reviewed Telegram photo/video transport constraints and current fail-closed readiness state;
- `canary-candidate-2026-08.json` — one exact future `sendPhoto` candidate with unresolved target/binding and provider authorization explicitly false;
- `canary-review-lock-2026-08.json` — exact Git-blob identities for the reviewed candidate/readiness bytes plus unresolved authorization inputs;
- `canary-preparation-2026-08.md` — human-readable pre-dispatch, target, media, authorization and outcome-verification boundaries for that exact candidate.

The asset contract is authoritative when an older draft/example could be read as requiring kitchen, production or BTS footage. While the current contract is active, finished-cake photos/videos are the primary visual source and production BTS/kitchen content remains at 0% unless separately reviewed source footage exists.

The older launch corpus contains one known ambiguous welcome phrase (`детали и процесс`). It must not be published as written while the current no-BTS contract is active. The exact safe replacement and interpretation rule live in `editorial-operating-plan-2026-08.md`.

The School shortlist is a source binding, not permission to copy metadata claims straight into a live post. The exact article/deep content and its source trail must be re-read before a School draft becomes a live payload.

The canary candidate is deliberately **not executable**. Its numeric `chat_id`, discovery proof, immutable target-binding digest, materialized media SHA-256 and decoded dimensions are unresolved; `publication_authorized=false`, `execution_ready=false`, and `provider_mutation_allowed=false`. Do not fill those fields by inference or by copying a value from another Telegram project.

The canary review lock protects the exact candidate/readiness bytes. Any change that produces a different Git blob invalidates the lock and requires a new review identity before authorization can even be considered.

Current WebM gallery videos are editorial source assets, not proven Telegram-native video payloads. Do not silently send them as documents. A separate deterministic MP4 conversion/readiness lane is required before a WebM-backed slot becomes a native-video release candidate.

Live publication requires, in order:

1. write-disabled Milovi identity profile;
2. fresh read-only exact target proof on current `main`;
3. separately reviewed immutable target binding;
4. cross-project fail-closed guards;
5. materialized/verified exact media bytes for the selected candidate;
6. one exact explicitly authorized canary tied to the reviewed candidate identity;
7. verified provider outcome before any subsequent post, pin, schedule or automation.

Do not convert editorial drafts, the media map, editorial sequence or canary-preparation files into a release queue merely because these files exist.
