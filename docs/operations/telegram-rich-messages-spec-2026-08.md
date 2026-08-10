# Telegram Rich Messages — Verified Technical Specification

**Document:** `docs/operations/telegram-rich-messages-spec-2026-08.md`  
**Status:** VERIFIED — based on official Bot API docs  
**Base SHA:** `8eb584e19f7ba7c8cb78f5b9121cb312ac13bd06`  
**Date:** 2026-08-10  
**Bot API Version:** 10.2 (2026-07-14)  
**Project:** Svodka / @deep_info_life  
**Scope:** Architecture research — NO provider/publisher writes

---

## 1. Overview

Telegram Rich Messages (Bot API 10.1+, June 11, 2026) enable bots to send highly structured content with native rendering of headings, tables, lists, block quotes, collapsible sections, math formulas, media blocks, collages, slideshows, and more.

**Key endpoint:** `sendRichMessage`  
**Draft streaming:** `sendRichMessageDraft` (private chats only)  
**Editing:** `editMessageText` with `rich_message` parameter

---

## 2. Bot API Methods

### 2.1 sendRichMessage

**Official:** YES — Bot API 10.1 (June 11, 2026)

**Purpose:** Send a rich formatted message.

**Parameters:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `business_connection_id` | String | Optional | For business accounts |
| `chat_id` | Integer/String | **Yes** | User, bot, supergroup, or channel (`@username`) |
| `message_thread_id` | Integer | Optional | Forum topic ID |
| `direct_messages_topic_id` | Integer | Optional | DM topic (required for DM chats) |
| `rich_message` | InputRichMessage | **Yes** | The message content |
| `disable_notification` | Boolean | Optional | Silent delivery |
| `protect_content` | Boolean | Optional | Prevent forward/save |
| `allow_paid_broadcast` | Boolean | Optional | 1000 msg/sec for 0.1 Stars each |
| `message_effect_id` | String | Optional | Private chats only |
| `suggested_post_parameters` | Object | Optional | DM chats only |
| `reply_parameters` | Object | Optional | Reply to message |
| `reply_markup` | Object | Optional | Keyboard markup |

**Return:** `Message` object (with `rich_message` field if rich-formatted)

**Media requirement:** If message contains a block with media, bot must have rights to send that media type to the chat.

---

### 2.2 sendRichMessageDraft

**Official:** YES — Bot API 10.1 (June 11, 2026)

**Purpose:** Stream partial rich message (ephemeral preview, 30 seconds).

**Parameters:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `chat_id` | Integer | **Yes** | Private chat only |
| `message_thread_id` | Integer | Optional | Forum topic |
| `draft_id` | Integer | **Yes** | Non-zero; animated changes |
| `rich_message` | InputRichMessage | **Yes** | Partial content |

**Return:** `True` on success

**Limitation:** Direct upload of new files NOT supported in drafts.

**Persistence requirement:** Must call `sendRichMessage` with complete message to persist. Draft is ephemeral.

---

### 2.3 editMessageText (with rich_message)

**Official:** YES — Bot API 10.1 (June 11, 2026)

**Purpose:** Edit text, rich, or game messages.

**Key parameters:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `chat_id` | Integer/String | Optional | Required if `inline_message_id` not set |
| `message_id` | Integer | Optional | Required if `inline_message_id` not set |
| `inline_message_id` | String | Optional | For inline messages |
| `text` | String | Optional | 1-4096 chars; required if `rich_message` not set |
| `rich_message` | InputRichMessage | Optional | Required if `text` not set |
| `reply_markup` | Object | Optional | Inline keyboard |

**Important:** `text` and `rich_message` are MUTUALLY EXCLUSIVE — exactly one required.

**Restriction:** When editing inline messages, new file upload not supported — use `file_id` or URL.

**No dedicated `editRichMessage` method exists.** Rich messages are edited via `editMessageText` with `rich_message` parameter.

---

## 3. InputRichMessage — The Rich Document Object

**Official:** YES — Bot API 10.1/10.2

**Exactly ONE of these fields must be used:**

| Field | Type | Description |
|-------|------|-------------|
| `html` | String | Rich HTML formatting |
| `markdown` | String | Rich Markdown formatting |
| `blocks` | Array of InputRichBlock | Explicit block structure (Bot API 10.2+) |

**Optional fields:**

