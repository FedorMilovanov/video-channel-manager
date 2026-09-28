# Direct ChatGPT → Telegram rich-copy workflow

Status: operational guidance for manually copying reviewed `@lordchrist` article copy from ChatGPT on a phone into Telegram while preserving bold, italic and quote formatting.

This workflow is intentionally separate from the bot/provider publisher. It exists for occasional interactive articles that the editor wants to post manually from the chat.

## What is known

On 2026-09-27, direct Android text selection from the **rendered ChatGPT response** successfully preserved bold, italic and quote formatting when pasted into Telegram. The ChatGPT/message-level `Copy` button was not the successful path. Blank paragraph spacing needed separate attention.

On 2026-09-28, the same general workflow on Android produced plain text in repeated tests. Programmatic clipboard experiments from a ChatGPT-hosted HTML artifact also produced plain text. Therefore rich clipboard transport must be treated as a client/browser capability, not as an invariant property of the article.

Telegram Android itself supports rich paste when the Android clipboard item contains `text/html`: its composer checks for the `text/html` MIME type, parses the HTML, and converts supported tags including `blockquote` into Telegram text entities. Therefore a plain-text result can occur **before** Telegram, when the source/browser/clipboard path fails to preserve the HTML clipboard flavour.

Relevant implementation references:

- Telegram Android `EditTextCaption.onTextContextMenuItem`: rich paste path requires `text/html` and calls `CopyUtilities.fromHTML`.
- Telegram Android `CopyUtilities`: converts bold/italic styles and `blockquote` into Telegram entities.
- Web-platform clipboard compatibility tables show current Chromium and Samsung Internet support for `text/html`, but support does not guarantee that every UI copy action emits rich HTML.

## Canonical manual-copy method

Use **ordinary rendered ChatGPT output**. The article must not be supplied as:

- a code block;
- raw Markdown source;
- raw HTML;
- a visible-symbol workaround such as `>` quote markers or vertical-bar pseudoquotes.

The response should visibly contain real bold, italic and block quotes before copying.

### Step 1 — run the canary first

Before copying a long article, copy this small rendered test from the same ChatGPT conversation and paste it into **Telegram Saved Messages**:

**Жирный текст**

> Настоящая цитата
>
> *Курсив внутри цитаты*

Обычный абзац.

Pass condition: Telegram composer visibly shows bold + quote block + italic **before sending**.

Fail condition: all text is plain, or literal Markdown punctuation (`>`, `*`, `**`) appears.

Do not copy the full article until the canary passes.

### Step 2 — direct selection, not message Copy

When the canary passes:

1. Long-press inside the rendered assistant response.
2. Expand the Android selection handles over the article body.
3. Use the **system selection `Copy` command**.
4. Switch directly to Telegram.
5. Long-press the Telegram composer and choose **Paste**.

Do **not** use:

- the ChatGPT message `Copy` icon/action if it returns Markdown or plain text;
- a keyboard clipboard-history card as the insertion method, because clipboard-history UIs may retain only the plain-text representation;
- `Paste as plain text`;
- an intermediate plain-text editor.

### Step 3 — preserve paragraph spacing

Prefer genuine blank paragraphs in the rendered response. If a particular client collapses empty lines while still preserving rich formatting, a dedicated invisible spacer may be used only as a transport-level workaround and only after confirming it is invisible in Telegram. Do not put visible pseudoformatting symbols into the article.

## If the canary suddenly fails although it worked previously

Treat this first as a browser/clipboard-state problem, not as an editorial problem.

Use this recovery order:

1. **Do not keep recopying the long article.** Re-test only the canary.
2. Clear the current clipboard history entry if convenient; then copy the canary afresh.
3. Force-stop and reopen **Chrome** and **Telegram**.
4. Reopen the ChatGPT conversation and retry direct selection → system Copy → Telegram system Paste.
5. If it still fails, reboot the phone once. This resets the browser/app processes and Android clipboard service state; it is a diagnostic reset, not a guaranteed fix.
6. If Chrome still emits plain text, open the same ChatGPT conversation in **Samsung Internet** (on Galaxy devices) and repeat the canary there. Modern Samsung Internet supports `text/html` clipboard data and is a useful independent Chromium implementation path.
7. If the canary fails in both browsers, manual rich copy is not certified for that current client/build/session. Stop troubleshooting the article itself.

## Why yesterday can work and today fail

The article markup can be identical while the clipboard output changes because several independent layers participate:

1. ChatGPT web UI decides what the rendered DOM and message Copy action expose.
2. The browser decides which clipboard MIME flavours are emitted by the copy action.
3. Android/Samsung clipboard infrastructure stores the clip.
4. A keyboard clipboard-history UI may re-insert only `text/plain`.
5. Telegram decides whether the incoming clip has `text/html` and converts it to entities.

A change or stale state in any layer can turn the same visible rich text into plain text. Therefore the **same-session canary** is the deterministic preflight.

Chrome 153 entered the September 2026 release cycle and Android regressions have occurred in that release family in unrelated areas. There is not currently enough evidence to claim a confirmed Chrome-153 rich-copy regression specifically. Do not write such a claim into user-facing copy without a reproducible upstream bug.

## 100% reliable publication path

There is no browser-independent way to guarantee that an arbitrary Android UI copy action will preserve rich clipboard MIME data. Therefore the only publication path that can be treated as transport-guaranteed is the existing Telegram provider path using explicit Telegram entities / HTML parse mode.

Operational rule:

- **Manual direct copy is allowed only after the canary passes in the same client/session.**
- **If the canary fails, use the existing `video-channel-manager` Telegram publisher rather than degrading the article or adding visible Markdown symbols.**

This keeps manual posting convenient when the device supports it while retaining a deterministic fallback when the Android clipboard path regresses.

## Article-output contract for ChatGPT

When the user asks for a manually copyable Telegram article:

- return one clean rendered article;
- no explanatory prose inside the copyable article;
- no raw URLs unless editorially required;
- real block quotes for exact quotations;
- restrained bold/italic;
- normal multi-sentence paragraphs;
- no slogan ladder;
- no visible Markdown/HTML syntax;
- historical quotations must be primary-source verified under `RICH_EDITORIAL_STANDARD.md`.

Before a long manual post, the assistant may provide the small canary separately if the user reports clipboard instability.
