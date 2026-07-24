# YouTube OAuth and read-only inventory

The first live adapter intentionally requests only:

```text
https://www.googleapis.com/auth/youtube.readonly
```

It cannot change titles, descriptions, playlists, privacy, thumbnails, or videos.

## Local files

```text
secrets/client_secret.json          # downloaded Google Desktop OAuth client
data/secrets/youtube/<alias>.json   # access + refresh token
data/youtube/accounts.json          # non-secret local registry
data/exports/*.json                 # AuditPackage exports
```

All runtime and credential paths are ignored by Git. Never paste their contents into issues, logs, or AI chats.

## First authorization

```powershell
video-manager youtube login --account legendary-poet
```

A loopback server binds to `127.0.0.1` on a random port. The system browser opens Google authorization. The flow uses PKCE, validates `state`, requests offline access, and stores the refresh token locally.

For another Google or Brand Account, use another alias:

```powershell
video-manager youtube login --account theology
```

## Inventory

```powershell
video-manager youtube accounts
video-manager youtube channels --account legendary-poet
video-manager youtube scan --account legendary-poet
```

When an OAuth identity exposes multiple channels, pass the exact channel ID:

```powershell
video-manager youtube scan --account legendary-poet --channel UCxxxxxxxx
```

The scan paginates the uploads playlist, batches `videos.list`, reads user-created playlists and memberships, computes deterministic revisions, and exports one versioned `AuditPackage` for a human or external AI.

## Testing-mode warning

Google OAuth apps left in External **Testing** mode can issue refresh tokens with a limited lifetime for sensitive scopes. Add every account as a test user for initial work. For long-running personal use, review the Google Auth Platform publishing status and move the app to production when appropriate; do not submit public verification unless the application will actually be distributed to other users.
