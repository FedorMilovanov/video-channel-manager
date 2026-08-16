# Milovi Cake Telegram — live rollout state

Updated: 2026-08-16
Owning issue: #353
Project: `milovi-cake`
Channel: `@MiloviCake`

This directory is the durable handoff for the exact live Telegram rollout. Historical editorial/canary preparation files remain provider-inert unless an exact live authorization says otherwise.

## Exact target evidence

Fresh read-only recovery proved:

- channel username: `@MiloviCake`;
- exact Bot API chat id: `-1002215328390`;
- type: `channel`;
- username → numeric id → username round trip: proved;
- exact bot token identity: `8716602202 / @preaching_mp3_bot`.

Telegram does not expose membership for this bot/channel through the attempted read-only `getChatMember` call and returns `Bad Request: member list is inaccessible`. This error is not treated as membership or posting-right proof.

## Exact canary media evidence

Publication: `milovi-cake-canary-001`
Operation: `sendPhoto`
Source media: `p18`

Pinned source:

- repository: `FedorMilovanov/Milovi_Cake`;
- commit: `c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370`;
- path: `img/gallery/gallery-18-hd.webp`;
- source Git blob SHA-1: `3574f726b233583a77b8a6db885f91b49e5189d8`;
- source bytes: `195742`;
- source SHA-256: `2fd0336e90d3d42ae70638b33fc51653c14ef3b4c08c1ce6fce7f5c818b65aca`;
- decoded dimensions: `1024x1536`.

Deterministic transport artifact:

- format: JPEG;
- dimensions: `1024x1536`;
- bytes: `580910`;
- SHA-256: `a9730cc62939845c61191f1a375b2bab35800122c968d6cc757f0ae4340771d5`.

Recovered canary evidence digest:
`sha256:d712ca06f2503bbb7e483f6c8d0fe3f0067b37b834536f7f7861bb38415fa580`.

## Live executor

PR #376 merged the exact one-shot canary executor after full CI #4463 succeeded on exact head `f44cce8c42066ac374ed53e79d1d883ef39d3bc0`.

Merge SHA: `f10f16c929b8fee567d05709e05fad18b2a068e5`.

The executor:

1. rejects GitHub workflow reruns before provider access;
2. requires an exact single-file authorization commit;
3. re-proves bot/channel identity before mutation;
4. re-materializes exact source bytes and deterministic JPEG;
5. commits a `dispatch_started` barrier before the provider mutation;
6. calls only one `sendPhoto` with mutation retry count zero;
7. forbids fallback operations and blind replay;
8. accepts success only with exact returned chat/caption/photo and a positive `message_id`.

## First live authorization and provider result

Authorization commit:
`d36d00de883062d0c0ea9b83a9bc1ab163eed54e`

Workflow run:
`31918457764`, attempt 1.

Durable pre-dispatch barrier commit:
`05313dfbf24d87c4215cbd86c1e43e03233b0919`.

The exact `sendPhoto` was dispatched once. Telegram returned a deterministic provider rejection:

`HTTP 403 — Forbidden: bot is not a member of the channel chat`

No positive `message_id` was returned. No retry was performed. The rejected authorization/run must never be rerun.

Canonical state is `canary-dispatch-state.json`, corrected after the provider response in commit `5bb16999bcac57fc3641d90de4e0030826a1518c` to:

- `status=provider_rejected`;
- `provider_effect=rejected_before_message_creation`;
- `message_id=null`;
- `automatic_replay_allowed=false`.

## Only current provider blocker

The exact shared bot `8716602202 / @preaching_mp3_bot` must be added to `@MiloviCake` as a channel administrator with the minimum channel posting privilege (`can_post_messages` / Post Messages).

Do not grant invite-user, add-admin, delete-message, edit-message or other unrelated privileges merely for publishing.

There is no supported Telegram user-session/admin mutation surface in this repository. Bot API `promoteChatMember` cannot bootstrap this state because the calling bot must already be an administrator.

After the channel owner/admin performs that one provider-side membership change:

1. run fresh read-only exact target + `getChatMember` proof;
2. require exact bot id/username, administrator status and `can_post_messages=true`;
3. bind the new proof to current `main`;
4. create a **new** one-canary authorization id and exact parent SHA;
5. dispatch one new zero-retry `sendPhoto`;
6. persist and verify the returned `message_id` before any bootstrap rollout.

The old authorization and run remain terminally rejected and non-replayable.
