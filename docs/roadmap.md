# Roadmap

## Foundation — completed in this PR

- modular Python package and PowerShell-friendly CLI;
- typed configuration and safe defaults;
- platform-neutral domain records;
- strict AuditPackage and ChangePlan 1.0 contracts;
- policy validation and plan preview;
- SQLAlchemy schema and Alembic baseline;
- local read-only media inventory;
- YouTube/VK adapter boundaries;
- tests, linting, typing, CI, and architecture documentation.

## Milestone 1 — YouTube read-only organizer

- Google OAuth desktop flow with refresh-token storage;
- channel discovery for accounts with multiple channels;
- complete paginated inventory of videos and playlists;
- normalized revisions and immutable snapshots;
- first deterministic rules: missing playlists, empty descriptions, stale links;
- export compact AI-specific packages.

## Milestone 2 — safe YouTube mutations

- playlist creation and membership changes;
- precondition re-read and revision checks;
- idempotency and retries;
- operation executor and verification;
- snapshots before/after and rollback for metadata.

## Milestone 3 — VK organizer

- administrator OAuth/token flow;
- community video and album inventory;
- safe metadata and album operations;
- VK-specific capability and limit checks.

## Milestone 4 — cross-platform comparison and transfer

- confirmed and probabilistic publication matching;
- YouTube/VK difference reports;
- yt-dlp cache for missing local sources;
- resumable VK upload queue;
- thumbnail and platform-specific description templates.

## Milestone 5 — local media intelligence

- ffprobe metadata;
- duplicate hashing;
- duration/title/frame/audio matching;
- immutable links between publications and confirmed local sources;
- no automatic deletion.

## Milestone 6 — interfaces

- local web dashboard;
- optional Telegram client for status and approvals;
- scheduled audits and notifications.
