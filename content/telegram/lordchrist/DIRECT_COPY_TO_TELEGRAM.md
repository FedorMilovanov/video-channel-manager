# Direct ChatGPT → Telegram rich-copy workflow

Status: operational guidance for manually copying reviewed `@lordchrist` article copy from ChatGPT on a phone into Telegram while preserving bold, italic and quote formatting.

This workflow is intentionally separate from the bot/provider publisher. It exists for occasional interactive articles that the editor wants to post manually from the chat.

## Verified working path on Android

Confirmed on 2026-09-28: the same clipboard entry can paste differently depending on **how Telegram inserts it**.

The working path is:

1. Copy the rendered rich text from ChatGPT.
2. Open the Telegram composer.
3. **Long-press inside the Telegram text field until the Android context menu appears.**
4. Tap the system **Paste / «Вставить»** command from that context menu.

This preserves the rich payload and Telegram converts it into its own text entities: bold, italic and block quotes.

The non-working path is:

- tapping a clipboard suggestion / clipboard-history item in the **keyboard toolbar or keyboard clipboard panel**.

That path inserts the `text/plain` representation and strips rich formatting.

Therefore, for `@lordchrist`, **system long-press Paste inside the Telegram composer is the canonical manual insertion method. Keyboard clipboard insertion is forbidden for rich posts.**

This resolves the 2026-09-28 apparent regression: the clipboard itself could contain the needed rich representation, but the keyboard clipboard UI was reinserting only plain text.

## What is known

On 2026-09-27, direct Android text selection from the **rendered ChatGPT response** successfully preserved bold, italic and quote formatting when pasted into Telegram. Blank paragraph spacing needed separate attention.

On 2026-09-28, repeated tests initially looked like a rich-copy failure because insertion was being performed from the keyboard clipboard UI. After switching to a long press in the Telegram composer and choosing the system **Paste** command, formatting was preserved again.

Telegram Android itself supports rich paste when the Android clipboard item contains `text/html`: its composer checks for the `text/html` MIME type, parses the HTML, and converts supported tags including `blockquote` into Telegram text entities.

Relevant implementation references:

- Telegram Android `EditTextCaption.onTextContextMenuItem`: rich paste path requires `text/html` and calls `CopyUtilities.fromHTML`.
- Telegram Android `CopyUtilities`: converts bold/italic styles and `blockquote` into Telegram entities.
- Telegram Bot API/TDLib explicitly support bold, italic and blockquote entities.

## Canonical manual-copy method

Use **ordinary rendered ChatGPT output**. The article must not be supplied as a code block, raw Markdown source, raw HTML, or a visible-symbol workaround such as `>` quote markers or vertical-bar pseudoquotes.

The response should visibly contain real bold, italic and block quotes before copying.

### Step 1 — run a small canary when needed

Before copying a long article after any client/app update, test this rendered sample:

**Жирный текст**

> Настоящая цитата
>
> *Курсив внутри цитаты*

Обычный абзац.

Pass condition: after **long-press → Paste** in Telegram, the composer visibly shows bold + quote block + italic before sending.

Fail condition: all text is plain, or literal Markdown punctuation (`>`, `*`, `**`) appears.

### Step 2 — copy from ChatGPT

Preferred path:

1. Long-press inside the rendered assistant response.
2. Expand the Android selection handles over the article body.
3. Use the system selection **Copy** command.
4. Switch directly to Telegram.

A ChatGPT-level Copy action may be used only if a canary proves that it preserves rich clipboard data in the current client. If it produces Markdown/plain text, do not use it for publishing.

### Step 3 — paste into Telegram correctly

1. Tap the Telegram composer.
2. **Long-press inside the composer itself.**
3. Wait for the Android text context menu.
4. Tap **Paste / «Вставить»** there.
5. Verify formatting in the composer before sending.

Do **not** paste a rich article by tapping:

- a keyboard clipboard-history item;
- a keyboard clipboard suggestion chip;
- a `Paste as plain text` action;
- an intermediate plain-text editor.

Those paths can discard the HTML/styled clipboard representation even when the system clipboard still contains it.

## Why the two paste actions behave differently

Android clipboard items can carry more than one representation, for example `text/plain` plus `text/html` or styled spans. The Telegram editor's own paste handler can inspect and parse the rich representation when invoked through the normal text-field paste action.

A keyboard clipboard manager, however, is a separate application layer. It may cache or insert only the plain-text representation. In that case Telegram receives already-flattened text and has no rich entities left to recover.

So the rule is about the **insertion path**, not merely the clipboard contents:

- **Telegram text field → long-press → Paste = rich path**;
- **keyboard clipboard panel → tap item = plain-text path**.

## If rich paste later fails even with long-press Paste

Treat that as a real client/clipboard-state issue and use this recovery order:

1. Re-test only the small canary.
2. Leave and reopen the ChatGPT conversation.
3. Force-stop and reopen Chrome/ChatGPT and Telegram.
4. Retry copy → Telegram composer → long-press → Paste.
5. Reboot the phone once if needed.
6. Try Samsung Internet or the ChatGPT Android app as an alternate source surface.
7. If the canary still fails through the canonical long-press Paste path, use the existing `video-channel-manager` Telegram publisher with explicit HTML/entities.

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

## Operational rule

For manual rich posting from Android, the canonical sequence is now:

**Rendered ChatGPT text → Copy → Telegram composer → long-press → system Paste.**

Never use the keyboard clipboard panel for rich articles.