| Field | Type | Description |
|-------|------|-------------|
| `media` | Array of InputRichMessageMedia | Media for `tg://photo?id=`, `tg://video?id=`, `tg://audio?id=` links (Bot API 10.2+) |
| `is_rtl` | Boolean | Right-to-left display |
| `skip_entity_detection` | Boolean | Skip auto-detection of URLs, emails, mentions, hashtags, etc. |

---

## 4. Media Insertion Between Text Blocks

### 4.1 Two Approaches

**Approach A: Markdown/HTML mode with `media` array (Bot API 10.2+)**

In `markdown` or `html` field, reference media via special links:
```
![](tg://photo?id=abc123)
![](tg://video?id=xyz789)
![](tg://audio?id=def456)
```

The `media` array maps these IDs to actual media:
```json
{
  "media": [
    {
      "id": "abc123",
      "media": { "type": "photo", "media": "file_id_or_url" }
    },
    {
      "id": "xyz789",
      "media": { "type": "video", "media": "file_id_or_url" }
    }
  ]
}
```

**Media block syntax in Markdown:**
```
![](https://example.com/photo.jpg)
![](https://example.com/photo.jpg "Photo caption")
![](https://example.com/video.mp4 "Video caption")
![](https://example.com/audio.mp3 "Audio caption")
![](https://example.com/audio.ogg "Voice note caption")
![](https://example.com/animation.gif "Animation caption")
```

**Media block syntax in HTML:**
```html
<img src="https://..." />
<video src="https://..."></video>
<audio src="https://...mp3"></audio>
<audio src="https://...ogg"></audio>  <!-- voice note -->
```

**Approach B: Explicit blocks mode (Bot API 10.2+)**

Use `blocks` array with `InputRichBlockPhoto`, `InputRichBlockVideo`, `InputRichBlockAudio`, `InputRichBlockAnimation`, `InputRichBlockVoiceNote`.

This allows explicit placement of media blocks between text blocks.

---

### 4.2 Media Placement Semantics

- Media blocks in Markdown/HTML render as separate block elements
- Media can be placed anywhere in document flow
- Media blocks support optional `caption` and `credit`
- Media blocks support `tg-spoiler` attribute for spoiler media
- For collage/slideshow: media elements are contained WITHIN those blocks

---

## 5. Rich Block Types (21 types as of Bot API 10.2)

### Text Blocks

| Block Type | HTML Tag | Description |
|------------|----------|-------------|
| `paragraph` | `<p>` | Text paragraph |
| `heading` | `<h1>`-`<h6>` | Section heading, size 1-6 |
| `preformatted` | `<pre>`, `<pre><code>` | Code block, optional language |
| `footer` | `<footer>` | Footer text |
| `divider` | `<hr/>` | Horizontal rule |
| `anchor` | `<a name="...">` | In-document anchor |

### Structure Blocks

| Block Type | HTML Tag | Description |
|------------|----------|-------------|
| `list` | `<ul>`, `<ol>` | Unordered/ordered list with items |
| `details` | `<details>`, `<details open>` | Collapsible block with `<summary>` |

### Quote Blocks

| Block Type | HTML Tag | Description |
|------------|----------|-------------|
| `blockquote` | `<blockquote>` | Block quotation with optional `<cite>` |
| `pullquote` | `<aside>` | Centered pull quote with optional `<cite>` |

### Media Blocks

| Block Type | HTML Tag | Description |
|------------|----------|-------------|
| `photo` | `<img>` | Photo with optional caption, credit, spoiler |
| `video` | `<video>` | Video with optional caption, credit, spoiler |
| `animation` | `<video>` (gif) | Animation/GIF with optional caption, credit, spoiler |
| `audio` | `<audio>` | Audio with optional caption, credit |
| `voice_note` | `<audio>` (ogg) | Voice note with optional caption, credit |

### Composite Media Blocks

| Block Type | HTML Tag | Description |
|------------|----------|-------------|
| `collage` | `<tg-collage>` | Media collage with items, optional caption |
| `slideshow` | `<tg-slideshow>` | Media slideshow with items, optional caption |

### Specialized Blocks

| Block Type | HTML Tag | Description |
|------------|----------|-------------|
| `table` | `<table>` | Table with rows, cells, alignment, colspan/rowspan, bordered/striped, caption |
| `map` | `<tg-map>` | Map with lat/long/zoom, optional caption |
| `mathematical_expression` | `<tg-math-block>` | LaTeX formula block |
| `thinking` | (custom) | AI thinking indicator (Bot API 10.2+) |

