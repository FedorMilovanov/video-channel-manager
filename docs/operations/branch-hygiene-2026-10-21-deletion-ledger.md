# Branch hygiene ledger — 2026-10-21

Classification produced from the GitHub compare API (`main...<branch>`), not from ref age,
prefix or a shallow local clone. A branch was deleted only when **every head-side blob of every
file it changes is byte-identical to `main`** — that is, its content is fully contained in `main`
and deletion loses nothing. `state/*` refs are durable state and are never candidates.

Each deleted ref is recorded below with its exact tip SHA, so a restoration is
`git push origin <sha>:refs/heads/<branch>` if it is ever needed.

Deleted 24 refs:

| Branch | Tip SHA |
| --- | --- |
| `agent/instagram-facebook-state-sync-577` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-historical-editorial-552` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-historical-live-561` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-slot-aware-production-20260906-v2` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-spurgeon-v3-live-media-561` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/retirement-archive-blob-integrity` | `b8250d9771bd48efef22913565a6020b7cf0fac1` |
| `arena/01a10838-video-channel-manager` | `59100ed6429ec02a7a78b7403b7cad65f377054e` |
| `arena/13447cc8-video-channel-manager` | `17c4521d44a305964fb0d7177c98e71c5e81636f` |
| `do-not-use` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `feat/lordchrist-historical-v3-archival-revisions-561` | `b8250d9771bd48efef22913565a6020b7cf0fac1` |
| `feat/lordchrist-quote-v4-readiness-20261004` | `ae05e10fef0aed1aa18cdeb97f3d5d5279a5be70` |
| `feature/lordchrist-successor-quote-corpus-v1-20260906` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `final-accidental` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `fix/instagram-cli-unicode-638` | `310b5e3a6ad7245d2585c965320497e68a3fb39f` |
| `fix/instagram-resumable-phase-diagnostics` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `fix/lordchrist-editorial-completeness-665` | `8807a466353b813d173fca5344da8f64a393d5d6` |
| `fix/lordchrist-quote-handoff-576` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `lane/lordchrist-history-human-editorial-561-20260907-copy` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `lane/lordchrist-spurgeon-v3-media-561-20260908` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `oops6` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `probe/lordchrist-historical-v3-final-sources-561` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `research/lordchrist-calvin-spurgeon-macarthur-series-v1` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `tmp-noop` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `zzz-test-ignore` | `254d90c8b0b72774dcb798e5b176cacb83288561` |

## Deliberately kept

The remaining branches carry content that is **not** in `main` (older editorial drafts with unique
binaries, unreleased wave/provider work, or history superseded in intent but not byte-identically).
They are kept until each is closed on its own evidence, and no branch is deleted merely because it
looks stale. The audit lists them for individual disposition.
