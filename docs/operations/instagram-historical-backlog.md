# Instagram historical factory backlog

Status: provider-inert  
Owner issue: #492  
Scope: historical repository evidence only; not current YouTube provider state

## Purpose

The Legendary Poet repository already freezes a reviewed historical YouTube→VK identity floor in:

```text
content/mappings/youtube-vk-reviewed-20260727.json
```

That mapping is useful for ensuring the old catalog is not silently ignored, but it is **not** a fresh YouTube inventory. This lane converts that historical floor into a deterministic editorial backlog without making any claim that an ID is currently public, private, deleted, Short, long-form, or even still present on the provider.

Current provider presence and current YouTube surface classification belong only to a fresh owner read-only `video-manager youtube scan` followed by `instagram video-intake` / `factory-coverage`.

## Command

For the registered `legendary-poet` project the canonical historical mapping and reviewed editorial corpus are resolved automatically from the repository:

```powershell
video-manager instagram historical-backlog `
  .\content\instagram\legendary-poet-reels-factory.json `
  --output .\data\reports\legendary-poet-instagram-historical-backlog.json
```

The command hashes the exact bytes of:

1. the historical mapping;
2. the deterministically ordered reviewed `content/youtube-comments/*.json` corpus;
3. the exact Reel factory registry.

The generated artifact carries:

```text
evidence_scope = historical_floor_not_current_provider_state
provider_effect = impossible
provider_writes_authorized = false
```

## Deterministic actions

Every ID in the historical mapping receives exactly one action:

| Evidence | Action |
| --- | --- |
| exact factory Reel jobs + reviewed editorial authority | `already_covered` |
| reviewed editorial authority, no factory Reel jobs | `design_reel_jobs` |
| no reviewed editorial authority and no factory Reel jobs | `build_editorial_record` |

An ID cannot be marked `already_covered` merely because a Reel job references it. If reviewed editorial authority has disappeared, the builder fails closed.

Reviewed IDs or factory YouTube sources that are not members of the old mapping are preserved separately as `*_outside_historical_floor`; they do not silently expand or rewrite the historical baseline.

## Repository baseline on 2026-08-20

The current frozen repository evidence is regression-locked as:

```text
historical floor                 111
already_covered                    9
design_reel_jobs                    6
build_editorial_record             96
reviewed outside historical floor   0
factory sources outside floor       0
```

These are historical-evidence counts, **not current YouTube counts**.

## What this artifact deliberately does not contain

It does not infer or store:

- current provider presence;
- current privacy status;
- current title or description;
- current Short / long-form status;
- current thumbnails;
- clean-master availability;
- rights clearance;
- Reel cut timestamps;
- Instagram provider account identity;
- publication authorization.

Those facts belong to their own exact-evidence lanes. Keeping them out of the historical backlog is intentional: an old mapping must never masquerade as a current provider snapshot.

## Schema

The normal schema export includes:

```text
instagram-historical-factory-backlog-v1.schema.json
```

Unknown fields are rejected. The output is a planning artifact only and cannot authorize a provider write.
