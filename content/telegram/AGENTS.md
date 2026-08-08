# Telegram content agent instructions

These instructions apply to `content/telegram/**` and are the current overlay for active Telegram/Svodka work requested on 2026-08-08.

For Svodka, read before changing content or activation artifacts:

1. `../../docs/operations/svodka-readiness.md`
2. `../../docs/operations/svodka-recovery.md`
3. `../../docs/operations/telegram-multichannel-migration.md`
4. `../../docs/research/2026-08-08-svodka-technical-verification-ledger.md`
5. `../../docs/research/2026-08-08-svodka-second-pass-audit.md`
6. `../../docs/research/2026-08-08-svodka-third-pass-audit.md`

The older repository-wide statement that no provider continuation was pending predates this explicit Svodka project. It must not be used to discard, overwrite or reinterpret the newer Svodka-specific state above. Historical material remains evidence only.

## Shared Telegram bot is intentional

One Telegram bot intentionally manages multiple channels. The current shared bot is:

- bot id `8716602202`;
- username `@preaching_mp3_bot`.

The shared bot token is a credential, not a channel selector. A legacy secret may still be named `LORDCHRIST_TELEGRAM_BOT_TOKEN`; mapping that same secret into the environment variable expected by the Svodka profile is intentional and is not cross-channel contamination.

Never create a second bot or duplicate token only to make configuration names symmetric unless an explicit future migration changes this architecture.

Exact channel isolation comes from all of the following together:

- selected `TelegramChannelProfile`;
- exact numeric `chat_id` and username;
- exact target-binding digest;
- immutable release digest and provider payload digests;
- separate state branch;
- shared single-writer concurrency group for that channel's mutations;
- fresh read-only preflight immediately before provider mutation.

## Current Svodka activation state

At the time of this instruction:

- channel: `@deep_info_life` / `СВОДКА`;
- profile: `content/telegram/channels/svodka.json`;
- exact binding: `content/telegram/channels/svodka-target-binding.json`;
- pilot queue: `content/telegram/svodka/draft-14-posts-2026-08.json`;
- canonical release id: `svodka-pilot-2026-08`;
- state branch: `state/svodka-telegram`;
- profile write gate: `provider_writes_authorized=false`;
- approved release: intentionally absent until exact candidate review;
- scheduler: installed but fail-closed and currently inactive;
- provider mutation by the current audit: none.

Do not infer that the scheduler's existence authorizes publication. It remains blocked until the exact approved release, write gate, ledger and verified manual canary exist.

## Content/release rules

- Canonical editorial JSON is edited directly; workflows do not rewrite facts or wording.
- Dynamic web/search results are never auto-published.
- Every structured source URL must remain visible to the reader.
- Prefer primary papers and official institutional sources; do not turn interpretations into established facts.
- The draft queue remains write-disabled. Authorization belongs to a separate reviewed immutable release.
- Quality and preflight must reproduce the same canonical target-bound `svodka-review-candidate` using release id `svodka-pilot-2026-08`.
- Authorized release provenance must self-verify `reviewed_candidate_sha256` against the immutable candidate representation.
- Never hand-edit an approved release to bypass candidate review.
- A missed publication window is skipped as `impossible`; never backfill a stale time-sensitive post merely to preserve count.
- `may_exist` is a hard stop for blind retry.
