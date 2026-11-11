# Lord God YouTube: evidence-led description repair

This is the durable operating guide for the lord-god-strength YouTube project. It does not grant standing provider write permission. Resolve the user's current request and the exact operation's authorization first. Owning legacy-description issue: https://github.com/FedorMilovanov/video-channel-manager/issues/795. Older issue comments are evidence, never current state.

## Runtime provenance, OAuth directory and agent handoff

- Resolve the exact current remote `main` SHA; inspect the source checkout's
  `git rev-parse HEAD` and `git status --short` before importing the program.
  A dirty, behind-main shared Windows checkout is **not** an execution source.
  Create a fresh isolated read-only/working clone or clean worktree and confirm
  that `video_channel_manager.cli.youtube.__file__` resolves to its `src`.
  A globally installed editable `video-manager` may still import code from
  a much older local directory even when the current repository is correct.
- `VCM_DATA_DIR=./data` is **relative to process CWD**. First identify the
  established owner's token directory without reading or copying secret bytes,
  then set `VCM_DATA_DIR` to its verified absolute parent data directory for
  all agents/CLI calls that need the same OAuth identity **and write lock**.
  Set `VCM_YOUTUBE_CLIENT_SECRET_FILE` to the verified absolute client JSON
  path only when necessary. The current `youtube accounts` command prints
  its resolved storage location; older locally installed versions may not.
  Never launch another Google login as a shortcut for a missing relative store.
- Only the canonical `fedor-milovanov` alias and a fresh owner
  `channels.list(mine=true)` proof bind this channel. Local `write` scope is
  necessary but is **not** proof of a matching channel or live mutation.
- Read the latest independent owner evidence and terminal receipts from issue
  #795 and the exact E: paths and SHA256 digests in its newest handoff.
  Historical clean counts, offline QA, staged correction drafts, receipts and
  unsigned plans are different evidence classes. A `shelf_id`-clean video can
  still be missing source credits and old contact cleanup.
- The historical source audit of the last 89 completed description edits
  found omissions requiring a separate **retrospective** review. Never treat
  the 53 community-link drafts, 19 other source drafts, or 10 Spurgeon drafts
  as provider-ready; no draft may update an already edited video without a
  fresh owner/title/before-description match and its own newly signed plan.
  Preserve malformed/truncated historical links as HOLD instead of inventing
  the omitted URL, and verify external channel attribution and playlist
  owner/membership before adding or removing links.
- `quotaExceeded` is a hard stop, not a reason to rotate OAuth accounts or
  projects. Use an offline-only review until the documented Pacific quota
  date changes, then run a bounded owner GET once; never repeatedly poll the
  provider to discover that the quota is still exhausted.

## Exact target and identity

- Project key and link profile: lord-god-strength.
- Owner YouTube channel ID: UCeSJsC6go2c9pdJCuUI1BYA.
- OAuth alias: fedor-milovanov. Verify the exact returned channels.list(mine=true) ID and granted write scopes; the alias alone proves neither.
- One video per signed description plan. Metadata-only descriptions: do not reupload video, rewrite the title or visibility, change audio/captions, or touch other channels.
- A clean count based only on absence of old shelf_id links does not certify source rights, factual accuracy, contact cleanup or SEO. Never report a historical or estimated count as a new owner-API scan.

## Recurring agent bugs and their fixes

**Two plain share-preview lines (8 Nov 2026 audit):** MP3Bot `docs/agent_direct_dubbing/CLIPS_SHORTS_AND_HANDOFF.md` and actual Lord God long-form videos establish that the first TWO nonempty raw Studio lines—not merely the first paragraph—must be unformatted substantive text, with no links or list headings. Some historical videos do not meet this standard; this is a future-publication gate, not permission to edit historical videos en masse. Use `presentation_issues()` on each exact proposed description before OAuth/API. Do not mark a copy ready if line two begins with a bold heading or has inline markers, even when the old generic `youtube_copy` first-paragraph check returned no errors.


