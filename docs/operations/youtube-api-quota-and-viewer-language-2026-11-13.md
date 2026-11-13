# YouTube API compliance and viewer-language triage — 2026-11-13

**Scope:** `video-channel-manager` / YouTube Data API, principally `project_key=legendary-poet`.  
**Owner-facing status:** evidence and incident handoff; **not** permission to issue API or browser writes.  
**Related owning tracker:** [Legendary Poet multilingual rollout #903](https://github.com/FedorMilovanov/video-channel-manager/issues/903).  
**Do not substitute** for [project identities](project-identity-registry.md), the current operating contract, or the separate project `lord-god-strength`.

## 1. API compliance and quota — verified versus pending

| Item | Evidence and state | Action |
| --- | --- | --- |
| Google YouTube API Services compliance/quota application | Owner submitted the official Google form on **13 November 2026 (Moscow date)**; both the Google confirmation page and an acknowledgment email were observed. | **Submission complete.** Await Google's decision; do not call this quota approval. |
| Requested quota | **100,000 units/day** requested for the locally operated Video Channel Manager. | This is a **requested allocation**, not approved capacity. |
| Cloud OAuth project | Numeric client ID prefix **1067074369047** extracted from the configured installed Google OAuth client. | **Cloud Console dashboard project-number confirmation remains pending**; a dashboard attempt timed out. Do not assume the numeric OAuth prefix independently proves Google approved or linked all channel aliases. |
| App privacy/terms | [Privacy Policy](https://github.com/FedorMilovanov/video-channel-manager/blob/main/PRIVACY.md) and [Terms](https://github.com/FedorMilovanov/video-channel-manager/blob/main/TERMS.md) published via PRs **#909**, with links visible on the [public app landing README](https://github.com/FedorMilovanov/video-channel-manager) via **#913**. | Published docs are evidence, **not** proof that every runtime retention/deletion and OAuth-revocation behavior is fully implemented; audit those behaviors independently. |
| Compliance attachments | Four file inputs in the actual Google form held source screenshots, app landing screenshot, terms PDF, and a composition of **real** OAuth/account-access/CLI evidence, then form validation showed only legal attestations remaining. Owner later consented, submitted and showed Google's success page. | Submission complete. Do not retransmit because a confirmation email arrives. Preserve local evidence privately outside Git. |
| Live daily quota | An official owner `videos.list` read for eight selected Legendary Poet video IDs returned **HTTP 403 `quotaExceeded` on 13 November 2026**; no automatic retry was issued. | **HOLD** new owner-API reads and especially all writes until a fresh permitted quota window and a bounded read-only probe confirm availability. No extra Cloud projects to evade limits. |
| Google response | Acknowledgment said review will follow; **no approval or newly granted limit verified** at this checkpoint. | Check email for a specific approval, questions or rejection. Track separately from the submission milestone. |

No addresses, contact emails, OAuth secrets, browser profiles, external media or personal identifiers are stored here.

## 2. Clarification of the user's report — **English title/description with VPN**

The owner reported that **Russian videos appear with English titles and descriptions while watching YouTube through a VPN**. The owner did **not** report a confirmed change to the audio or the Russian metadata in YouTube Studio.

YouTube officially chooses which localized **title/description/captions** to display using viewer-side signals including preferred languages, location and watch history. VPN-related location may contribute but is not by itself proof of the cause. A viewer may see English metadata whenever `localizations.en-US` exists, **without any changes to the Russian original**. See:
- [YouTube Help — How translated videos display](https://support.google.com/youtube/answer/7296123)
- [YouTube Help — Preferred languages for audio, titles and descriptions](https://support.google.com/youtube/answer/13339776?co=GENIE.Platform%3DDesktop)
- [YouTube API resource — snippet.defaultLanguage, snippet.localized and localizations](https://developers.google.com/youtube/data/reference/rest/v3/videos)
- [YouTube API — videos.list `hl` parameter](https://developers.google.com/youtube/data/reference/rest/v3/videos/list)

**Never conflate four separate facts:**

1. `snippet.title`, `snippet.description` and `snippet.defaultLanguage`: source/default **text**.
2. `localizations[language].title/description`: optional additional language-specific **text**.
3. `snippet.defaultAudioLanguage`: API annotation for the **original audio**, which can be incorrect or unset and needs independent content verification.
4. Watch-page/search-result **display language**: personalized per viewer, partly affected by language/location/history and not a reliable provider-write readback.

**Evidence captured 2026-11-12 01:53:56 UTC** in the local owner inventory for `legendary-poet` (178 videos):
- **178/178** had `snippet.defaultLanguage=ru`;
- **141** had an `en-US` entry in the `localizations` map (completeness per locale requires title/description checks);
- `defaultAudioLanguage`: 171 `ru`, 4 `en-US` (`uP_Hn7D3l0w`, `I-ZXzLCYQmw`, `TCg98H9Zm68`, `x-puy27S2qs`), one `zh` (Chinese-language version `CfpwtD7lWK0`), two missing (`DlLO8yoAE0A`, `QH1sD7J72JQ`).
These are **historical owner-provider readbacks**, not a fresh proof of every item's current live state. The non-`ru` audio-language annotations are **a separate investigation**, not an explanation for English titles. Do not change them automatically or by inference from a Russian title. No claim about whether an alternate audio track exists without inspecting the video.

### Correct diagnostic sequence; no remote mutation

1. Pick **the exact same video ID** with a visibly English watch title under VPN, capture viewer account/browser, VPN on/off, YouTube UI language and playback **preferred languages**. Do not guess from the video search rank.
2. In YouTube settings: profile → Settings → Playback and performance → Language → add/edit preferred languages → select **Russian**. Viewer may also change the UI language to Russian. These are **viewer preferences**, not channel metadata edits. Changing them does not guarantee immediate display changes for every watch page.
3. Compare the **same video** under the viewer's normal and incognito sessions, under VPN and without VPN, keeping observations separate. Do not log personal cookies, IP addresses or Google account information.
4. When quota is available, read the official owner API for the exact ID using `part=snippet,localizations` **without an `hl` localization override**. Compare `snippet.title/description/defaultLanguage` with previously accepted Russian source SHA and inspect all `localizations`, including `en-US`. Optionally call `videos.list?hl=ru` and `?hl=en` **read-only** to demonstrate localized display; `snippet.localized` is read-only representation, not the original `snippet.title`.
5. If RU source text and default language remain unchanged, classify this **viewer-localization behavior**, not a channel error. Preserve English translations for foreign-language discoverability. If a real RU default mutation is discovered, handle that **single exact video** via the owning issue, immutable before/after, owner approval, write lock, quota preflight, readback and no blind retry.
6. Do not modify audio-language settings, remove translations, switch the whole channel to English, or alter MP3Bot's Russian master because the owner saw English viewer-facing text.

**Closure for the report:** explanation and viewer-side remedy documented. **Owner visual comparison of an exact watch page remains unverified**; do not claim provider-side anomaly fixed or audio settings corrected.

## 3. Legendary Poet localization state — post-issue-body receipts

The original body of issue #903 is a **historical pilot checkpoint**. Its statement “NO foreign subtitle publication verified” has been superseded by subsequent **owner-verified issue comments and local release receipts**, not by the creation of this document.

At the latest independently recorded **12 November** wave checkpoint:
- `NZISwKGIzGI` / Tyutchev `Silentium!`: **ten foreign caption tracks** `en-US,fr,es,de,it,pt-BR,pl,tr,ja,zh` verified as provider `serving`; their text was read back, with local per-child receipts. Existing Russian default title/description and the pre-existing English localization preserved.
- Two other videos, `WizaG8S085g` (Lomonosov) and `hUwoFkvUyDE` (Lermontov), each gained nine new verified metadata localizations, with original RU and existing EN preserved. These are **metadata-only** receipts, not proof of captions.
- **195 / 1,780 target locale metadata slots verified** on the 178-video 2026-11-12 baseline, so **1,585 slots remain unverified/missing** as of that checkpoint; this number must not be passed off as a live November 13 full inventory.
- The first attempted `WizaG8S085g::en-US` caption insert got 403 quotaExceeded, with a prior `may_exist` journal state; **read-only reconcile first** after quota resumes. Never blindly reissue it or mark it absent from a rejection alone.

Prewrite safeguards: exact `project_key=legendary-poet`, OAuth alias `legendary-poet`, channel ID `UC-78ys2S3cQ3lpqgXfo-SvQ`, exact video ID, all pre-existing localizations merged, preserve original RU and already verified English, bound content evidence, durable journal `may_exist` / `verified`, common write lock, no retry on HTTP uncertainty.

This quota form concerned a combined API client used by multiple authorized channels; it **does not** merge content identities or authorize operations against `lord-god-strength` or `milovi-cake`.

## 4. Follow-up gates and scope ownership

| Gate | Minimum evidence for closure | Owner |
| --- | --- | --- |
| Quota application receipt | Official confirmation page **and** Google acknowledgment email | **Closed** 2026-11-13 |
| Quota increase granted | Actual Google response **and** verified current quota/project limit | **Open** |
| Original-language viewer complaint | Confirmed viewer preferred-language settings and same-ID VPN on/off comparison; distinct from owner API original/locale readback | **Explained; viewer comparison pending** |
| Four suspicious `en-US` audio annotations and two missing values | Verified spoken/produced original audio + exact current provider state; only then decide whether to update | **Separate, open; no mass fix** |
| Multilingual content completion | Full fresh owner inventory and per-video locale/caption acceptance with explicit rights/HOLD exceptions | **Open (#903)** |
| Cloud project number | Dashboard proof for numeric prefix in installed OAuth credentials | **Open** |
| OAuth policy compliance | Evidence of revocation, token cleanup and API-data retention/deletion behavior on the actual supported current-main runtime | **Open** |
| MP3Bot dubbing & media handoff | Only the specifically authorized dubbed MP4/SRT workflow, with independent technical/audio/rights approvals | **Unrelated to viewer-localized text** |

**Local evidence (not committed):** `%LOCALAPPDATA%\TheLegendaryPoet\localization-wave-20261112\`, including `owner_inventory_20261112.json`, per-child release receipts and exact captions; application form evidence in the operator's Downloads. Treat these as historical observations until fresh provider reconciliation.

This document does **not** direct another agent to modify existing `mp3telegrambot` dubbing/media assets. Its YouTube presentation notes may be linked from MP3Bot's separate presentation documentation **after** the active foreign-agent worktree changes are reconciled; do not overwrite those pending edits.


## 5. Google reviewer requested a full screen recording — action required 2026-11-13

**This section supersedes any prior "awaiting Google's response" summary for the next action.** The original compliance submission is acknowledged, but **Google has determined the evidence insufficient to conduct its full YouTube API compliance review**. This is a request for additional evidence, not an approval and not a final rejection.

**Official reviewer email:** received Friday **2026-11-13 03:56:49 Pacific / 14:56:49 Moscow**, in the same Google YouTube API Services submission thread; email sender `YouTube API Quota`. Its request, paraphrased faithfully:

> Provide a detailed, step-by-step **visual reference, i.e. a screencast**, showing the **complete end-to-end Video Channel Manager workflow**, specifically **YouTube video metadata management and subtitle translation**, for the owner's channels.

Google requested all required supporting evidence and complete answers **within seven business days**. Working estimate **2026-11-24**, calculated starting with the next working day (November 16), with no holiday adjustments; **aim to respond by November 20** to avoid ambiguity. This is *not* a new submission deadline the API automatically enforces, nor confirmation Google accepted a late response.

**Actual completion criterion:** a genuine, legible walkthrough of the real application's operations is recorded and inspected, a reachable video sharing link with reviewer access is placed in a reply **within the existing Google email thread**, and the reply is verified in Sent/thread. A draft, screenshots-only composite, code listing, form receipt, API quota estimate or fabricated browser UI does **not** satisfy the request by itself.

### 5.1 Required evidence storyboard — show only real operations

1. **Opening and identity (00:00–00:40):** real computer screen, repository/app name `Video Channel Manager`, current checkout/CLI version, explicit separate project keys `legendary-poet` and `lord-god-strength` and their owner-authorized YouTube channels. Do **not** display tokens, full OAuth client IDs, user email addresses, private browser tabs or local secrets.
2. **OAuth (00:40–01:40):** app's actual authorization mechanism, its requested scope descriptions and how a channel owner grants/revokes permissions, using existing authorized context. A new consent prompt is *optional* and must not be approved, canceled, or used to revoke real access merely for filming. Do not show access or refresh tokens, authorization codes, cookies or callback query strings.
3. **Read exact video (01:40–02:30):** demonstrate the supported owner-video selection and inventory/read-only `videos.list` workflow for an actual exact video ID, with `snippet.title/description/defaultLanguage` and `localizations` visibly distinct. The original RU content must remain unchanged. If quota returns `quotaExceeded`, show the genuine error once; do **not** retry to manufacture a success.
4. **Translate metadata (02:30–04:00):** demonstrate the actual local editorial process from an existing Russian source through verified language-specific titles/descriptions, source checks, and an exact before/after *offline* change plan. Label offline stages as such. The producer must preserve existing RU and en-US and the full merged localization map.
5. **Subtitle translation and alignment (04:00–05:40):** show original media timing/source text, actual translated SRT files with timing (not fabricated examples), validation of actual duration/Unicode/timecode and the per-language artifact directory. Prefer a previously verified `NZISwKGIzGI` child with 10 served captions, plus the relevant local hashes/journals.
6. **Provider result and readback (05:40–07:10):** show the app's actual official YouTube API calls or its verified nonsecret receipts from a prior successfully completed run, including `videos.update part=localizations`, `captions.insert`, `captions.list/download` readback. Mark historical receipts **"Previously completed and verified on 2026-11-12"**, not as present-tense writes. If a fresh quota-safe call cannot execute, show the actual `403 quotaExceeded` and why the 100k/day request is needed. Do not publish/modify a video solely to create a compliance demo.
7. **Result to viewer and privacy (07:10–08:20):** show real YouTube Studio or public video watch page for the same exact ID (if accessible) and the public app [Privacy Policy](https://github.com/FedorMilovanov/video-channel-manager/blob/main/PRIVACY.md), [Terms](https://github.com/FedorMilovanov/video-channel-manager/blob/main/TERMS.md), authorization revocation guidance and clear identification of the source Russian audio/metadata versus translated display.

**A complete genuine screencast matters more than the suggested timestamps.** A terminal-based real local application is acceptable to demonstrate as terminal operation if that is truly its interface; do not present an HTML/mockup as a functioning production UI.

### 5.2 Recording and handling contract

- Capture a real continuous screen demonstration using a screen recorder (OBS, system capture or another legitimate recorder), with audible narration or legible explanatory subtitles. If edits are required to redact secrets, preserve the order of events and note the redaction.
- Verify 1280×720 or better, readable terminal text, no private popups/notifications, no credentials, no private viewer identities, no full account IDs, no private customer information. Stop and redact if a token is exposed; do not put screenshots of secrets into Git, chat or a public cloud folder.
- Keep raw recording, sanitized final MP4, checksums, a short step-to-timecode index and reviewer URL **outside Git**, in the operator's approved working folder. Prefer a restricted-link Google Drive file or an unlisted video with explicit reviewer view access; independently test link visibility before replying.
- **Never** replay uncertain provider operations, reset a working OAuth account, create extra Cloud projects to evade quota, or force a test upload/publication just for this demonstration. Preserve other agents' worktrees and existing multi-project journal/lock rules.
- If current quota or remote computer is unavailable, retain **blocked** status and make the next action restore authorized desktop access, record the current version and historic verified artifacts, then obtain the quota-safe live component. Do not assert the demonstration has been recorded or supplied in the interim.

### 5.3 Response plan

Reply directly to Google's existing YouTube API Services thread, with:
- one accessible URL to the **actual** complete screencast;
- an optional compact timestamp index and what part shows metadata, captions, OAuth and readback;
- a transparent note that extra quota remains pending and the demonstration may show quota exhaustion;
- the same API-client name and numeric project number **only after actual Cloud Console cross-check**; otherwise avoid claiming the Cloud project number was independently confirmed.

Do not send a reply claiming a completed demo until the file is recorded, reviewed, uploaded and the link has been tested. After sending, verify the Gmail thread contains the outgoing response and document the response date, without copying private mail addresses or support tracking tokens into a public repo.

### 5.4 Current execution status

- Google request was **read and understood** from its full email body on November 13.
- Previous four static/combined screenshots were insufficient for this review.
- **Real screencast not yet recorded** and no reply supplying that screencast yet.
- Remote Desktop Commander **reported no connected devices** at the first attempt after receiving this email; the user's computer must reconnect before executing a screen recording on it.
- Exact end-to-end workflow and file assets can be prepared from existing repo runbooks and local verification receipts; do not assume every 2026-11-12 credential/working directory state still applies.
- Main technical blocker previously observed: `403 quotaExceeded` on a subsequent `videos.list`; no blind retries.

