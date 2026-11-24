# Charnock release reconciliation — live readback evidence (2026-11-23)

**READ_ONLY EVIDENCE / NOT APPROVAL / NOT A RELEASE MANIFEST / NO SEND**

Issue: https://github.com/FedorMilovanov/video-channel-manager/issues/997

## Authoritative objects and scopes

The protected historical release manifest `charnock-reschedule-2026.json` is **not** the QC page-edit manifest `charnock-qc-reissue-20261121.json`. Distinguish the two; identical URL and schedule do not imply identical article bytes. The terminal Telegram replacement receipt is in **`state/lordchrist-telegram`** (not necessarily in `main`).

| Article | Scheduled MSK | Historical reissue article Git blob | Current queue + QC article Git blob | Result |
| --- | --- | --- | --- | --- |
| 09 | 20 Nov | `bbf90eb3062eeb383bfe58745c86898ddb1feb17` | `5b39c769c81aac137009c835f56227cb5a60264a` | **VERIFIED** reissue, see separate state receipt |
| 10 | 24 Nov | `1173a305bb192c0aec3606485c5b3664c95e8650` | `cb1819866d98348a184e98a2893ee847a02c0fdd` | **BLOCKED** until versioned source-binding decision |
| 11 | 27 Nov | `cd64ba6071f08591e5959949cc73b877d4401e70` | `d42392bb593de4f89d36a12a3548f459efe41090` | **BLOCKED**, translation and source-credit issue |
| 12 | 1 Dec | `095de9e09ccfcb99e389ea92fc40e350fa374f02` | `e7ea215bcea907747363f41dc0bc4443f58269a8` | **BLOCKED**, source-credit issue |
| 13 | 4 Dec | `cc9b20e98cb88c14b7c3ec739a4c07c4f738cae9` | `eedc00889bb2e907bbcc91de914d8ddf68f1737c` | **BLOCKED**, editorial and SEND HOLD |

### №09 terminal state branch receipt

Read-only GitHub source: `refs/heads/state/lordchrist-telegram`, observed commit `bca3c01f2455516b2756494452cda7e8cd366098`,
`content/telegram/lordchrist/telegraph-v1/publication-ledger.json`.
`entries.lordchrist-telegraph-charnock-09.scheduled_reissue` records:
- `state=verified`; `provider_effect=verified`
- old deleted Telegram message ID `1599`; **new message ID `1630`**
- `sent_at_moscow=2026-11-20T12:05:33.409581+03:00`
- `verified_at_moscow=2026-11-20T12:05:46.394323+03:00`

**Do not replay №09.** In this observed state, 06–08 and 10–13 have **no** `scheduled_reissue` field. Old Telegram messages 1596–1603 are historical and must not be treated as replacement receipts.

## Direct public Telegraph API readback (2026-11-23)

Read-only endpoint pattern:
`https://api.telegra.ph/getPage/{path}?return_content=true`, with live origin preferred over a search cache.
Checks below used the public `getPage` `ok:true` response, without Telegra.ph account tokens or provider mutation. Extracted text was whitespace-normalized, including rich children.

**№10 public page:** https://telegra.ph/Sudya-kotorogo-nelzya-vyklyuchit-sovest-i-zhazhda-beskonechnogo-11-05
- Exact page path/title and author `Господь Бог`, author URL `https://t.me/lordchrist`.
- 97 top-level Telegraph nodes, including 25 `blockquote` nodes and a visible final `© Цитаты Чарнока` source-credit paragraph.
- Compared **every one** of the 69 JSON rich blocks in the current QC article (`cb181986...`) with the public API node text: **68/69 exact normalized text matches**. The only exception is the headline `h-1` (uppercase authored presentation vs title case in live page title); it has a corresponding partial/case-insensitive title match. This is **visible-text parity**, not exact provider JSON/node-attribute/media parity.
- All **seven** prose changes `p-1,p-2,p-7,p-12,p-24,p-29,p-30` **and the newly split `p-35`** match the current QC version exactly. None of those changed blocks exactly matches historical v1. All 25 rich blockquotes and all 26 `sources` are structurally identical between old and current Git blobs; media and media_slots are also structurally equal. Hence **do not silently revert** to historical v1 just to satisfy the old reissue manifest.

**№11 public page:** https://telegra.ph/Nebo-ne-molchit-sudy-chudesa-i-prorochestva-11-05
- Public `ok:true`, expected title/author; 71 top-level nodes, 18 blockquotes.
- Final © Gutenberg credit absent. The published mistranslation `странное расстройство у некоторых имений` remains visible in q-10. The proposed correction is **only** in Draft PR #1100, without approval or in-place edit authority.

**№12 public page:** https://telegra.ph/Nelzya-dokazat-chto-Boga-net-shest-otvetov-somnevayushchemusya-11-05
- Public `ok:true`, expected title/author; 55 nodes, 13 blockquotes; final © Gutenberg credit absent.

**№13 public page:** https://telegra.ph/Utverditsya-i-poklonitsya-chem-zakanchivaetsya-beseda-o-bytii-Boga-11-05
- Public `ok:true`, expected title/author; 56 nodes, 13 blockquotes; final © Gutenberg credit absent. The five quotation repairs from 21 Nov are already present in canonical QC JSON and public text. In particular q-3 includes an explicit `[…]` for the omitted English argument and appears **merged with the next Telegraph blockquote** via a visible `…` separator; q-19 exactly matches the longer current quote including flies, Ps. 10:4 and its conclusion. These content fixes are not pending re-application. **Telegram SEND HOLD remains enforced** independent of the © credit.

## What remains to close safely

1. **№10 before the 24 Nov slot:** independent editorial/owner authorization of a **versioned source-binding migration** that explicitly identifies the current QC article Git blob, regenerated `source_article_sha256` and media-base, preserved original deleted Telegram ID and ledger history, and exact page URL. Run guard checks (including structural live-tree reconciliation and all release tests) **before** making a durable authority change. If not complete, the scheduled executor should fail closed; no backfill.
2. **№11–13:** qualified review of the source-credit corrections and translation candidates; define a durable intent for each authorized in-place `editPage`, provider-origin readback and one receipt. Do not reuse the retired unsafe editor or send Telegram to repair Telegraph content.
3. **№06–08:** separately approve future Moscow dates, preserving their original deleted receipts; no manual replay of November dates.
4. **№13 and Research PR #629:** independent ED-06 translation review (currently 0/12), remaining ED-02 1684 witness collation and rights review. Those cannot be represented by a successful software CI check.

**This file is an audit packet, not a release artifact.** No existing approved source, queue, manifests, ledger, schedule, workflow, live Telegraph pages, media, MILOVI job or Telegram messages were modified by this inspection. Public API readback proves observed visible text only at this date; it does not replace approval, rights clearance, complete tree comparison or a provider-write receipt.
