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
- Telegram Bot API/TDLib explicitly support bold, italic and blockquote entities.

There is also current evidence of **intermittent ChatGPT Android/web copy and Writing Block regressions in September 2026**. Public OpenAI Developer Community reports describe Android text-selection/copy actions disappearing until the conversation view is refreshed, and Writing Blocks / Copy Response intermittently failing on ChatGPT Web after the September UI changes. These reports do not prove the exact rich-MIME failure seen here, but they make a ChatGPT/client-state regression more plausible than an article-markup error.

Current diagnostic references:

- 2026-09-08: `Android partial text selection intermittently shows only “Select all” — “Copy” missing`.
- 2026-09-20: `Writing Blocks disappear from assistant messages; Copy Response fails`.
- 2026-09-20 OpenAI Support reply on an Android Writing Block/rendering regression recommends checking updates and reporting exact app/Android versions if it persists.

Do not claim a specific Chrome rich-copy regression unless an upstream browser issue reproduces it directly.

## Canonical manual-copy method

Use **ordinary rendered ChatGPT output**. The article must not be supplied as a code block, raw Markdown source, raw HTML, or a visible-symbol workaround such as `>` quote markers or vertical-bar pseudoquotes.

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

Do **not** use the ChatGPT message `Copy` action when it returns Markdown/plain text, a keyboard clipboard-history card, `Paste as plain text`, or an intermediate plain-text editor.

## If the canary suddenly fails although it worked previously

Treat this first as a **client/view/clipboard-state problem**, not as an editorial problem.

Recovery order:

1. Do not keep recopying the long article. Re-test only the canary.
2. Leave the conversation and reopen it once. Current Android reports show that refreshing/resuming a ChatGPT conversation view can restore broken text-selection actions.
3. Force-stop and reopen **Chrome** and **Telegram**.
4. Reopen the conversation and retry direct selection → system Copy → Telegram system Paste.
5. If it still fails, **reboot the phone once**. This resets browser/app processes and Android clipboard-service state. It is a diagnostic reset, not a guaranteed fix.
6. If Chrome still emits plain text, open the same conversation in **Samsung Internet** on Galaxy devices and repeat the canary there. This gives an independent browser/UI path.
7. If available, also test the current **ChatGPT Android app** with the same canary. App/web copy regressions can differ by build.
8. If the canary fails on all current surfaces, manual rich copy is not certified for that session/build. Stop changing the article itself.

## Why yesterday can work and today fail

The article markup can be identical while the clipboard output changes because several independent layers participate: ChatGPT web/app UI, browser/app clipboard serialization, Android/Samsung clipboard infrastructure, keyboard clipboard-history UI, and Telegram rich-paste parsing. A UI rollout, app/browser update or stale view/clipboard state in any layer can turn the same visible rich text into plain text.

Therefore the **same-session canary** is the deterministic preflight.

## 100% reliable publication path

There is no browser-independent way to guarantee that an arbitrary Android UI copy action will preserve rich clipboard MIME data. The transport-guaranteed path is the existing Telegram provider path using explicit Telegram entities / HTML parse mode.

Operational rule:

- **Manual direct copy is allowed only after the canary passes in the same client/session.**
- **If the canary fails, use the existing `video-channel-manager` Telegram publisher rather than degrading the article or adding visible Markdown symbols.**

A future convenience improvement may add a private/staging Telegram preview lane: reviewed HTML is sent by the existing bot to a private preview target, then the editor forwards the already-formatted Telegram message to the public channel. This avoids Android rich-clipboard dependence while preserving manual editorial control. It must reuse the existing bot and target-isolation architecture.

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
