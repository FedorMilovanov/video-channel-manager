# MILOVI CAKE — Telegraph cover / Instant View acceptance (2026-11-07)

**State: LIVE EDIT COMPLETED AND SOURCE VERIFIED 2026-11-07.** Existing Telegraph page was edited in place once, with a positive editPage reply and independent getPage readback confirming 56 nodes and 6 figures, including original selected cover as first image. Public HTML was separately read with TelegramBot user-agent: og:image and twitter:image both point to the selected cover. Telegram client Instant View and link preview cache refresh were not independently observed; don't claim client-side rendering/caching is guaranteed.

## Existing, immutable targets

- Existing article: https://telegra.ph/Kto-pridumal-konditerskoe-delo-Ot-myasnyh-pirogov-do-iskusstva-desertov-11-07-2
- Telegraph page path (use editPage, not createPage): `Kto-pridumal-konditerskoe-delo-Ot-myasnyh-pirogov-do-iskusstva-desertov-11-07-2`
- Original cover: `content/telegram/milovi-cake/assets/patisserie-history-cover-20261107.webp`, 1672 × 941, SHA256 `2bf4ec0e537fcb3c8349267ade1992d779e12ef832c9497a62a10c014d003328`, Git blob SHA1 `b8a0303742e20f3b231d3bcd019029793a495a3a`
- Pinned public original image URL: https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/c29d95072bc8b1781466ec4781cc94481909b164/content/telegram/milovi-cake/assets/patisserie-history-cover-20261107.webp
- Existing Telegram post, leave unchanged: https://t.me/MiloviCake/28 (photo post)
- Existing VK post, leave unchanged: https://vk.com/wall-68859909_563

## Exact intended layout

1. **First article image:** the owner-selected golden vintage patisserie cover, before the lead text; this should be the first Telegraph `figure/img` node.
2. Original Abraham Bosse's **Metropolitan Museum** engraving moves next to the opening paragraph of **section 3** (an engraving from ca. 1632–33), retaining its historic image source, wording, public-domain attribution and caption.
3. Sugar work, Stohrer, Carême and Saint-Honoré images remain in their respective original sections, with the same captions and source links.
4. Original article text, ten section headings, author and original order link to `https://milovicake.ru/` are preserved.
5. Authoritative prepared sources: `content/editorial/milovi-cake/patisserie-profession-history-20261107.telegraph-nodes.json` (56 nodes, 6 figures), matching `.html` and source manifest.

## Strict live editor procedure

Access is not included in Git. The Telegraph access token is encrypted on the user's authorized Windows host under `%LOCALAPPDATA%/MiloviCake/telegraph-history-editor-20261107.dpapi`; its private bytes must **never** be printed, checked into Git, sent in chat or copied to another app. The previously paired desktop connection reached its monthly usage limit on Nov 7. Do **not** repeatedly retry or reconnect.

When the authorized Telegraph editor is available:

1. Read and archive the live page via `getPage(<exact page path>, return_content=true)`, verifying the original live content and preserving author, byline and title. The last certified live revision had 55 nodes and five images.
2. Validate the new first image is publicly fetchable from Telegram/Telegraph, ideally upload the exact owner cover to Telegraph's own image hosting to get an immutable `https://telegra.ph/file/...` URL, then replace **only the image source** of the first node in the prepared bundle. Never invent a Telegraph file URL or reuse an unrelated generic illustration.
3. Commit any required final image-host normalization back into the corresponding JSON, HTML, manifest and tests, preserving all content and digest checks.
4. Make one **`editPage`** against the exact existing path, not `createPage`. Retain original metadata and all 55 historical nodes in re-ordered positions plus the new cover (56 total). Never publish a second duplicate page.
5. Independently call `getPage(path, return_content=true)` after the write and validate 56 nodes, six `img` elements, first image = selected cover URL, Bosse engraving located after the first paragraph in section 3, five unchanged historical image URLs, body paragraphs, citations, cake CTA, and exact original page URL.
6. Check the real Telegram **link-only preview / Instant View** for the existing page in a *private, unpublished draft*, ensuring large cover image is selected. Telegram may cache old previews; do not promise an immediate refresh or add arbitrary URL query parameters to public channel posts.
7. Document live update timestamp, full getPage readback and preview evidence in an audit; only then remove the manifest's pending-live status and close this task.

**Important:** Telegram Instant View is available for Telegraph links in messages that have a proper link preview. Editing the page does **not** change the content type of the already published Telegram photo `/28` or make its image/photo attachment disappear. Do not delete or repost `/28` just to force an Instant View preview; owner has not authorized destructive replacement of published content.

## Completed live-editor acceptance on 2026-11-07

- Original page edited exactly once via owner-protected DPAPI credential on authorized newly reconnected Milovi Desktop Commander, no token exposed.
- Provider positive editPage reply, independent getPage readback: 56 nodes, six images.
- Selected cover first as figure/img, Bosse engraving moved to section 3, all five other historical images/paragraphs preserved; original article URL unchanged.
- Independent public HTML GET 200, first image correct, og:image and twitter:image point to selected cover for newly generated previews.
- Local audit (not committed): operator-output/milovi-telegraph-instantview-cover-live-20261107.json.
- Existing Telegram photo post 28 and VK wall post 563 remain unchanged. Do not delete/repost to alter photo into a text-link post.
- Telegram may display cached preview data; no claim that existing photo post automatically becomes Instant View.
