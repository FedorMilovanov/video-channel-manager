# VK Clips read-only scan

## Purpose

`video-manager vk clips-scan` enumerates the native VK Clips surface for one exact canonical project without changing provider state.

This command exists because the ordinary `video.get(owner_id=...)` inventory is not a complete Clips inventory for Milovi Cake: exact public `short_video` objects can be absent from that ordinary catalog. The scan therefore uses VK API `video.search` with the exact owner plus the `short` filter and then validates every returned object.

Current owning scope for Milovi Cake reconciliation: Issue #257. This runbook authorizes no provider mutation.

## Transport and provider effect

- transport: `official_api_read`
- provider writes: `0`
- retries: the existing safe-read VK HTTP policy only
- mutation endpoints: none

The command performs local canonical identity validation before the first provider call, then requires the provider to re-prove the exact community and that the current token manages it.

## Provider contract

The current VK API 5.199 schema defines:

- `video.search.owner_id` — exact video owner;
- `video.search.filters` — includes `short` for short videos only;
- `video.search.offset` / `count` — paginated search, max page size 200;
- `video_video.type` — includes `short_video`.

Primary schema references:

- https://github.com/VKCOM/vk-api-schema/blob/master/video/methods.json
- https://github.com/VKCOM/vk-api-schema/blob/master/video/objects.json

The implementation sends the one-element array filter in VK's wire representation as `filters=short`, fully paginates through the repository's existing safe-read offset helper, and fails closed if any returned object:

- belongs to another owner;
- lacks a valid positive video ID;
- is not exactly `type=short_video`;
- duplicates a remote ID already returned on another page.

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

Use `--require-remote-id` when an exact already-known Clip should be present in the surface. The command fails if a required probe is absent, rather than silently treating an incomplete/changed provider response as complete evidence.

Milovi Cake has an exact known public probe:

```text
-68859909_456239130
```

The option can be repeated for multiple probes.

## Output

The command writes UTF-8 JSON with schema:

```text
vk-clips-readonly-audit-v1
```

Important fields:

- `project_key`, `account_alias`, `api_version`;
- exact community/owner and `managed_by_token=true` proof;
- immutable request contract used for the scan;
- coverage count and required-probe results;
- every Clip's exact `owner_id`, `video_id`, combined remote ID, `type`, title, description, duration, date, dimensions, views, permalink, and raw provider object.

For an interactive Windows handoff, always pass an explicit output path under `operator-output` and return that exact file for review. Do not ask the operator to search timestamped export directories.

## Stop conditions

Stop without mutation if:

- project/community/owner identity mismatches canonical registration;
- the credential cannot prove management of the exact community;
- VK returns a foreign owner or non-`short_video` object under the short-filter scan;
- a required exact coverage probe is missing;
- the provider response is otherwise malformed or ambiguous.

An unmatched YouTube Short is not `missing_native_clip` until this complete Clips surface is reconciled against the source inventory. This command does not upload, hide, delete, edit, schedule, or publish anything.
