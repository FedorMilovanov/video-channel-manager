# Legendary Poet article wave — August 2026

Owner: issue #99  
Project: `legendary-poet`  
VK community: `235216998`  
VK owner: `-235216998`

## Approved scope

Fedor approved ten article posts without editorial changes. The immutable policy is:

```text
data/editorial/legendary-poet-article-wave-202608.json
```

Policy SHA-256:

```text
sha256:af210867d2ea392394e2034cffa9d43c3e1adc632386e9ec4827b033c8fff9a0
```

The schedule is every two days at 19:00 Europe/Moscow from 2026-08-06 through 2026-08-24.

## Supported sequence

1. Run `video-manager wave article prepare` from a clean current `main` checkout.
2. Review the generated preparation summary and ten JPEG 1200×630 asset identities.
3. Execute only the one-operation canary request through `scripts/operator/Invoke-VideoManager.ps1`.
4. Verify the exact postponed canary result and remote post identity.
5. Execute the separate nine-operation batch request only after the canary succeeds.

Canary and batch are intentionally separate immutable Wave plans. Do not combine them into one unattended operation.

## Provider boundaries

The only registered production operation kind for this workflow is:

```text
vk_postponed_article_photo
```

Every operation is bound to the exact approved policy row, project identity, message, article URL, cover URL, publish date, deterministic guid, materialized JPEG digest, and canary dependency.

The provider adapter performs complete published/postponed preflight, blocks duplicate messages and occupied schedule slots, saves one wall photo, creates one postponed wall post, and verifies one exact wall delta.

## Unknown outcomes

After any ambiguous provider dispatch:

- do not delete the Wave journal;
- do not rerun the apply request;
- do not retransmit `photos.saveWallPhoto` or `wall.post`;
- build an exact reconciliation request from the Wave result;
- reconcile by reading the approved postponed-post identity.

## Isolation

This workflow does not authorize video uploads, Shorts/Clips work, VK Audio, catalog edits, cleanup, theological-project operations, or other Wave operation kinds.