**Raw versus prefixed SHA-256:** Python hashlib.sha256(text.encode("utf-8")).hexdigest() returns 64 hexadecimal characters. The signed-plan helper video_channel_manager.platforms.youtube.copy_plan.sha256_text(text) returns the literal prefix "sha256:" plus those characters. Validate archival raw digests using hashlib; validate signed plan before_sha256 and after_sha256 using sha256_text. Never disable hashes to overcome a representation mismatch.

**Read-only recovery is not publication:** `youtube reconcile-copy-fixes`
must accept structurally valid, hash-bound historical plans even when they
violate today's stricter formatting or source-preservation publication policy.
It does not write, approve, or authorize replay. `apply-copy-fixes` still
fails closed on the current publication gate. Lord God write preflight also
checks the frozen video title against the current owner title before any PUT;
other projects retain their general title semantics.

**Script restart:** Before anything, inspect exact plan IDs, existing immutable backups, terminal receipts and active processes. A stopped script that signed 20 plans but did not write must resume from those exact validated plans, not sign over them. After any provider dispatch, reconcile each video by an independent owner GET before resuming. An ambiguous or rolled-back write is not authorization for another PUT.

**Windows UTF-8:** Non-ASCII PowerShell here-strings sent over remote transport may turn Cyrillic into literal question marks. Write a UTF-8 Python/JSON file, verify the file content and SHA locally, then run python -X utf8. A malformed console display is not evidence that the underlying source document is corrupt.

**UTF-8 limit (12 Nov 2026):** YouTube Data API `videos.update` limits
`snippet.description` to **5000 UTF-8 bytes**, not 5000 Unicode characters.
`presentation_issues()` rejects an after-description that exceeds
`len(description.encode("utf-8")) > 5000` with
`description_over_5000_utf8_bytes`, before OAuth/API access. Do not silently
truncate or delete credits/chapters/source URLs to fit; rewrite the draft and
re-sign it. Read-only `reconcile-copy-fixes` remains able to inspect older
structurally valid signed plans, regardless of current publication styling.
Source: https://developers.google.com/youtube/data/reference/rest/v3/videos .