---

## 6. Collage and Slideshow Semantics

### 6.1 Collage

**Block type:** `collage`  
**HTML:** `<tg-collage>...</tg-collage>`

**Structure:**
- Contains `blocks` array of **media blocks only** (photo, video, animation)
- Optional `caption` (RichBlockCaption with text + credit)
- Items specified as media URLs or tg:// links
- Cannot contain arbitrary text blocks inside collage/slideshow — only media

**Markdown syntax:**
```
![](photo1.jpg)
![](video1.mp4)
```

**HTML syntax:**
```html
<tg-collage>
  <img src="photo1.jpg" />
  <video src="video1.mp4"></video>
</tg-collage>
```

### 6.2 Slideshow

**Block type:** `slideshow`  
**HTML:** `<tg-slideshow>...</tg-slideshow>`

**Structure:**
- Contains `blocks` array of media blocks
- Optional `caption` (RichBlockCaption with text + credit)
- Slides advance sequentially

**Markdown syntax:**
```
![](slide1.jpg)
![](slide2.jpg)
```

**HTML syntax:**
```html
<tg-slideshow>
  <img src="slide1.jpg" />
  <img src="slide2.jpg" />
</tg-slideshow>
```

---

## 7. Headings

**Supported:** YES — h1 through h6

**Markdown:**
```markdown
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6
```

**HTML:**
```html
<h1>Heading 1</h1>
<h2>Heading 2</h2>
<!-- ... -->
<h6>Heading 6</h6>
```

**Block representation (Bot API 10.2+):**
```json
{
  "type": "heading",
  "size": 1,
  "text": "Heading text"
}
```

**Size mapping:** 1 = largest (h1), 6 = smallest (h6)

---

## 8. Quotes and Pull Quotes

### 8.1 Block Quotation

**Supported:** YES

**Markdown:**
```markdown
>Block quotation started
>
>Block quotation continued on the next line
>Block quotation continued on the same line
>
>The last line of the block quotation
```

**HTML:**
```html
<blockquote>
  <p>Block quotation started</p>
  <p>Block quotation continued</p>
  <cite>The Author</cite>
</blockquote>
```

**Block representation:**
```json
{
  "type": "blockquote",
  "blocks": [...],
  "credit": "The Author"
}
```

### 8.2 Pull Quote

**Supported:** YES

**HTML:**
```html
<aside>
  <p>Pull quote text</p>
  <cite>The Author</cite>
</aside>
```

**Block representation:**
```json
{
  "type": "pullquote",
  "text": "Pull quote text",
  "credit": "The Author"
}
```

---

## 9. Tables

**Supported:** YES

**Markdown (GitHub Flavored Markdown compatible):**
```markdown
| Header 1 | Header 2 |
|:---------|:--------:|
| left     | center   |
```

**HTML:**
```html
<table bordered striped>
  <caption>Table caption</caption>
  <tr>
    <th>Header 1</th>
    <th>Header 2</th>
  </tr>
  <tr>
    <td colspan="2" rowspan="2" align="left" valign="top">Value</td>
  </tr>
</table>
```

**Constraints:**
- Table cells can contain ONLY inline formatting (no nested blocks)
- colspan, rowspan, align (left/center/right), valign (top/middle/bottom) supported
- bordered, striped, caption supported
- Note: "Maximum 20 columns" comes from tg-rich-messages library validation, NOT from official Telegram docs. Official Telegram docs do not specify a column limit for tables.

---

## 10. Formulas (Mathematical Expressions)

**Supported:** YES

**Inline formula (Markdown):**
```markdown
$x^2 + y^2$
```

**Block formula (Markdown):**
```markdown
$$E = mc^2$$

```math
E = mc^2
```
```

**Inline formula (HTML):**
```html
<tg-math>x^2 + y^2</tg-math>
```

**Block formula (HTML):**
```html
<tg-math-block>E = mc^2</tg-math-block>
```

**Notes:**
- Formula source treated as raw LaTeX
- Supports both inline (`<tg-math>`) and block (`<tg-math-block>`) forms

---

## 11. Footnotes

**Supported:** YES (via Markdown reference syntax)

