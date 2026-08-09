# Svodka production rollout — August 2026

Owner scope: live rollout for `@deep_info_life` after repository implementation issue #170 was closed. Issue #235 owns the production rollout until a verified autonomous scheduled publication is recorded.

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
- approved release SHA-256: `sha256:e774115e4382ef9ff1871f0d9b5a7d80c075f41c66ecc9963ccbee7c23d41233`;
- immutable approval receipt: `content/telegram/svodka/release-approval-2026-08.json`;
- the full approved release is deterministically materialized and both candidate/release digests are checked before state or provider operations.

## Current rollout state

- repository implementation: complete;
- exact target binding: complete/read-only verified;
- effective 14-item schedule: complete;
- approval receipt: committed;
- profile execution gate: enabled;
- durable ledger: not initialized yet;
- manual canary: not yet verified;
- scheduled workflow: configured for Aug. 10–16 but cannot dispatch until the same release has a verified manual canary in durable state;
- rollout completion: false.

## Remaining gates

1. Exact-head PR CI and rollout candidate proof must be green.
2. Merge the reviewed rollout change without head drift.
3. Current `main` must pass both `svodka-quality.yml` and `svodka-approved-release-quality.yml`.
4. Initialize the exact release ledger on `state/svodka-telegram`.
5. Dispatch exactly one fresh strict-next manual canary with durable intent-before-send and zero blind retries.
6. Verify the exact provider receipt/state for that canary.
7. Let the scheduled publisher dispatch only the remaining strict-next items inside freshness windows and the two-per-day verified quota.
8. Record the first autonomous scheduled proof and immutable final rollout state before closing #235.

## Safety invariants

- no title/fuzzy target selection;
- exact channel/bot binding before provider access;
- immutable approval binds exact candidate and exact approved release digests;
- no mutation retry after ambiguous provider outcome;
- one durable intent before each provider mutation;
- `may_exist`/unknown outcomes block automatic replay;
- maximum two verified publications per Europe/Moscow day;
- no scheduled dispatch before a verified same-release manual canary;
- archived outcome recovery remains provider-free and tied to the exact persisted dispatch/release;
- YouTube work remains independent from this rollout.
