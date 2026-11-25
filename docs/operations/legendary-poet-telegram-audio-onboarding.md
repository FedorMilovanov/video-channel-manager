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

It contains the **unchanged** user-supplied MP3, a 320×320 JPEG thumbnail, reviewed HTML caption, cross-platform copy and `release-manifest.json`. Source file digest: `10cc0f069970a75b49d33a95cf7bf514fc25be3f1069ddf2a5437e2ea090c3e8`. Exact caption and media must be included in the reviewed release; do not use filename-only matching or an unpublished website link as a live claim. This historical Windows handoff was not re-opened by the technical checkpoint below.

## Provider-free source decode — 23 November 2026 Moscow time

At 22 November 23:31 UTC, the [source-only checkpoint](https://github.com/FedorMilovanov/video-channel-manager/issues/1036#issuecomment-7087633303) revalidated 4,825,010 bytes from Git blob `9da6847c5ee5008981fa154b1b95d87d6809cf01` at `FedorMilovanov/TheLegendaryPoet@7d041a174c34325ac003bfde1c78903b5dff1e58`: the MP3 SHA-256 remains `10cc0f069970a75b49d33a95cf7bf514fc25be3f1069ddf2a5437e2ea090c3e8`. This is a pinned Git source, not a fresh production-HTTP or Windows-bundle check.

FFmpeg 7.0.2-static, extracted from the PyPI `imageio-ffmpeg` 0.6.0 wheel, fully decoded the first audio stream with `-xerror` and local `file,pipe` protocol restriction. The decode exited zero; a separate PCM pass emitted no stderr errors. The resulting 48 kHz stereo `pcm_s16le` stream contained **9,011,270 stereo sample frames**, or **187.7347917 seconds**; its SHA-256 was `f5626af91887032d79c9c1fc30d53a5b248a9b8fd8eff13a5c8c33176c85b818`. That PCM hash describes this particular decoder output, not a new master. FFmpeg's rounded container duration of 187.78 seconds and the earlier Mutagen estimate of 187.776 seconds are different measurements, not evidence of a different MP3.

`volumedetect` reported a mean of −16.2 dB and a rounded maximum of 0.0 dB; one of 18,022,540 quantized 16-bit samples reached negative full scale. These numbers **do not prove audible clipping or its absence**, listening quality, editorial acceptance, rights, release approval or duplicate absence. The extracted decoder binary SHA-256 was `e7e7fb30477f717e6f55f9180a70386c62677ef8a4d4d1a5d948f4098aa3eb99`; source and decoder were temporary `/tmp` copies, not the owner's handoff.

The exact MP3's editable ID3v2.3 `WOAS` and `COMM::eng` refer to Suno song `246e82d9-16a8-4ddb-875d-24ba9c065019`. An [unmerged website research ledger](https://github.com/FedorMilovanov/TheLegendaryPoet/blob/f1424c6326734775ff19ed9810ed915ab7cad792/docs/research/LERMONTOV_NIVA_SOURCE_LEDGER_2026-11-18.md) instead names `24fab091-1baf-46f9-bed0-8ddbe0af5be7` as variant 1. **The relation between these IDs is unverified**: neither metadata nor that draft proves different audio, current release status, the correct source ID or rights. The ID3 comment calls it a working test, but that historical label is not a live status determination. No Suno request was made. Reconcile the exact master's provenance and rights with the owner; do not rewrite tags or replace the accepted MP3 SHA to make the identifiers match.

The separate 22,308-byte candidate JPEG was previously identified by SHA-256 `6be386a116c9564ee1c09c6f7c5a385c324e00ed86753782cea24f389f43cfd4`. The MP3's embedded cover has a different SHA-256 and must not be substituted. No blob of the candidate's exact length appeared in the pinned website tree or `video-channel-manager@aa9cf9ef10b2dcae54f9eeee1cc9b8676b39ad17`; this limited Git-tree check says nothing conclusive about other commits or the owner's Windows bundle.

Independent human listening and editorial/rights review, an exact JPEG and caption check, complete duplicate reconciliation, fresh target proof and a separately authorized release/intent/execution remain required. The historical 19 November proposed slot has expired. This checkpoint performed no `sendAudio` and grants no provider authority.

## Shared-bot onboarding verified — 18 November 2026 (Issue #1036)

**Use the existing shared bot.** The production account is `@preaching_mp3_bot` (ID `8716602202`), intentionally reused by `@lordchrist`, `@deep_info_life`, `@MiloviCake` and this newly registered channel. Do not create another bot, copy a new token or treat the legacy secret name as a target selector. The existing MP3Bot `BOT_TOKEN` was checked in memory without printing/copying it; its bot ID matches.

**Exact destination confirmed by the repository-owned read-only discovery CLI on current main:** `@thelegendarypoet`, numeric chat ID `-1003345085810`, bot `@preaching_mp3_bot`, `administrator`, `can_post_messages=true`. The checks were `getMe`, `getChat(public)`, `getChat(numeric)`, `getChatMember`. No Telegram write request occurred. The proof is archived outside Git under `operator-output/legendary-poet-telegram-discovery-20261118/legendary-poet-target-proof-readonly.json`, and the canonical, verified non-secret binding is `content/telegram/channels/legendary-poet-target-binding.json`.

**Separate channel profile:** `content/telegram/channels/legendary-poet.json` uses `project_key=legendary-poet`, distinct prefix, `state/legendary-poet-telegram`, concurrency group, and `LEGENDARY_POET_TELEGRAM_*` names. The shared token can be mapped into that profile's environment from approved secret storage (including the existing historical LordChrist secret); it must never be committed, pasted into commands or exposed in logs. The `state/` ref is reserved/protected but is not yet initialized with an authorized release. The profile remains **`provider_writes_authorized=false`** and the live per-profile truth is `docs/operations/channel-write-authority.json`.

**Transport boundary:** discovery succeeded through the generic Telegram Bot API read-only transport without restarting, logging out or changing MP3Bot's separate Local Bot API runtime. The 4.8 MB audio does not justify changing the working bot server. A fresh exact-target preflight is required immediately before any future send.

### Operator experience and single owner instruction

The owner's explicit instruction to publish an exact MP3 to this channel is the
business authorization for that operation, not a request to manually calculate
hashes, set internal flags or approve the same unchanged operation repeatedly.
The operator must capture the instruction once with the exact selected master,
caption/artwork, channel and requested timing; derive the internal release,
intent and receipts using the existing reviewed runtime. A materially different
asset, caption, target, timing or previously uncertain effect is a different
decision. Never manufacture independent rights/editorial evidence or resolve
historical duplicate uncertainty by assumption.

The current implementation is incomplete: this profile remains disabled and
the protected channel state is not initialized. The 25 November Yesenin Steel
Blizzard owner request in [#1036](https://github.com/FedorMilovanov/video-channel-manager/issues/1036#issuecomment-7163639718)
is distinct from the historical Lermontov candidate above; do not apply the
old media or caption to it. The remaining engineering scope is one canonical
operator entrypoint, safe protected state initialization/migration, channel-wide
duplicate and unresolved-effect checks across releases, automatic durable
intent and result persistence, and no-replay reconciliation. The owner need
not manipulate those artifacts. A network timeout is a transport diagnosis,
not a reason to demand the same authorization again. A verified connection
failure before dispatch can resume the same authorized intent through the
existing outcome state machine; ambiguous dispatch cannot be blindly repeated.

The generic `prepare --binding` route performs fresh exact-target preflight
inside preparation for an already authorized release/profile; it replaces
the separate proof-file creation and handoff, without a second preflight.
Existing `--target-proof` workflows remain compatible. It is not a publisher,
does not enable a disabled channel, and is only the first orchestration step.

The existing `send-once` command consumes the exact persisted intent using an
exclusive claim beside the canonical resolved ledger before provider dispatch.
The claim is retained across process interruption, and the outcome is written
atomically. A second invocation with a different output path cannot replay
that intent on the same ledger. A claim without an outcome requires read-only
reconciliation; never delete it to force a retry. This local protection does
not establish cross-host or cross-release duplicate coverage and does not
replace the protected channel state, serialization or exact provider receipt.

### Required checks before the first audio post

1. Revalidate the registered profile and the pinned target binding on exact current `main`, including any concurrent edits and write-authority registry.
2. Freeze one exact `GenericAudioPayload` with unmodified MP3 SHA-256/bytes, proven thumbnail, title/performer/duration, verified HTML caption and UTF-16 entities; do not claim the site URL works until HTTP 200 is confirmed.
3. Separately review/authorize the immutable `GenericReleaseQueue`, initialize the dedicated state ledger and obtain an operation-specific execution gate. This discovery itself is **not** authority to post.
4. Use only the current-main `telegram_multichannel_cli` workflow `initialize-ledger → prepare → verify-intent → send-once → apply-outcome`, recording durable intent before `sendAudio`. A possible remote effect `may_exist` blocks any blind repeat.
5. Verify the exact returned numeric chat ID, actual MP3, caption/entities, positive message ID and permalink `https://t.me/thelegendarypoet/<message_id>`; store the immutable receipt before reporting success.

Until that exact verified receipt exists, the state is **target binding verified, audio publication not dispatched**.

## Explicit boundaries

- The audio adapter is reusable and the shared posting bot is intentional; neither their presence nor the new binding authorizes a send or activates a schedule.
- A private Telegram Desktop login is not a substitute for the Bot API and exact target proof under this runbook.
- The Legendary Poet VK legacy token alias `legendary-poet` remains quarantined (issue #662). No VK reads/writes using that token.
- The Rutube channel (registered ID `74579453`) needs its **own** verified identity, duplicate inventory and upload mechanism.
- YouTube full `dhPngN2CWRw` is already public; YouTube Short `VNRwP99Umjs` is scheduled 2026-11-19 19:00 MSK. Do not re-upload either.
