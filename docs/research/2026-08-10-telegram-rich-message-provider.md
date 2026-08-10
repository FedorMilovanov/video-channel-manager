# Telegram Rich Message provider transport review

Date: 2026-08-10
Repository: `FedorMilovanov/video-channel-manager`
Initial fetched base: `origin/main` at `8eb584e19f7ba7c8cb78f5b9121cb312ac13bd06`
Final reconciled base: `origin/main` at `5aa3e0aeed561bc710c847e15be24ee363f50a7d`
Provider writes performed for this change: **0**

## Scope

This change adds an isolated `sendRichMessage` transport in
`src/video_channel_manager/telegram_rich_provider.py`. It does not connect that
transport to a live workflow, does not add or modify workflow triggers, and
does not modify either Svodka's durable state branch or the existing shared
`sendMessage` implementation.

The eventual target can be bound to `@deep_info_life`, chat
`-1003527567039`, bot `8716602202 / @preaching_mp3_bot`, profile
`sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9`,
and target binding
`sha256:d95113f19ef340587653e45ba25c01ccdcc8d6aefedc32043c61a4c4db6e6a63`
by a future reviewed rich document. This PR does not authorize or perform that
rollout.

## Official Bot API facts rechecked

Primary sources checked on 2026-08-10:

- Telegram Bot API: <https://core.telegram.org/bots/api>
- Telegram Bot API changelog: <https://core.telegram.org/bots/api-changelog>

The latest documented Rich Message changes are Bot API 10.1 (2026-06-11) and
10.2 (2026-07-14):

- `sendRichMessage` accepts exact `chat_id` and one `InputRichMessage` and, on
  success, returns a `Message`;
- exactly one of `InputRichMessage.html`, `.markdown`, or `.blocks` is used;
- Bot API 10.2 added explicit `InputRichMessage.media` and block-form rich
  input;
- a returned `Message` may carry `rich_message: RichMessage`;
- `RichMessage` contains parsed `blocks` and optional `is_rtl`;
- returned rich media blocks expose Bot API media objects. Those objects can
  include provider identifiers such as `file_id` and `file_unique_id`.

## What the response can and cannot prove

A successful HTTP response alone is not publication verification.

The transport marks `verified` only when all of the following hold:

1. the rich target embeds the complete read-only `TelegramTargetBinding`, its
   digest is recomputed, the exact runtime `TelegramChannelProfile` matches and
   has its provider-write gate enabled, a fresh `GenericTargetProof` exactly
   matches project, profile, channel id/username/type, bot id/username and
   posting permission, and read-only `getMe` using the same credential selected
   for the mutation resolves to that exact bot;
2. exactly one `sendRichMessage` mutation request was made;
3. the returned `Message.chat` exactly matches the expected numeric channel,
   username, and `type=channel`;
4. a positive `message_id` is present;
5. `Message.rich_message` is present as a complete object with blocks;
6. the canonical SHA-256 of the complete returned `RichMessage` equals the
   reviewed expected-return structure digest;
7. the canonical digest of every recursively returned media block, including
   its location, type, and returned media object, equals the expected media
   digest.

The full exact comparison is intentionally conservative. Block-specific
required fields, nesting, list labels, table cells, map bounds, captions and
media object identity are validated against the reviewed Bot API contract.
Optional fields, media identifiers, ordering, or any other returned structure
drift produce `may_exist`, not `verified`. The archived outcome also carries
the explicit expected chat/bot identities, target-binding digest, and exact
fresh target-proof digest instead of relying on an opaque document hash alone.

The Bot API response does **not** echo:

- the original input HTML or Markdown source;
- every input-only parsing choice, such as the source representation itself;
- authenticated bot credentials/identity in the returned `Message`;
- client-specific visual rendering beyond the returned `RichMessage` model.

Therefore bot identity evidence comes from both the fresh exact target proof
and a bounded read-only `getMe` made with the same credential object immediately
before dispatch; a mismatch or unavailable identity prevents the mutation.
Semantic structure evidence still comes only from `Message.rich_message`. If
Telegram omits or partially returns that structure, the outcome is `may_exist`;
the transport does not pretend that rich semantics were verified.

## Failure/effect model

The archived evidence distinguishes:

- `impossible`: an exact local target/bot/freshness precondition failed; no
  provider method was called;
- `not_dispatched`: the provider transport proves timeout/failure before an
  HTTP mutation request started;
- `confirmed_absent`: Telegram returned an explicit trusted non-5xx rejection;
- `may_exist`: a request may have reached Telegram but response evidence is
  unavailable, malformed, incomplete, wrong-target, missing `message_id`, or
  mismatched in structure/media; 5xx results are also conservative
  `may_exist`;
- `verified`: exact target, positive `message_id`, complete rich structure, and
  media all match the reviewed document.

All outcomes set `automatic_retry_allowed=false`. A rich error never triggers
an automatic `sendMessage` fallback because that would be a second mutation
with possible duplication. The old `GenericMessagePayload` is retained in the
rich document as an optional exact fallback and remains executable through the
unchanged shared `send_message_once` path only when selected **before** any
provider mutation under a separate reviewed dispatch.

## Archival ordering

`publish_rich_once` performs these phases in order:

1. fail-closed local binding/write-gate/freshness checks;
2. one bounded read-only same-credential `getMe` identity check;
3. at most one provider mutation request with explicit connect/read/write/pool
   timeouts and transport retries fixed to zero;
4. construct exact canonical provider-outcome bytes;
5. require a durable archive receipt bound to those bytes by SHA-256;
6. only then invoke an optional state-mutation callback.

An archive failure or digest mismatch blocks state mutation. Non-verified
outcomes may preserve an observed message id only as reconciliation evidence;
`message_id` and canonical public URL fields are reserved for `verified`.

## Fallback and rollout boundary

The existing `telegram_multichannel_transport.send_message_once` path is not
rewritten. Rich transport selection must happen before dispatch. There is no
same-attempt fallback and no blind retry.

## Follow-up: explicit URL-media evidence for the manual canary

The later manual Svodka canary keeps the default full-byte-equivalent RichMessage
comparison for ordinary documents. It adds one narrowly opted-in mechanism for
URL media whose `file_id`, `file_unique_id`, and optional transfer metadata do
not exist before Telegram fetches the reviewed URL:

- each opted-in media block is named by its exact recursive block path;
- the request document and exact reviewed URLs remain fully hashed; the canary
  additionally records fresh byte-level SHA-256 proofs and requires an identical
  read-only re-fetch immediately before mutation;
- returned media must still be valid, non-empty Bot API media at the exact path
  and type, with the exact caption and surrounding structure expected by the
  reviewed document;
- only the provider-generated `PhotoSize` variants (including their opaque
  identities, dimensions/count, and optional transfer metadata) are
  canonicalized for the expected-vs-returned digest, because none exist until
  Telegram fetches URL media;
- the complete actual returned `RichMessage`, including Telegram file
  identities, is retained in the exact provider outcome artifact.

This is not a wildcard for missing or misplaced media. Missing media, malformed
or empty file evidence, wrong media path/type, caption or optional structural
changes, or any other non-reviewed drift remains `may_exist`. The complete raw
returned file identities, variants and dimensions remain in the archived
provider outcome. Documents that do not explicitly list provider-assigned media
paths retain the original full exact comparison.
