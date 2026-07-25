# Unified Editorial Operational Runbook

## Safety boundary

All commands in `video-manager content` are local read/validate/render/plan operations. They do not call YouTube or VK write APIs. Remote mutation remains inside the existing platform-specific guarded executors with fresh snapshots, exact confirmations, local writer locks, journals, and postflight verification.

## Audit and queue

Use the existing platform audits first:

```powershell
python scripts/audit_youtube_comments.py ...
python scripts/build_youtube_comment_editorial_queue.py ...
python scripts/audit_all_vk_descriptions.py ...
```

Do not author against stale target IDs or remembered remote text.

## Validate records

```powershell
video-manager content validate --input content/editorial
```

Legacy YouTube comment v2 files can also be validated and previewed directly.

## Preview one record

```powershell
video-manager content preview --platform youtube --surface comment --input content/editorial/examples/tyutchev-night-sea.json
video-manager content preview --platform vk --surface video_description --input content/editorial/examples/tyutchev-night-sea.json
```

## Preview a batch

```powershell
video-manager content preview --platform youtube --surface comment --input content/editorial --strict --json-output artifacts/youtube-preview.json
video-manager content preview --platform vk --surface video_description --input content/editorial --strict --json-output artifacts/vk-preview.json
```

Batch preview rejects duplicate variation keys, duplicate content IDs, and duplicate rendered text.

## Build a generic signed content plan

Prepare a reviewed target manifest:

```json
{
  "source_snapshot": "artifacts/vk-audit.json",
  "source_snapshot_generated_at": "2026-07-25T20:30:00+00:00",
  "operations": [
    {
      "content_id": "tyutchev-night-sea",
      "action": "update",
      "target_id": "123_456",
      "expected_before_text": "Exact current text from the snapshot",
      "expected_revision": "sha256:exact-live-revision"
    }
  ]
}
```

Then build and validate:

```powershell
video-manager content plan build --platform vk --surface video_description --input content/editorial --targets artifacts/vk-targets.json --output artifacts/vk-editorial-plan.json
video-manager content plan validate artifacts/vk-editorial-plan.json
```

The plan contains deterministic operation IDs, exact-before hashes, expected revisions, rendered hashes, operation-set hash, counts, and a final plan SHA-256.

## Read-only preflight and resume classification

Export fresh target state, then run:

```powershell
video-manager content plan preflight artifacts/vk-editorial-plan.json --state artifacts/vk-live-state.json
```

Every operation becomes `ready`, `already_applied`, or `conflict`. A rerun after a successful write is idempotently classified as `already_applied`; a changed target becomes `conflict`.

## YouTube comments apply path

Existing YouTube comment records now pass through the common canonical validator and `YouTubeCommentRenderer`. Continue using the established workflow:

```powershell
python scripts/build_youtube_comment_plan.py ...
python scripts/apply_youtube_comment_plan.py ... # dry-run first; --execute only after exact confirmations
```

The existing self-validating comment plan, channel lock, journal-before-write, verification, and resume behavior remain unchanged.

## VK catalog apply path

Build the existing guarded VK catalog plan from fresh YouTube/VK audit packages, then replace its description outputs with canonical records:

```powershell
python scripts/build_vk_catalog_plan.py ...
video-manager content plan adapt-vk-catalog artifacts/vk-catalog-plan.json --input content/editorial --output artifacts/vk-catalog-editorial-plan.json
python scripts/apply_vk_catalog_plan.py artifacts/vk-catalog-editorial-plan.json ... # dry-run first
```

`adapt-vk-catalog` preserves the existing source/target snapshot IDs, target inventory digest, exact before-title/description hashes, and executor-compatible operation IDs. It replaces only reviewed `after_description` values, adds editorial provenance, recalculates hashes, and re-signs the complete VK catalog plan.

## Execute and resume

Never skip the platform executor dry-run. Execute only with the exact plan SHA and confirmations required by that executor. On interruption, use its journal/resume path; do not regenerate a plan from memory or edit a signed JSON file by hand.