**Markdown:**
```markdown
Text with a reference[^id1] and another one[^id2].

[^id1]: Definition of the first footnote.
[^id2]: Definition of the second footnote.
```

**HTML:** Uses `<tg-reference>` and `<tg-reference-link>` tags (per tg-rich-messages library)

**Notes:**
- Footnotes defined at document end
- Referenced via `[^id]` syntax in Markdown
- HTML mode uses custom tags

---

## 12. Collapsible Blocks (Details)

**Supported:** YES

**Markdown:**
```markdown
<details>
<summary>Summary with **bold text**</summary>

### Details heading
- List item with _italic text_
- List item with spoiler
</details>
```

**HTML:**
```html
<details>
  <summary>Summary with <b>bold text</b></summary>
  <h3>Details heading</h3>
  <ul>
    <li>List item with <i>italic text</i></li>
    <li>List item with <tg-spoiler>spoiler</tg-spoiler></li>
  </ul>
</details>
```

**Open by default:**
```html
<details open>
  ...
</details>
```

**Block representation:**
```json
{
  "type": "details",
  "open": false,
  "title": "Summary text",
  "blocks": [...]
}
```

---

## 13. Task Lists (Checklists)

**Supported:** YES

**Markdown:**
```markdown
- [ ] task list item
- [x] completed task list item
```

**HTML:**
```html
<ol>
  <li type="1">Task item</li>
</ol>
```

**Block representation (InputRichBlockListItem):**
```json
{
  "type": "list",
  "items": [
    {
      "blocks": [...],
      "has_checkbox": true,
      "is_checked": false
    },
    {
      "blocks": [...],
      "has_checkbox": true,
      "is_checked": true
    }
  ],
  "ordered": false
}
```

---

## 14. Limits

| Limit | Value | Notes |
|-------|-------|-------|
| **Text characters** | 32,768 UTF-8 | Including emoji alt text and formula source |
| **Blocks** | 500 | Including nested blocks, list items, table rows, quotation blocks, details blocks |
| **Nesting depth** | 16 levels | Formatting and blocks |
| **Media attachments** | 50 total | Photos, videos, audio files combined |
| **Table columns** | 20 | Per table (library validation) |
| **Media ID length** | 1-64 chars | For tg:// links (A-Z, a-z, 0-9, _, -) |
| **editMessageText text** | 1-4096 chars | After entity parsing |
| **Draft expiration** | ~30 seconds | Ephemeral preview |

---

## 15. Chat Type Support

| Chat Type | sendRichMessage | sendRichMessageDraft | editMessageText (rich) |
|-----------|-----------------|----------------------|------------------------|
| **Private chat** | YES | YES | YES |
| **Bot** | YES | NO | YES (inline) |
| **Supergroup** | YES | NO | YES |
| **Channel (@username)** | YES | NO | YES |
| **Forum topic** | YES (via message_thread_id) | NO | YES |
| **DM topic** | YES (via direct_messages_topic_id) | NO | YES |

**Key findings:**
- `sendRichMessageDraft` is **private chat only** (confirmed in docs)
- `sendRichMessage` works for all chat types including channels
- Channel support via `chat_id: "@channelusername"`

---

## 16. Bot Editing Capabilities

### 16.1 Can a bot edit a rich message?

**YES** — via `editMessageText` with `rich_message` parameter (Bot API 10.1+)

**Restrictions:**
1. `text` and `rich_message` are mutually exclusive
2. For inline messages: cannot upload new files, must use `file_id` or URL
3. Bot can only edit messages sent by the bot
4. No dedicated `editRichMessage` method

### 16.2 Editing workflow

```python
# Initial send
result = bot.sendRichMessage(chat_id=..., rich_message={...})

# Edit rich content
bot.editMessageText(
    chat_id=chat_id,
    message_id=result.message_id,
    rich_message=new_input_rich_message
)
```

---

## 17. Return Structure / Provider Response Proof

### 17.1 sendRichMessage response

Returns a `Message` object. To verify rich structure was preserved:

**Check `Message.rich_message` field:**

```json
{
  "message_id": 123,
  "date": 1760123456,
  "chat": {...},
  "from": {...},
  "text": "...",           // May contain plain text fallback
  "rich_message": {       // Present if message is rich-formatted
    "blocks": [
      {
        "type": "heading",
        "size": 1,
        "text": "..."
      },
      ...
    ],
    "is_rtl": false
  }
}
```

