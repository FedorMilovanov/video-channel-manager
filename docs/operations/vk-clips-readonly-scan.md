# VK Clips read-only scan

## Purpose

`video-manager vk clips-scan` performs a bounded, mutation-free VK short-filter discovery for one exact canonical project.

It does **not** claim to enumerate the complete native Clips surface. The command uses VK API `video.search` with the exact owner plus `filters=short`, then classifies a native Clip only when the returned object itself proves `type=short_video`.

Current owning scope for Milovi Cake reconciliation: Issue #257. This runbook authorizes no provider mutation.

## Transport and provider effect

- transport: `official_api_read`
- provider writes: `0`
- retries: the existing safe-read VK HTTP policy only
- mutation endpoints: none

The command performs local canonical identity validation before the first provider call, then requires the provider to re-prove the exact community and that the current token manages it.

## Provider contract and observed behavior

The current VK API 5.199 schema defines:

- `video.search.owner_id` — exact video owner;
- `video.search.filters` — includes `short`, described as short videos only;
- `video.search.offset` / `count` — paginated search, max page size 200;
- `video_video.type` — includes both `video` and `short_video`.

Primary schema references:

- https://github.com/VKCOM/vk-api-schema/blob/master/video/methods.json
- https://github.com/VKCOM/vk-api-schema/blob/master/video/objects.json

Live Milovi Cake provider evidence on 2026-08-10 showed that `video.search(owner_id=-68859909, filters=short)` can return an object whose provider `type` is `video`. Therefore the documented `short` search filter is not treated as a Clip identity guarantee and is not treated as proof of complete native-Clip coverage.

The implementation fully paginates the bounded search, requires exact owner identity and valid IDs on every returned object, and then separates:

- `clips` — objects proving `type=short_video`;
- `filter_noise` — all other returned provider types, including ordinary `type=video` objects.

A foreign owner, invalid video ID, duplicate remote ID, project mismatch, or management-proof failure remains a hard stop. A non-Clip type is evidence, not a transport failure.

## Exact identity requirements

The caller must supply all three:

- canonical `project_key`;
- positive VK `community_id`;
- exact negative `owner_id = -community_id`.

For Milovi Cake:

```text
project_key: milovi-cake
community_id: 68859909
owner_id: -68859909
```

The local credential alias is authentication only and never selects the project.

## Coverage probes

Use `--require-remote-id` for an exact already-known public Clip. A probe is diagnostic evidence and is recorded in the snapshot in one of three states:

- `required_remote_ids_found_as_clips` — returned and proved `type=short_video`;
- `required_remote_ids_returned_non_clip` — returned by the short-filter search but not as `short_video`;
- `required_remote_ids_missing_from_search` — absent from this bounded search.

Milovi Cake has an exact known public probe:

```text
-68859909_456239130
```

A missing probe is important evidence about endpoint coverage, so v2 preserves the JSON result instead of discarding the snapshot. It still does **not** authorize an upload or prove that the Clip is absent from VK.

## Output

The command writes UTF-8 JSON with schema:

```text
vk-clips-readonly-audit-v2
```

Important fields:

- `project_key`, `account_alias`, `api_version`;
- exact community/owner and `managed_by_token=true` proof;
- immutable request contract used for the scan;
- `evidence_level=bounded_provider_search`;
- search candidate count, detected Clip count and filter-noise count;
- provider type counts;
- coverage-probe status;
- explicit `clip_surface_complete=false` and known limitations;
- every detected Clip and every filter-noise object with exact owner/video ID, provider type, title, description, duration, date, dimensions, views, permalink and raw provider object.

For an interactive Windows handoff, always pass an explicit output path under `operator-output` and return that exact file for review. Do not ask the operator to search timestamped export directories.

## Decision boundary

This snapshot may prove that a returned object **is** a native Clip when its exact provider object says `type=short_video`.

This snapshot may **not** prove that an unmatched source is missing from the native Clips surface. In particular:

- absence from `video.search(filters=short)` is not `missing_native_clip`;
- `filter_noise` is not converted into Clip identity by duration, title or vertical dimensions;
- a future upload queue must not be derived from this snapshot alone;
- ordinary VK videos, native Clips, published wall posts and postponed wall posts remain separate surfaces.

The next safe reconciliation step is to combine this bounded discovery with the ordinary VK inventory, exact known source/target markers, and separate published/postponed wall reads. Any remaining unmatched item stays `ambiguous/requires_attention` until a stronger provider or UI proof is available.

This command does not upload, hide, delete, edit, schedule, or publish anything.
