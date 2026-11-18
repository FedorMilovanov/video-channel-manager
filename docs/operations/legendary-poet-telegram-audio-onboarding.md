# The Legendary Poet — Telegram MP3 audio handoff

**Project key:** `legendary-poet`. **Target channel:** `@thelegendarypoet` / https://t.me/thelegendarypoet. **Status:** provider writes **NOT AUTHORIZED**; this document and the generic `sendAudio` transport do not publish anything or prove bot privileges.

## Why this change exists

The owner supplied the exact 187.734792-second, 4,825,010-byte MP3 of M. Yu. Lermontov's 1837 poem «Когда волнуется желтеющая нива…». The full video is already public at https://www.youtube.com/watch?v=dhPngN2CWRw. The channel needs an **audio message** (Telegram Bot API `sendAudio`), not an MP4, a generic document upload, or a text-only announcement.

The new `telegram_multichannel_audio.py` adapter is integrated into the same checked `GenericReleaseQueue`, `GenericPublicationLedger`, `GenericDispatchEnvelope`, exact channel profile + target proof and one-shot mutation transport as existing Telegram media. It does not introduce a second publisher. On unknown provider response, preserve `may_exist` and **never blindly retry**. Exact bytes and text/entity digest are validated before POST.

## Correct local handoff

The canonical operator bundle is the following on the authorized desktop:

```text
C:\Users\Fedor\Projects\video-channel-manager\operator-output\legendary-poet-lermontov-niva-20261118
```

It contains the **unchanged** user-supplied MP3, a 320×320 JPEG thumbnail, reviewed HTML caption, cross-platform copy and `release-manifest.json`. Source file digest: `10cc0f069970a75b49d33a95cf7bf514fc25be3f1069ddf2a5437e2ea090c3e8`. Exact caption and media must be included in the reviewed release; do not use filename-only matching or an unpublished website link as a live claim.

## Required onboarding before the first send

1. Obtain a Telegram bot account that is **administrator with permission to post messages** in the *exact* channel `@thelegendarypoet`. Register its Bot API token through the supported secret manager, never in Git, chat, logs or a committed JSON artifact.
2. Create a reviewed `content/telegram/channels/legendary-poet.json` profile with unique `project_key`, `state_branch`, concurrency group and credential environment names. Start `provider_writes_authorized=false`. Do not invent any `chat_id`, `bot_id` or `bot_username`.
3. Use the repository-owned read-only discovery/binding flow to prove the **actual** `getMe` bot identity, `getChat` channel ID and `getChatMember` bot administrator permissions. Only then create the exact target binding and update the machine-maintained write-authority registry, tests and runbook; never borrow the LordChrist or Milovi Cake bot.
4. Freeze a single `GenericAudioPayload` with `render_audio_payload`: `caption_html`, parsed expected caption/entities, verified MP3 path, SHA-256, size, safe ASCII transfer filename, `title`, `performer`, `duration` and thumbnail JPEG proof. Include it in a release queue. The profile/target binding/release must be reviewed and authorized separately.
5. Run the usual `initialize-ledger`, `prepare`, `send`, and outcome application flow; preserve `dispatching/may_exist` before provider mutation. Verify the returned `sendAudio` receipt with exact chat identity, caption, entities and returned audio. Save **message ID and URL**.
6. Re-read the channel permalink before any retry or cross-post. Never treat an unverified `HTTP 200` or incomplete upload as a verified publication.

## Explicit boundaries

- The audio adapter is reusable, but its presence **does not authorize any existing channel** or activate an independent schedule.
- A private Telegram Desktop login is not a substitute for the Bot API and exact target proof under this runbook.
- The Legendary Poet VK legacy token alias `legendary-poet` remains quarantined (issue #662). No VK reads/writes using that token.
- The Rutube channel (registered ID `74579453`) needs its **own** verified identity, duplicate inventory and upload mechanism.
- YouTube full `dhPngN2CWRw` is already public; YouTube Short `VNRwP99Umjs` is scheduled 2026-11-19 19:00 MSK. Do not re-upload either.