**Verification strategy:**
1. `rich_message` field present → Telegram stored rich structure
2. `Message.text` may also contain text (depends on how sent)
3. If `rich_message` absent but sent with rich → fallback may have occurred

### 17.2 editMessageText response

Returns edited `Message` object (same structure as above).

### 17.3 sendRichMessageDraft response

Returns `True` (boolean) — no message structure proof available (ephemeral).

---

## 18. Premium vs Bot API Behavior

### 18.1 Features requiring Telegram Premium (USER side)

| Feature | Premium Required? | Notes |
|---------|-------------------|-------|
| Custom emoji in messages | **YES** (for sender) | Bot owner needs Premium OR bot purchased username on Fragment |
| Animated emoji | **YES** (for sender) | Custom emoji packs |
| Infinite reactions | **YES** (for reactor) | Up to 3 reactions per message |
| Emoji status | **YES** | Profile status |
| 4 GB file uploads | **YES** (for uploader) | Free users: 2 GB |
| Faster downloads | **YES** | Priority bandwidth |
| Voice-to-text | **YES** | For video messages |
| Ad-free experience | **YES** | In public channels |

### 18.2 Bot API Rich Features (independent of user Premium)

| Feature | Premium Required? | Notes |
|---------|-------------------|-------|
| sendRichMessage | **NO** | Available to all bots via Bot API 10.1+ |
| sendRichMessageDraft | **NO** | Available to all bots |
| editMessageText (rich) | **NO** | Available to all bots |
| Tables | **NO** | Rendered natively by Telegram clients |
| Headings | **NO** | Rendered natively |
| Lists/checklists | **NO** | Rendered natively |
| Block quotes | **NO** | Rendered natively |
| Collapsible blocks | **NO** | Rendered natively |
| Math formulas | **NO** | Rendered natively |
| Collages | **NO** | Rendered natively |
| Slideshows | **NO** | Rendered natively |
| Maps | **NO** | Rendered natively |
| Media blocks | **NO** | Bot needs rights to send media type |
| Custom emoji in rich messages | **CONDITIONAL** | Bot needs Premium owner OR Fragment username |

### 18.3 Custom Emoji in Rich Messages

**From Bot API docs / Stack Overflow:**

- Custom emoji entities can only be used by bots that purchased additional usernames on Fragment
- **OR** bot owner has Telegram Premium subscription (since Bot API 9.4, Feb 2026)
- Bot can use custom emoji in private, group, and supergroup chats
- **Channels NOT explicitly listed** as supported for custom emoji from bots

---

## 19. Unsupported / Unknown Features

### 19.1 Explicitly unsupported (no evidence in official docs)

| Feature | Status | Notes |
|---------|--------|-------|
| `editRichMessage` dedicated method | **UNSUPPORTED** | Use `editMessageText` with `rich_message` |
| Rich message scheduling | **UNSUPPORTED** | No `schedule_date` in sendRichMessage params |
| Rich message reactions API | **UNSUPPORTED** | Bots can't set reactions on their messages |
| Rich message replies in channels | **CONDITIONAL** | Bot must be admin or channel posts |

### 19.2 Unknown / needs verification

| Feature | Status | Notes |
|---------|--------|-------|
| Rich message in topic replies | **CONDITIONAL** | `message_thread_id` supported but needs testing |
| Rich message copy-to-clipboard behavior | **UNKNOWN** | Telegram Web has rendering issues reported |
| Cross-client rendering consistency | **UNKNOWN** | Telegram Web vs Desktop vs Mobile differences reported |

---

## 20. Rich Text Inline Formatting (25+ types)

**Available inline formatting (RichText subtypes):**

