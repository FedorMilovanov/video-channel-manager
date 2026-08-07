# Generic multi-channel Telegram publisher runbook

Status: additive foundation on `main`; legacy `@lordchrist` production remains unchanged.

## Goal

One Telegram code path should be reusable for multiple channels without ever guessing a target or sharing publication state between channels. A new channel is represented by an immutable channel profile plus a reviewed release artifact. Provider writes remain impossible until both artifacts explicitly authorize them and a fresh exact target proof succeeds.

## Separation model

Each channel has its own:

- `project_key` and exact `@channel_username`;
- `publication_id_prefix`;
- timezone and daily verified limit;
- GitHub secret/variable names for bot and target identity;
- state branch and concurrency group;
- reviewed release queue and release digest;
- publication ledger and durable intent history.

The generic code does not use a global Telegram target. Every provider payload and target proof is bound to the selected profile SHA-256.

## Current Svodka profile

Canonical profile: `content/telegram/channels/svodka.json`.

It binds `svodka` to `@deep_info_life`, `Europe/Moscow`, a two-publication daily limit, `state/svodka-telegram`, and the `SVODKA_TELEGRAM_*` credential/identity namespace. It currently has `provider_writes_authorized=false`.

## Content lifecycle

```text
web / primary-source research
        ↓
draft editorial queue (write-disabled)
        ↓
strict validation + deterministic provider rendering
        ↓
release candidate (write-disabled, exact payload hashes)
        ↓
human review / immutable authorized release
        ↓
read-only exact bot + channel preflight
        ↓
initialize isolated release ledger
        ↓
manual exact publication_id canary
        ↓
verify returned chat/message/poll and persist receipt
        ↓
only then permit scheduled strict-order execution
```

Search results and AI output are never provider input by themselves. A scheduled job can only consume an already reviewed immutable release.

## Provider payloads

`sendMessage` and `sendPoll` are separate deterministic payload types. Polls follow the current Telegram Bot API contract used by the generic transport: quiz answers are represented by `correct_option_ids`; the Svodka poll description can expose source attribution while the provider payload remains hash-bound.

Mutation transport retries are disabled. If the provider response is ambiguous after a mutation attempt, the durable ledger must remain `unknown/may_exist`; the strict queue then blocks rather than blindly retrying and risking a duplicate.

## Target proof

Before any mutation, preflight resolves all of the following independently:

1. bot token via `getMe` → exact expected bot ID and username;
2. numeric channel ID via `getChat`;
3. public `@username` via a second `getChat` → same exact channel;
4. bot administrator membership via `getChatAdministrators(return_bots=true)`;
5. `can_post_messages` permission.

The resulting proof is profile-bound and short-lived. A stale proof cannot prepare a dispatch.

## Release and ledger gates

A generic dispatch requires all of these to be true at the same time:

- profile `provider_writes_authorized=true`;
- release `release_authorized=true` with reviewer and timezone-aware review timestamp;
- release profile digest exactly equals the selected profile digest;
- ledger digest/coverage exactly equals the immutable release;
- fresh exact target proof matches project/channel/bot;
- exact GitHub run ID, run attempt and code/workflow SHAs are present;
- manual publish names the strict-next `publication_id`, or scheduled item is already due;
- scheduled runs use attempt 1 only;
- scheduled production has a verified manual canary for the same chat and bot;
- the channel's daily verified quota is not exhausted.

Preparing a dispatch first persists `dispatching/may_exist` with an intent ID and exact execution provenance. Only a verified Telegram receipt can transition that entry to `published/verified`.

## Adding another Telegram channel

Do not copy hard-coded provider logic. Add a new profile under `content/telegram/channels/`, give it a unique state branch/concurrency group/credential namespace, validate its content with an editorial adapter, and freeze a generic release candidate. The provider transport, release model and durable ledger remain shared.

A thin channel workflow may map that profile's GitHub Secrets/Variables into the generic CLI. Credentials are never stored in profile files or queues.

## Svodka rollout state

The Svodka workflow `.github/workflows/svodka-telegram-preflight.yml` currently supports validation, deterministic preview, write-disabled release-candidate construction and read-only exact target preflight only. It has no schedule and no provider mutation step.

Do not create or enable a live schedule until the exact target/bot variables exist, read-only preflight has passed, a reviewed authorized release has been frozen, an isolated ledger exists, and one exact manual canary is verified.
