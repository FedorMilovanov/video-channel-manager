# 2026-08-08 generic release-review binding gap

## Finding

The first generic release-review helper required an exact candidate digest and non-empty target fields, but it did not independently prove that the candidate still matched the exact current `TelegramChannelProfile` and `TelegramTargetBinding` selected for review.

The live generic runtime would later reject a mismatched profile or target, so this did not create a direct provider-write bypass. It did, however, weaken the meaning of `release_authorized=true`: a stale or incorrectly rebound candidate could be marked reviewed and only fail later at execution.

## Fix

Generic release review now requires the exact profile and target binding as inputs and rejects drift in:

- project key;
- channel username;
- profile digest;
- timezone;
- daily verified limit;
- target-binding digest;
- numeric chat id;
- bot id;
- bot username.

The review operation remains provider-inert and does not require `provider_writes_authorized=true`.

## Regression invariant

`release_authorized=true` means the exact candidate digest was reviewed against the exact channel identity contract and exact immutable Telegram target binding. Provider-write authority remains a separate runtime gate.

The existing Lordchrist research validation workflow now covers generic release-review code and tests so changes to the approval boundary re-prove the exact research candidate before merge.