| Type | Markdown | HTML | Description |
|------|----------|------|-------------|
| bold | `**text**` or `__text__` | `<b>` | Bold |
| italic | `*text*` or `_text_` | `<i>` | Italic |
| underline | (not in Markdown) | `<u>` | Underlined |
| strikethrough | `~~text~~` | `<s>` | Strikethrough |
| spoiler | `||text||` | `<tg-spoiler>` | Spoiler |
| code | `` `text` `` | `<code>` | Inline code |
| marked | `==text==` | `<mark>` | Marked/highlighted |
| subscript | (not in Markdown) | `<sub>` | Subscript |
| superscript | (not in Markdown) | `<sup>` | Superscript |
| link | `[text](url)` | `<a href>` | URL link |
| email | `[text](mailto:)` | `<a href="mailto:">` | Email link |
| phone | `[text](tel:)` | `<a href="tel:">` | Phone link |
| user mention | `[text](tg://user?id=)` | `<a href="tg://user?id=">` | User mention |
| inline math | `$x^2$` | `<tg-math>` | Inline formula |
| custom emoji | `![](tg://emoji?id=)` | `<tg-emoji>` | Custom emoji |
| date/time | `![](tg://time?...)` | `<tg-time>` | DateTime |
| bank card | (auto-detected) | `<tg-bank-card>` | Bank card number |
| hashtag | `#tag` | (auto) | Hashtag |
| cashtag | `$USD` | (auto) | Cashtag |
| bot command | `/command` | (auto) | Bot command |

---

## 21. Formatting Modes Comparison

### 21.1 Rich Markdown Mode

**Pros:**
- GitHub Flavored Markdown compatible where possible
- Can contain arbitrary HTML
- Familiar syntax for developers

