# External AI exchange format

The application intentionally does not embed an AI model. Data moves through two strict, versioned documents.

## AuditPackage 1.0

A read-only snapshot containing:

- exact channel reference;
- exact video and collection IDs;
- revisions used for optimistic concurrency;
- memberships;
- deterministic audit findings;
- optional raw metadata.

The external AI may analyze this package, but it never receives OAuth tokens.

## ChangePlan 1.0

A proposed mutation set containing:

- source snapshot ID;
- exact target channel;
- unique operation IDs;
- enum-based operation types;
- exact target IDs;
- operation-specific payload;
- expected revision;
- risk level;
- human-readable rationale.

Example:

```json
{
  "schema_name": "video-manager.change-plan",
  "schema_version": "1.0",
  "source_snapshot_id": "00000000-0000-0000-0000-000000000000",
  "title": "Add Esenin videos to author playlist",
  "channel": {
    "platform": "youtube",
    "channel_id": "UC123",
    "remote_id": "UC123"
  },
  "operations": []
}
```

## Compatibility rules

- Patch-compatible additions require optional fields.
- Breaking changes require a new schema version.
- Importers reject unknown fields by default.
- Schema validity does not imply execution permission.
- IDs are never inferred from titles.
- Plans created from stale snapshots may be rejected at execution time.

Generate current JSON Schemas:

```powershell
video-manager schema export
```
