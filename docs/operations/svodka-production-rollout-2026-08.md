# Svodka production rollout — August 2026

Owner scope: live rollout for `@deep_info_life` after repository implementation issue #170 was closed.

This document restores the missing operational ownership boundary. Repository implementation is already present; production rollout is not complete until an exact reviewed release is committed, the isolated ledger is initialized, one exact manual canary is verified, and scheduled publication is proven from durable state.

## Current known target

- channel: `@deep_info_life`
- chat id: `-1003527567039`
- bot id: `8716602202`
- bot username: `preaching_mp3_bot`

## Current rollout state

- repository implementation: complete
- target binding: complete/read-only verified
- 14-post queue: present, review-only
- approved release: absent
- profile provider-write gate: disabled
- durable state branch: present
- manual canary: not yet verified
- scheduled production: not yet active

## Rollout gates

1. Rebase the pilot onto a fresh 7-day window without dropping any of the 14 reviewed materials.
2. Run exact-current-main Svodka quality and read-only target preflight.
3. Freeze and review the exact target-bound candidate digest.
4. Commit an authorized immutable release derived from that exact candidate.
5. Enable the profile provider-write gate only in the same reviewed rollout change.
6. Initialize the exact release ledger on `state/svodka-telegram`.
7. Dispatch exactly one fresh manual canary with durable intent-before-send and zero blind retries.
8. Verify exact provider receipt/state for that canary.
9. Only after the verified manual canary, allow the scheduled publisher to dispatch the remaining strict-next items.
10. Record the first autonomous scheduled proof and final rollout state in immutable audit/current-state documentation.

## Safety invariants

- no title/fuzzy target selection;
- exact channel/bot binding before provider access;
- no mutation retry after ambiguous provider outcome;
- one durable intent before each provider mutation;
- `may_exist`/unknown outcomes block automatic replay;
- maximum two verified publications per Europe/Moscow day;
- no schedule-only activation without a verified same-release manual canary;
- YouTube work remains independent from this rollout.
