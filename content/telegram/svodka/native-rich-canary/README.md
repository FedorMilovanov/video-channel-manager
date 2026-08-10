# Svodka native Rich Message canary

This directory is the reviewed, release-independent content package for the one-time manual `sendRichMessage` canary on `@deep_info_life`.

## Safety boundary

- The only write-capable entrypoint is `.github/workflows/svodka-native-rich-message-canary.yml`.
- It is `workflow_dispatch`-only, `main`-only, and requires the exact confirmation `RICH-CANARY:@deep_info_life:ONE-ARTICLE`.
- Repository artifacts do **not** authorize a provider write. The runtime profile gate, both exact-current-main quality runs, fresh exact target proof, same-credential `getMe`, and a remotely persisted one-shot intent are all still required.
- The state file is `content/telegram/svodka/native-rich-message-canary.json` on `state/svodka-telegram`. It is deliberately separate from `publication-ledger.json`.
- Any durable state — including an abandoned `intent`, `not_dispatched`, `confirmed_absent`, or `may_exist` — blocks every second run. `may_exist` means **STOP**.
- The workflow never deletes or edits the canary and never falls back to legacy `sendMessage` after a rich attempt.
- This canary does not modify the frozen pilot release, consume a publication-ledger entry, unlock the legacy scheduler, or count among the 14 pilot posts.

## Article, Agent A bridge, and media registry

The final wiring incorporates Agent A's native rich bridge from PR #294. The reviewed canary is first materialized as its provider-neutral `RichArticleDocument`, validated under the bridge limits, and rendered through `telegram_rich_renderer.render_rich_document()` into the exact `TelegramRichMessageDocument` consumed by `publish_rich_once()`. The durable intent binds both the domain-article digest and render digest. A golden input/expected structure in `canary-spec.json` must exactly match the bridge output, so neither hand-built transport payload drift nor bridge drift can silently publish.

`canary-spec.json` describes a short standalone Svodka article about the total solar eclipse of 12 August 2026. Its heading, formatted lead, list, divider, safety blockquote, compact table, natural angular-size formula, source details block, and two inline images serve the explanation rather than acting as a feature dump.

The final wiring incorporates the provider-ready media work from Agent A's PR #293. It uses that registry's two declared canary assets:

1. the official NASA/SVS totality map;
2. the NASA WB-57 high-altitude research-aircraft photo.

The complete media registry, each selected entry, both exact HTTPS URLs, captions, credits, MIME expectations, `remote_ready`, `acquisition_status`, `provider_upload_status`, and the registry's provider-disabled authorization are digest-bound before intent creation. The workflow also fetches both URLs read-only, requires HTTP 200 plus the exact MIME signature, hashes the bytes into the durable intent, and repeats that proof immediately before mutation; any byte change stops before Telegram. The canary keeps a separate state and publication identity; reusing the editorial sources does not turn it into the pilot article or consume its ledger slot.

Telegram assigns URL-media `file_id`, `file_unique_id`, transfer metadata, and the available `PhotoSize` variants only after fetching the asset. The rich document therefore opts the two reviewed block paths into explicit provider-assigned identity handling. Verification remains exact for:

- the complete reviewed request and both registry-bound media URLs;
- the exact two media block paths and types, captions, credits, and surrounding structure;
- a valid non-empty returned Telegram photo-size collection at each path;
- the complete normalized returned `RichMessage` structure;
- the complete actual returned `RichMessage`, including every Telegram file identity, dimension, and optional field, retained in the provider outcome artifact.

Any missing image, malformed file evidence, wrong media path/type, caption or structural drift, wrong chat, or missing positive message ID becomes `may_exist`, never `verified`. Documents without explicit provider-assigned media paths retain the transport's original full-value exact comparison.

## Future edit test

The spec also carries a separate provider-disabled `editMessageText` review fixture using the Bot API `rich_message` parameter. `svodka_native_rich_canary preview` can materialize it for tests. It has no message ID, no provider adapter, no workflow wiring, and no write authorization. This PR does not execute an edit; a future edit can only be designed from a verified canary outcome under a separate one-shot state machine.

Provider writes performed while preparing this package: **0**.
