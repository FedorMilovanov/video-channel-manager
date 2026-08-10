# Svodka production rollout — August 2026

Owner scope: live rollout for `@deep_info_life` after repository implementation issue #170 was closed. Issue #235 remains open and owns the production rollout until a verified autonomous scheduled publication is durably recorded.

This document records the reviewed rollout contract and durable checkpoints. It is **not** the mutable provider-state authority. At every operation start, read the current `state/svodka-telegram` ledger and Issue #235 first.

## Exact target

- channel: `@deep_info_life`
- chat id: `-1003527567039`
- bot id: `8716602202`
- bot username: `preaching_mp3_bot`
- state branch: `state/svodka-telegram`

## Approved pilot

- effective window: 2026-08-10 through 2026-08-16, Europe/Moscow;
- slots: 10:30 and 19:30 Europe/Moscow;
- materials: all 14 reviewed items are preserved;
- the time-sensitive Aug. 12 eclipse item is explicitly scheduled for 10:30 before the evergreen octopus item at 19:30;
- reviewed candidate SHA-256: `sha256:98e259210f138b8ad0280dec38306dcecbbdba89899db336906994f9dfb0bc0f`;
- approved release SHA-256: `sha256:959a42e914acedc6969550ba842a12d1a2b174c940497d8a98f4ab8e2e63cdce`;
- immutable approval receipt: `content/telegram/svodka/release-approval-2026-08.json`;
- the full approved release is deterministically materialized and both candidate/release digests are checked before state or provider operations.

## Completed rollout gates

- repository implementation: complete;
- exact target binding: complete/read-only verified;
- effective 14-item schedule: complete;
- approval receipt: committed;
- profile execution gate: enabled;
- rollout PR #236: merged without head drift as `877fc12dd28f87f864283050d47aa03e70b2a21b`;
- exact-head PR CI: 6/6 green;
- exact-head rollout-candidate workflow: green and reproduced candidate `sha256:98e259210f138b8ad0280dec38306dcecbbdba89899db336906994f9dfb0bc0f`;
- provider writes performed by PR #236: 0.

## Durable checkpoint and live-truth boundary

The latest verified checkpoint captured during the 2026-08-10 audit is:

- the exact ledger for approved release `sha256:959a42e914acedc6969550ba842a12d1a2b174c940497d8a98f4ab8e2e63cdce` is initialized;
- all 14 approved entries are still `pending` with `provider_effect=impossible`;
- no manual canary is durably verified and no provider receipt is recorded;
- scheduled workflow remains canary-gated;
- rollout completion is false and Issue #235 remains open.

This checkpoint is historical evidence only. If the durable state branch has advanced, the branch wins.

## Remaining gates before rollout completion

1. Resolve the current exact durable state and current-main quality before any provider operation.
2. If strict-next is outside its bounded freshness window, use only the reviewed state-only expired-slot recovery semantics; the observed freshness/recovery dead zone must fail closed and must not be bypassed by a guessed skip or send.
3. The next provider mutation, when one is again eligible, must be exactly one fresh strict-next manual canary for this approved release with durable intent-before-send and zero blind retries.
4. Require the exact canary result to be durably `published` with `provider_effect=verified`, exact chat/bot identity and message receipt.
5. Only after that verified same-release manual canary may the scheduled publisher dispatch remaining strict-next items inside freshness windows and the two-per-day verified quota.
6. Record at least one autonomous scheduled publication in durable state.
7. Only then mark rollout complete and close Issue #235.

## Recovery paths

- missed but never-dispatched publication windows may be marked skipped only by the explicit state-only `svodka-skip-expired.yml` workflow after exact-release validation and the same bounded freshness semantics used by dispatch;
- a persisted intent whose GitHub send step is proven `skipped` may be reconciled to `confirmed_absent` only through `svodka-reconcile-skipped-send.yml`;
- an unresolved mutation with an archived provider outcome may be recovered provider-free through `svodka-reconcile-provider-outcome.yml` after exact run/artifact/dispatch validation;
- ambiguous/may-exist provider effects are never blindly retried.

## Safety invariants

- no title/fuzzy target selection;
- exact channel/bot binding before provider access;
- immutable approval binds exact candidate and exact approved release digests;
- no mutation retry after ambiguous provider outcome;
- one durable intent before each provider mutation;
- `may_exist`/unknown outcomes block automatic replay;
- maximum two verified publications per Europe/Moscow day;
- no scheduled dispatch before a verified same-release manual canary;
- all Svodka state writers share one non-cancelling concurrency group;
- archived outcome recovery remains provider-free and tied to the exact persisted dispatch/release;
- YouTube work remains independent from this rollout.
