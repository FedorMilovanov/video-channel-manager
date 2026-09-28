# @lordchrist quotation attribution standard

Status: canonical presentation rule for quotations in rich/editorial Telegram posts.

## Rule

A Telegram blockquote contains **only the quoted words**. The author and work title are not part of the quotation block.

Immediately after the quote block, place attribution on its own line in *italic*, outside the blockquote:

> «Точный текст цитаты»

*Автор, «Название труда»*

This is the default for Scripture, theologians, confessions, church fathers and other cited primary sources.

For Scripture, use the same visual hierarchy:

> «Текст библейской цитаты»

*Лк. 8:13*

## Why

Keeping attribution outside the coloured Telegram quote block prevents the author/work metadata from looking like part of the quoted sentence. It also gives the post a cleaner editorial hierarchy: quotation first, source second.

## Spacing for Android manual paste

When a manually copied ChatGPT article needs a visibly blank line between blocks in Telegram, the transport layer may use a line containing an invisible `U+2060 WORD JOINER`. The character must remain invisible to the reader and must never replace normal punctuation or appear inside quoted wording.

The canonical Android insertion path remains:

**Rendered ChatGPT text → Copy → Telegram composer → long-press → system Paste.**

Do not insert rich posts from the keyboard clipboard/history panel because that path can flatten rich text to plain text.

## Primary-source discipline

Attribution styling does not relax evidence requirements. Historical quotations must still be exact primary-source quotations or clearly identified editorial translations from a verified primary/public-domain text. Paraphrases must not be placed inside quotation marks.