**Cons:**
- Media must be separate blocks (not inline)
- Media blocks support only HTTP/HTTPS URLs (NOT tg:// links in Markdown mode)
- Cannot specify programming language for standalone code tags
- **Markdown not parsed inside HTML block tags** except `<blockquote>`, `<details>`, and `<aside>` — inside other HTML blocks only HTML tags can be used (no Markdown syntax)

### 21.2 Rich HTML Mode

**Pros:**
- Full control over structure
- Supports all tags including custom Telegram tags
- Can use `media` array with tg:// links (Bot API 10.2+)

**Cons:**
- More verbose
- Programming language cannot be specified for standalone `<code>` tags

### 21.3 Blocks Mode (Bot API 10.2+)

**Pros:**
- Explicit type-safe structure
- Direct media block placement
- Best for programmatic generation

**Cons:**
- Most verbose
- Newest feature (July 2026)

---

## 22. Verification Strategy for Providers

### 22.1 Pre-send validation

1. **Text length:** ≤ 32,768 UTF-8 characters
2. **Block count:** ≤ 500 blocks (including nested)
3. **Nesting depth:** ≤ 16 levels
4. **Media count:** ≤ 50 media attachments
5. **Table columns:** ≤ 20 columns

### 22.2 Post-send verification

1. Check `Message.rich_message` field is present
2. Verify `rich_message.blocks` structure matches sent content
3. If `rich_message` absent → fallback occurred, log for analysis

### 22.3 Capability detection

1. Attempt `sendRichMessage` on test chat
2. If method returns `Message` with `rich_message` → fully supported
3. If method fails with "Bad Request" or method not found → fallback to MarkdownV2
4. **Implement capability latch** — once determined, cache result

---

## 23. Fallback Strategy

### 23.1 When sendRichMessage unavailable

**Fallback to:** `sendMessage` with `parse_mode: "MarkdownV2"` or `"HTML"`

### 23.2 Degradation mapping

| Rich Feature | MarkdownV2 Fallback |
|--------------|---------------------|
| Tables | Plain text rows (degraded) |
| Headings | `#` visible markers or bold |
| Code blocks | Indented or inline code |
| Collapsible details | Visible markers |
| Math formulas | Raw LaTeX text |
| Media blocks | May not render |
| Task lists | `- [ ]` visible markers |

### 23.3 Recommended fallback trigger

Use rich mode ONLY when content contains:
- Tables
- Task lists
- `<details>` blocks
- Block math/formula syntax
- Other structures that degrade poorly through MarkdownV2

For ordinary prose, use `sendMessage` with MarkdownV2 for consistent typography.

---

## 24. Edits During Streaming

### 24.1 Streaming architecture

**Problem:** Intermediate `editMessageText` calls during streaming destroy rich formatting if not using rich_message parameter.

**Correct approach:**

1. **First chunk:** `sendRichMessage` with initial content (or `sendRichMessageDraft` for private chats)
2. **Intermediate chunks:** `editMessageText` with `rich_message` parameter for each update
3. **Final chunk:** `editMessageText` with complete `rich_message`

**Alternative (if edit-based streaming not implemented correctly):**
1. Send initial rich message
2. For each update, send NEW rich message
3. Delete old message

### 24.2 Rich draft streaming (private chats only)

1. Use `sendRichMessageDraft` for streaming preview
2. Draft is ephemeral (30 seconds)
3. Must call `sendRichMessage` to persist final content

---

## 25. Known Issues / Client Incompatibilities

### 25.1 Telegram Web rendering

**Reported:** Telegram Web may not render `sendRichMessage` replies correctly (June 2026 reports).

**Workaround:** Disable rich messages for Telegram Web users or use fallback.

### 25.2 Body text size

**Reported:** Rich Message body text appears larger than normal bot messages, ignoring user's Telegram text-size setting (June 2026).

**Impact:** May be poor default for ordinary prose.
**Mitigation:** Use rich mode only for structured content (tables, task lists, etc.)

### 25.3 Line break handling

**Reported:** Rich messages may collapse ordinary line breaks into single paragraph.

**Mitigation:** Convert text-node newlines to `<br/>` tags before sending via rich mode.

---

## 26. Provider Integration Contract

### 26.1 What providers MUST implement

1. **sendRichMessage** call with valid `InputRichMessage`
2. **Pre-send validation** (text ≤ 32768, blocks ≤ 500, media ≤ 50, depth ≤ 16)
3. **Response verification:** check `Message.rich_message` field
4. **Capability detection:** test endpoint availability, latch result
5. **Fallback:** to `sendMessage` with MarkdownV2/HTML when rich unavailable

### 26.2 What providers MAY implement

1. `sendRichMessageDraft` for private chat streaming
2. `editMessageText` with `rich_message` for edits
3. Blocks mode (InputRichMessage.blocks) for explicit structure
4. HTML mode with `media` array for tg:// link resolution

### 26.3 What providers MUST NOT assume

1. No `editRichMessage` method exists — use `editMessageText`
2. No scheduling for rich messages
3. No guarantee of cross-client rendering consistency
4. Custom emoji requires Premium owner OR Fragment username

---

## 27. Source References

| Source | URL | Date Accessed |
|--------|-----|---------------|
| Telegram Bot API — sendRichMessage | https://core.telegram.org/bots/api#sendrichmessage | 2026-08-10 |
| Telegram Bot API — Rich Messages | https://core.telegram.org/bots/api#rich-messages | 2026-08-10 |
| Telegram Bot API — editMessageText | https://core.telegram.org/bots/api#editmessagetext | 2026-08-10 |
| Bot API Changelog (June 11, 2026) | https://core.telegram.org/bots/api-changelog | 2026-08-10 |
| Bot API Changelog (July 14, 2026) | https://core.telegram.org/bots/api-changelog | 2026-08-10 |
| tg-rich-messages library (TypeScript) | https://github.com/vdistortion/tg-rich-messages | 2026-08-10 |
| Telegram Premium FAQ | https://telegram.org/faq_premium | 2026-08-10 |
| Hermes Agent PR #44829 | https://github.com/NousResearch/hermes-agent/pull/44829 | 2026-08-10 |
| Hermes Agent Issue #46009 | https://github.com/NousResearch/hermes-agent/issues/46009 | 2026-08-10 |

---

## 28. Summary for Following Agents

**This specification is the CONTRACT for Telegram Rich Messages integration.**

**Key takeaways:**

1. `sendRichMessage` is REAL and ACUTAL (Bot API 10.1+, June 2026)
2. Rich document is defined by `InputRichMessage` with ONE of: `html`, `markdown`, or `blocks`
3. Media inserted between text blocks via:
   - Markdown/HTML syntax with `media` array (Bot API 10.2+), OR
   - Explicit `blocks` array with media block types
4. Collage = `<tg-collage>` containing media items; Slideshow = `<tg-slideshow>` containing media items
5. Bot CAN edit rich messages via `editMessageText` with `rich_message` parameter
6. Proof of saved rich structure: check `Message.rich_message` field in response
7. Most rich features work via Bot API without Premium; custom emoji requires Premium owner or Fragment username
8. `sendRichMessageDraft` is private-chat-only; `sendRichMessage` works for bots, groups, channels

**Unsupported:**
- No dedicated `editRichMessage` 
- No scheduling for rich messages
- No guaranteed Telegram Web compatibility

**Next agents should:**
- Use this spec + capability matrix as source of truth
- Do NOT trust previous chat claims without checking this doc
- Implement validation, capability detection, and fallback as specified
