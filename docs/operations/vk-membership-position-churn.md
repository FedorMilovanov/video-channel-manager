# VK membership position churn

## Incident

The first reviewed correction apply for three «Исповедь Самоубийцы» descriptions completed all three writes and produced an authoritative `status=completed` result journal. The final snapshot matched all reviewed after-states, but the outer wrapper reported failure during independent postflight.

The cause was not a catalog mutation. Two existing videos in system collection `-13` exchanged read-only `position` values between consecutive VK scans:

```text
-235216998_456239114: 37 -> 38
-235216998_456239113: 38 -> 37
```

The collection/video membership pairs remained identical. Membership count remained 294 and the canonical membership SHA-256 remained:

```text
sha256:bdb556321dce7b5dd9400de33c92fb186dce55faac327f0a5a077491bfd5b966
```

## Correct invariant

For editorial waves that have no catalog mutation methods, membership identity is the multiset of:

```text
(collection_remote_id, video_remote_id)
```

The following remain strict failures:

- a collection/video pair is added;
- a collection/video pair is removed;
- the membership count changes;
- the canonical membership SHA-256 changes;
- collection inventory or titles change.

The following is recorded as warning metadata rather than a failed write invariant:

- `position` changes while the exact collection/video identity multiset remains unchanged.

## Rationale

`position` is derived response metadata and can change between read-only scans, especially in system collections. A descriptions-only writer cannot call membership reorder methods. Comparing positions as if they were stable identities creates a false postflight failure after successful text writes.

## Safeguards

The reviewed correction apply verifier now:

1. compares membership identities with a strict `Counter` of collection/video pairs;
2. verifies the unchanged canonical membership SHA-256;
3. records every position-only difference in `membership_position_changes`;
4. still fails on any real membership addition or removal;
5. preserves outer-wrapper failure as a warning when the authoritative result journal and final VK state prove completion.

Regression tests cover both a two-item position swap and a real membership replacement.
