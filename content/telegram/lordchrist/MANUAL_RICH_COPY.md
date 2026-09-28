# @lordchrist manual rich-copy handoff

Status: operator/editor handoff contract for occasions when an article is drafted in ChatGPT or another editor and the operator wants to paste it manually into Telegram rather than execute the repository publisher.

This document does **not** authorize a provider write. It defines how to preserve formatting when manual copy/paste is chosen and how to diagnose failures without corrupting the article or falling back to visible Markdown symbols.

## Important distinction

There are two different goals:

1. **Convenient direct copy from a chat/editor into Telegram.** This depends on the source surface, browser/app, Android clipboard MIME payload and Telegram client. It is therefore a best-effort transport unless the clipboard is explicitly verified.
2. **Guaranteed Telegram formatting.** The deterministic path is the existing Telegram provider flow using the reviewed HTML payload and Telegram entities/`parse_mode=HTML`; it does not depend on Android clipboard behavior.

Never claim that a browser clipboard route is 100% reliable across Android clients merely because it worked on a previous day or device.

## Why formatting can disappear

Telegram for Android can preserve pasted rich text when the Android clipboard contains an HTML representation (`text/html`). Android's clipboard model supports a clip containing both plain text and HTML. Chromium also supports writing `text/html` through the Clipboard API.

Formatting is lost when any upstream surface writes only `text/plain`, strips the HTML representation, or runs in a restricted/sandboxed context that cannot perform the rich clipboard write. In that case Telegram receives ordinary characters and cannot infer which words were bold, italic or block quotations.

Do not confuse this with Markdown parsing. Telegram does not turn literal ChatGPT Markdown such as `**bold**`, `*italic*` or `> quote` into rich formatting merely because it was pasted.

## Fast isolation test

When formatting unexpectedly stops working, do not rewrite the article. Isolate the transport in this order:

1. Copy a tiny known-rich sample containing **bold**, *italic* and a block quote from a known-good HTTPS rich-text source and paste it directly into Telegram's composer.
2. Paste with Telegram's normal system **Paste** action. Do not use keyboard clipboard history, "paste as plain text", a notes intermediate, or any clipboard-cleaner utility.
3. If the known-good sample also arrives as plain text, the problem is below ChatGPT: restart/force-stop the browser and Telegram, then reboot Android once and retest. A reboot is a reasonable recovery step because it resets the browser/app processes and clipboard service state, but it is not a proof or permanent fix.
4. If the known-good sample retains formatting but ChatGPT output does not, treat the ChatGPT/mobile-web copy surface as the failing layer. Reopening the conversation, switching between the ChatGPT app and a top-level Chrome/Brave page, or retrying after an app/browser update may restore it. Do **not** clear Telegram data or credentials merely to repair formatting.
5. If behavior changes from one day to the next without an OS change, prefer a client/UI regression hypothesis over changing the article format. Record browser/app versions and the exact copy action that succeeded or failed.

The acceptance probe is visual: before posting to the channel, paste into Saved Messages and verify one bold span, one italic span and one real Telegram quotation block. If any of the three is missing, the manual rich-copy handoff has failed.

## Repository-owned reliable manual helper

If manual chat-to-Telegram posting is a recurring workflow, the repository should own a **top-level HTTPS rich-copy helper**, not a downloaded/sandboxed HTML attachment.

Required properties:

- served as a normal top-level HTTPS page, not `file:`, `data:`, a ChatGPT attachment preview, or a sandboxed iframe;
- accepts raw Markdown or reviewed Telegram HTML as input;
- normalizes output to Telegram-supported constructs only;
- writes one clipboard item containing both `text/plain` and `text/html` from an explicit user click;
- uses the Async Clipboard API when available and reports a hard failure instead of silently claiming rich copy succeeded;
- includes a small test payload and an operator-visible success/failure state;
- never sends the article text to a third-party service;
- never performs a Telegram provider mutation itself;
- the operator still verifies the Saved Messages acceptance probe before channel publication.

A third-party converter may be used temporarily as a diagnostic reference, but it is not the durable project contract. The durable implementation belongs in this repository and should be deployed only through an explicitly reviewed hosting path.

## Copy-ready article contract

When an article is intended for manual rich copy from ChatGPT/editor:

- deliver one clean article, not commentary plus article in the same selectable block;
- no code fence around the article;
- no literal Markdown control characters intended to remain visible in Telegram;
- real paragraph spacing is preserved;
- use bold and italics sparingly;
- block quotations are reserved for Scripture or exact primary-source quotations;
- the article must still read correctly as plain text if styling is removed;
- stay below the Telegram message limit with safety margin after formatting is parsed;
- primary-source quotations follow `RICH_EDITORIAL_STANDARD.md` and must remain contiguous and verifiable.

## Failure policy

If the manual rich-copy acceptance probe fails twice on the same client/session, stop experimenting with the article text. Formatting transport and editorial content are separate concerns.

Choose one of these paths instead:

- recover the client/browser rich clipboard path using the isolation test above;
- use the repository-owned top-level HTTPS rich-copy helper once it is deployed;
- use the reviewed Telegram provider path for deterministic formatting.

Do not insert visible `>`, `*`, `_`, pseudo-quote bars, Unicode box characters or similar workarounds merely to imitate formatting. Those are presentation defects, not a fix for a broken rich clipboard.