**Retired bank-card appeal regression (12 Nov 2026, issue #795):** A
previously approved ShepCon 2020 paragraph solicited support using a
16-digit bank-card number *before* a parenthetical Sberbank label. Earlier
checks only caught bank-prefixed numbers and missed seven signed releases.
A new Lord God description must reject a payment-solicitation line with
a 16-digit card number irrespective of whether the bank appears before or
after that number. Such a line is not a translator credit or sermon source
and may be removed in a new independently signed one-video correction,
while all genuine original credits, playlist IDs and links remain preserved.
Do not reapply old signed plans or infer that any live video is already
corrected; inspect a fresh exact owner readback first. Do not copy the
personal card number into repository source, tests or issue comments.

## Long-form editorial voice: natural language, not metadata labels (10 Nov 2026)

These are **forward-looking authoring rules** for Lord God YouTube long-form descriptions, not an instruction to re-edit old live descriptions. Shorts have a separate unfinished workflow. Do not retrospectively republish approved videos solely to change their tone.

- **No bureaucratic speaker/format/topic cards.** Do not append `*Выступающий:* Джон МакАртур`, `*Автор:*`, `*Формат: вопрос и ответ`, `*Тема:*`, or similar redundant administrative fields to a new description. The title and natural opening prose already establish who speaks and what the video is about. Preserve a genuine original translator/copyright/source attribution from the previous description when necessary: that is provenance, not an excuse to invent a speaker card.
- **Original links stay simple.** For a confirmed English recording, use exactly the short human-facing label `Англоязычная запись:` followed by its plain URL on the next line, without extra platform, speaker, publisher, or runtime metadata. In particular, do **not** write `Англоязычная запись Grace to You, 3:14:` or `(17:33)`: these durations may be interpreted as clickable video timestamps. Keep genuine pre-existing chapter timestamps intact; do not introduce a duration as a chapter.
- A Russian dub or translator's upload is **not** an English original: identify it accurately as `Русская версия:` or with the existing precise translator credit, followed by the URL. Never invent or mislabel primary recordings. Retain rights/source evidence and the original label when the preservation gate requires it, without layering unnecessary explanations into the viewer-facing copy.
- **Playlist headings describe the *subject*, not the age of a link.** For verified Q&A collections use `Вопросы и ответы:` and the playlist URL(s). Never call them `Исторические плейлисты`, `Архивная навигация`, or imply they contain historical material merely because the URLs came from an old description. For other playlists use their verified real names when known; otherwise the neutral `Другие плейлисты:`. Do not claim the video belongs to a playlist unless the owner listing confirms its membership. A legacy link that must be preserved but has uncertain relevance remains under a truthful neutral label, not a fabricated category.
- Avoid generic field-by-field summaries. Start with two plain, substantial preview lines, then write coherent, human-readable paragraphs, selective YouTube `*bold*` and `_italic_` emphasis, and only links that add value. Do not duplicate title metadata in a closing list.

**Before signing any new copy plan:** check for all forbidden template labels and stray duration strings, verify exact playlist names and membership when asserted, verify that `Англоязычная запись:` really links to an English recording, and run both the source-preservation and presentation gates. The preservation gate is stronger than stylistic preferences: do not delete a historical credit or non-retired source URL just to make the copy shorter. Resolve any conflict editorially before signing a plan. Neither these rules nor this documentation change authorize new provider writes.

Example, without a simulated runtime:

```text
Англоязычная запись:
https://www.youtube.com/watch?v=X65vspiZLLA

Вопросы и ответы:
https://www.youtube.com/playlist?list=VERIFIED_PLAYLIST_ID
```

## Editorial source retention

Study the exact original video title and owner description and a meaningful portion of its transcript. Do not invent Bible references, historical quotes, timecodes or speakers from a few keyword hits. When reading an old historical sermon, distinguish its original author from a modern narrator or translator.

The Lord God project presentation gate now calls the pure function source_preservation_issues(before, after) before provider OAuth. It fails closed if any of the following old, non-obsolete evidence disappears from the proposed new description:

- Original chapter lines and their exact question/topic labels, including stamps in h:mm:ss format.
- Original translation, attribution, copyright, or primary-recording/source-credit lines.
- Primary-source links, independent video URLs, specific Telegram posts and other non-retired references.
- Original YouTube playlist IDs even if the URL scheme or query parameter ordering changes.

This is a preservation gate, not a rights grant. Original links must still be checked for relevance, availability and licensing. Actual playlist owner and exact video membership must be verified by official API, including several valid playlists in one video. Playlist mismatch or source uncertainty is a HOLD; do not silently delete an unverified link or invent membership.

The only automatically exempt links are proven obsolete owner channel shelf/navigation URLs, retired personal contact URLs and retired donation endpoints. An **exact registered owner-community** link `https://vk.com/the_lord_god_is_my_strength` may also be replaced by its canonical `https://vk.ru/the_lord_god_is_my_strength` route. This does **not** apply to VK videos, posts, unknown communities, similarly named paths or links containing query parameters; they remain preservation HOLDs. A second exact owner-only exception is the retired VK fundraising widget `https://vk.com/the_lord_god_is_my_strength?w=app5727453_-60805374`, which the longform presentation gate already forbids. Remove that precise legacy payment URL from future descriptions without broadening the exception to any other VK query, wall post, video, or app route; tests must enforce this exactness. Every other URL needs preservation or a documented editorial decision. All third-party source/media rights remain separately reviewable.

## Offline next-wave checkpoint (zero YouTube API calls)

Use the supported `scripts/lord_god_wave_checkpoint.py` for **candidate discovery only** before drafting a new wave. It consumes an exact full owner-scan JSON, the SHA-verified original archive SQLite DB (read-only), and an explicit per-owner HOLD JSON ledger (`{"owner":"<exact channel ID>","ids":["<video ID>",...]}`). Provide `--owner-scan`, `--archive-db`, `--expected-archive-sha256`, `--holds-json`, `--historical-holds-report`, `--expected-historical-holds-sha256`, `--output` and `--limit 25` (1-50). The historical source is the independently validated `LORDGOD-NEXT100-OWNER-READONLY-PROVENANCE-V3-AFTER-RESET-20261107.json` report; its exact owner, count, 43 review HOLDs, read-only status and SHA are validated and merged with the explicit ledger. This prevents accidentally selecting the earlier 43 blocked IDs when an operator provides only the newer partial HOLD list. The output file must not exist; the tool will not overwrite evidence.

It refuses a scan with duplicates, intersecting clean/dirty sets, missing IDs, regressions, wrong owner or inconsistent counts. It excludes known HOLDs and videos lacking substantial archived transcript evidence. It prioritizes the remaining candidates using **archived** views, carries exact source SHA, verbatim archived URL/chapter/possible-credit evidence and three real transcript excerpts, and writes a provenance-bound machine-readable editorial checkpoint. It imports no YouTube client and performs no network or browser operations. A historical owner scan is not a fresh live snapshot.

**Safety boundary:** All emitted candidates are `EDITORIAL_REVIEW_ONLY`: no publication approval, no signed plan, no live owner proof, no rights grant. A HOLD ledger may be incomplete; independently reconcile the full editorial HOLD registry before any execution. Review original chapters, provenance, translator credits, external links and actual playlist membership. Only then perform a fresh official owner GET and proceed through the separately authorized guarded single-video workflow below. Never use headless YouTube Studio to evade provider quota or to replay uncertain writes.

## Bounded, evidence-led big waves

1. GET-only owner inventory. Reconcile the exact original cohort; exclude already-clean, ambiguous-write, rollback and special-source/title/playlist-held IDs. Do not depend on an old list without checking fresh live state.
2. Choose 20-50 distinct candidates by popularity, related series and transcript quality. Read the source evidence and prepare individual descriptions. Keep all source material, working links and existing chapter timestamps.
3. Fresh official owner preflight: channels.mine, videos.list in up to 50 IDs per call, owner/public/current title, exact original-before raw SHA, and every archived playlist's channel ownership and actual membership. A title or SHA drift blocks that video.
4. For each approved video generate one signed v3 plan, exact current before/after text and hashes, unique immutable backup and receipt filenames. Run the project presentation and source preservation validators.
5. Dry-run ALL approved plans before the first mutation. Require Ready: 1 and no unexpected revision drift. Do not relax the rules to force a green run.
6. Execute only one video at a time using official protected CLI. On ReadTimeout, ambiguous outcome or failed postflight STOP. Independently reconcile exact after, exact safe-original rollback or never-attempted state. Never blindly repeat a timed-out upload/write.
7. Independently read back all attempted IDs and the full original video cohort; report observed clean/dirty, old shelf link occurrences, old operator contacts, missing IDs, unexpected clean IDs, regressions and remaining editorial holds. A wave is complete only after reconciliation.

## Agent handoff and branches

Use the current supported main code in a clean isolated worktree. Do not modify other agents' shared Windows checkout. For a code or documentation fix, use one focused PR, run tests, merge and retire the ephemeral work ref. Keep machine reports and signed plans on the authorized E: work area or the operator's explicitly selected folder; cite exact file paths and digests in the owning issue. Local scratch scripts alone are not a durable repository fix.

Adding a new source module must also update docs/operations/coverage-ratchet.json with a measured module floor. The repository enforces exact package/file coverage; never lower existing floors.

Regression tests (offline, no provider calls):

    python -m pytest -q tests/test_lord_god_presentation.py tests/test_lord_god_source_preservation.py tests/test_youtube_copy_execution.py tests/test_youtube_copy_reconciliation_cli.py tests/test_youtube_login_scope_guard.py
