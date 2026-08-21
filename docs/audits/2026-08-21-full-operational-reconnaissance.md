# Full operational reconnaissance — 2026-08-21

Status: read-only evidence  \nAudited `main`: `8955b2f5d481947560ab70ccc1c225e7b4de8337` (PR #506, 2026-08-20T19:59:00Z)  \nOpen PRs: **0**  \nOpen issues: **#503**, **#353**  \nProvider writes performed by this audit: **0**

This file is a current-tree reconnaissance. It does **not** authorize Instagram, Telegram, YouTube, VK, Dzen, Meta, GitHub-ruleset or any other provider mutation. Historical success, green CI, authorized-but-undispatched bundles and leftover branch names are evidence only.

Canonical live interpretation remains [`docs/operations/current-state.md`](../operations/current-state.md). Where this audit and that file disagree, treat this audit as a **drift report**, not a replacement — several current-state sentences are already stale (see §11).

---

## 0. How to read the cemetery of agent work

The last month produced ~354 merged PRs, ~64 closed-unmerged PRs and **137 remote branches**. Almost none of those branch names are unfinished product work.

Three completion kinds must stay separate:

| Kind | Meaning | Typical false signal |
| --- | --- | --- |
| Repository implementation complete | code/contracts/tests merged on current `main` | leftover `agent/*` branch still exists |
| Artifact complete | exact bytes/hashes exist under the current provenance contract | JSON “candidates” without media SHA-256 |
| Provider rollout complete | one authorized remote mutation was verified | `execution_authorized=true` file that was never dispatched |

Agents repeatedly stopped at 50–90% because the remaining 10–50% was **local OAuth / Takeout / vertical render / human `workflow_dispatch`**, not more Python. The repository then correctly refused to fake that last mile.

---

## 1. What this repository actually is

`video-channel-manager` is a safety-first modular monolith for three **separate** owner projects. It is not a social-media autoposter and not a YouTube→VK script.

Observed size on current `main`:

| Surface | Count |
| --- | ---: |
| Python sources under `src/` | 298 files / ~78.9k lines |
| Tests | 374 `test_*.py` / ~62.3k lines |
| GitHub Actions workflows | 24 |
| `docs/operations/` files | 133 |
| Remote branches | 137 |
| Merged PRs | 354 |
| Closed issues | 86 |
| Open issues | 2 |
| Open PRs | 0 |

Default posture: read-only, exact IDs, no guessed objects, no blind mutation retry, one writer per durable namespace, credentials authenticate but never select the project.

Three registered projects ([`project-identity-registry.md`](../operations/project-identity-registry.md)):

| `project_key` | Public name | YouTube | Telegram | VK community |
| --- | --- | --- | --- | --- |
| `lord-god-strength` | Господь Бог — Сила Моя | `@fedormilovanov` `UCeSJsC6go2c9pdJCuUI1BYA` | `@lordchrist` | `60805374` |
| `legendary-poet` | The Legendary Poet | `@TheLegendaryPoet` `UC-78ys2S3cQ3lpqgXfo-SvQ` | `@thelegendarypoet` | `235216998` |
| `milovi-cake` | Milovi Cake | `@milovi_cake` `UCMDnxfGZiBqcDzgUV1zjFpw` | `@MiloviCake` | `68859909` |

Shared Telegram bot `8716602202` / `@preaching_mp3_bot` is intentional. Shared VK user token alias `legendary-poet` is authentication, not a project selector.

---

## 2. Live vs paper — one-page matrix

| Lane | Repo code | Artifacts | Live provider | Current owning scope |
| --- | --- | --- | --- | --- |
| YouTube «Чёрный человек» album | complete | historical published bytes | **live** `x-puy27S2qs` | closed; no replay |
| YouTube comments / copy executors | complete | historical | historical | no standing write |
| VK Milovi native Clips #323 | complete | 12/12 allowlisted | **live / closed** | do not reopen as “missing uploads” |
| LordChrist Telegram **quotes** | complete | queue + ledger | **live 1/day 09:17 MSK** | no new scope; catch-up 21:17 is quota-only |
| LordChrist Telegram **rich articles** | complete | 1 live canary | **live msg 1484**, second article inert | closed #473 |
| LordChrist Telegram **Shorts** | complete + hardened #502/#504/#505 | **no fresh inventory, no owner MP4s** | **0 native videos** | **open #503** |
| Svodka Telegram rich | complete, one-shots retired | 2 verified msgs 28/29 | **stopped on purpose** | no new mutation |
| Milovi Telegram control plane | complete #486–#500 | 16/16 video artifacts; 12-item marathon copy | **1 historical canary msg 26; marathon item 1 never sent** | **open #353** |
| Instagram Poet + Lord God | content system merged #493 | 9+9 launch packs, 59 Reel jobs, 111 historical IDs | **0 posts, 0 Reels, no account IDs, no publisher** | #492 closed as *implementation*; live rollout never started |
| Dzen Milovi | none | none | **0** | named in #353, not engineered |
| GitHub branch protection | probe only | — | `main` `protected=false`, rulesets `0` | #443 closed `not_planned` |
| Resi / local MP3 | complete | local-only | provider effect `impossible` | no remote |

The user’s two sharp observations are correct:

1. **Instagram: nothing was uploaded.** Not a hidden failure — the merged work was designed to stop before Meta.
2. **Господь Бог Shorts were not loaded into Telegram.** Same pattern: #501/#502 built the inert lane; #503 still needs a fresh owner YouTube scan + Takeout/local masters.

---

## 3. Instagram — why “nothing loaded”

Owner issue #492 is **closed** (2026-08-20, PR #493). That close means *repository content system complete*, not *Instagram has a feed*.

What exists:

- Canonical Instagram caption renderer (`reel` / `feed` / `carousel`).
- Launch packs:
  - Poet `@the.legendary.poet` — 9 candidates in `content/instagram/legendary-poet-launch-candidates.json`;
  - Lord God `@thelordgodismystrength` — 9 candidates in `content/instagram/lord-god-strength-launch-candidates.json`.
- Reel factory: 59 jobs, baseline `40 source_led_ready / 8 quote-blocked / 8 source-unbound / 3 materialization`.
- Historical floor: 111 YouTube↔VK IDs, of which 96 still need editorial records.
- Read-only Graph identity client (`InstagramFacebookIdentityClient`) — discovers Professional account IDs, does not publish.
- Analytics *schema* only.

What does **not** exist:

- exact Instagram Professional account IDs (`provider_account_id: null` in both packs);
- Meta publishing executor / workflow;
- vertical MP4/Reels bytes + SHA-256;
- selected clip timings against clean masters;
- exact canonical edition/span for quote Reels;
- any GitHub Action that talks to Instagram write APIs.

Every backlog row is `PROVIDER-BLOCKED` by design. Handles are display hints, not operational IDs.

Remaining Instagram work, if ever requested as a new exact scope:

1. prove exact Professional account IDs (Facebook Login read);
2. bind those IDs into the registry (not by handle);
3. render/hash vertical masters for the first 3–6 identity pieces;
4. only then a separate write-authorized publisher.

Until that happens, Instagram remains a content warehouse.

---

## 4. Господь Бог Shorts → `@lordchrist` — why they did not load

### 4.1 What is live today on `@lordchrist`

The **quote** publisher `.github/workflows/lordchrist-telegram-poster.yml` is a real scheduled writer:

- 09:17 and 21:17 Europe/Moscow;
- `daily_verified_limit=1`;
- production config `enabled=true` since 2026-08-08;
- durable state `state/lordchrist-telegram` (head `d44b296`, last result `2026-08-20T07:05:10Z` for run `32342356455` — the 09:17 slot).

The 21:17 run `32406598101` (2026-08-20T19:03:32Z) concluded **success** but skipped `sendMessage`. That is the designed catch-up: prepare returned “no eligible next publication / today’s quota used”. Quotes are not stuck; Shorts were never on this workflow.

Rich article canary «Перо, стенографист и магнитная лента» is complete (Telegram message `1484`). Second rich article remains provider-inert. One-shot rich controllers were retired.

### 4.2 Shorts lane — implementation 100%, artifacts ~10%, provider 0%

Closed #501 / merged #502/#504/#505/#506 built a provider-inert pipeline:

```text
youtube scan (read-only, fileDetails required)
→ snapshot readiness (max age 48h)
→ inventory (short | candidate | excluded)
→ owner Takeout/local SHA-256 bindings
→ local FFmpeg Telegram-ready MP4
→ complete state materialization
→ unauthorized release preview (17:17 MSK, oldest first)
```

Policy `content/telegram/lordchrist/shorts-feed-policy.json` hard-codes:

- `automated_youtube_download_allowed=false`
- `telegram_provider_mutation_allowed=false`
- `telegram_stories_enabled=false`
- slot `17:17`, four-hour gap from 09:17 / 21:17

Open **#503** owns the missing artifact wave. Historical owner AuditPackage `2026-07-29` has 1826 records / 25 post-cutoff ≤180s IDs, but **no `fileDetails` / `videoStreams`**. Those 25 IDs are reconciliation candidates, not proven Shorts. The classifier correctly refuses to treat them as an empty-or-complete inventory.

Blocker is environmental, not code: this session has no `fedor-milovanov` OAuth runtime and no Takeout/local masters. Next legal step is local:

```bash
video-manager youtube scan --account fedor-milovanov --channel UCeSJsC6go2c9pdJCuUI1BYA
python -m video_channel_manager.lordchrist_shorts inventory --audit <fresh.json>
```

No Telegram Story, MTProto, YouTube download helper or `sendVideo` is in scope of #503.

### 4.3 Phantom Shorts-quality failures

`.github/workflows/lordchrist-shorts-quality.yml` is `pull_request` (path filter) + `workflow_dispatch` only. Recent `main` **push** runs (including #506 run `32411608353`) conclude `failure` in 0s with **0 jobs**. That is empty-check-suite noise, not a Shorts test failure. Full `CI` / Pillow / Svodka / Milovi quality on the same SHA were green.

---

## 5. Milovi Cake Telegram — authorized on paper, never dispatched

Issue **#353 remains OPEN** on purpose: engineering/control-plane is complete; growth/publication operations are not.

### 5.1 What is actually on `@MiloviCake`

- Historical live canary `milovi-canary-20260818-002` = Telegram message **26**. Authority consumed, non-replayable.
- Durable state `state/milovi-cake-telegram` last commit `2026-08-18T19:42:53Z` — bootstrap retirement, **no feed ledger for 20260820-***.
- `.github/workflows/milovi-telegram-feed-publisher.yml` is the only writer. Trigger: **manual `workflow_dispatch` only**. GitHub Actions run list for this workflow: **[]** — zero initialize-state, zero publish, zero validate.

### 5.2 The 20:00 MSK miss (exact)

PR #500 froze marathon position 1 as `milovi-feed-20260820-002`:

| Field | Value |
| --- | --- |
| slot | `2026-08-20T20:00:00+03:00` |
| operation | `sendPhoto` / media `p06` |
| `release_authorized` | true |
| `execution_authorized` | true |
| `provider_mutation_allowed` | true |
| max attempts | 1 |
| publisher lag gate | `MAX_PUBLICATION_LAG_MINUTES=120` |

Nobody ran `initialize-state` then `publish`. By 2026-08-21 that identity is past the 120-minute freshness window. Repository rule is explicit: **do not retime or catch up**. A future photo, if wanted, needs a **new** `milovi-feed-YYYYMMDD-NNN` for a current daylight slot.

`milovi-feed-20260820-001` (10:30 MSK, `p16`) and `milovi-feed-20260819-001` remain unauthorized / stale history.

`docs/operations/current-state.md` still calls `20260820-001` “the current exact candidate”. That sentence is **wrong** after #500. See §11.

### 5.3 Marathon remainder

Canonical sequence `content/telegram/milovi-cake/marathon-wave-2026-08.json`: 12 items (9 Cake photo + 3 School text at positions 3/7/11). Wave-level `publication_authorized=false`. Only position 1 was ever given a dated identity, and that identity expired unused.

16/16 accepted H.264 artifacts live on preserved branch `agent/milovi-video-accepted-73c578eff825`. They are not in this marathon and create no `sendVideo` authority.

Dzen, invite links/QR, paid placements, life/BTS: named in #353, **not started**.

---

## 6. Closed lanes that must not be “resumed”

Treat these as finished unless a **new** exact issue is opened:

| Lane | Evidence | Trap |
| --- | --- | --- |
| Svodka rich | msgs 28 + 29 verified; 14-entry August ledger terminalized `skipped/impossible`; one-shots retired | old `pending` rows look like a backlog |
| LordChrist research-v2 | #286 `retired_no_replay` | any other `may_exist` still fail-closes the channel |
| VK #323 Milovi Clips | 12/12 native uploads + wall mappings | old issue text saying `8/12` |
| YouTube Black Man | public `x-puy27S2qs` | regenerating the album “to satisfy later policy” |
| Instagram #492 | content system | “issue closed ⇒ Instagram is live” |
| Shorts #501 | code | “issue closed ⇒ Shorts are posting” |

---

## 7. Branch cemetery — 137 refs, almost no unique work

[Hygiene audit 2026-08-19](../operations/branch-hygiene-audit-2026-08-19.md) aligned 111 ephemeral refs to then-`main` `fb2a8c0`. Current `main` has since moved to `8955b2f`, so those refs are now **stale pointers to old main**, not active branches. Ref deletion was unavailable to that agent.

### 7.1 Keep (durable or unique evidence)

| Ref | Why |
| --- | --- |
| `main` | only code/runtime baseline |
| `state/lordchrist-telegram` | live quote ledger |
| `state/svodka-telegram` | terminal Svodka ledger |
| `state/milovi-cake-telegram` | Milovi durable state |
| `agent/milovi-video-accepted-73c578eff825` | 16/16 content-addressed video proof |

### 7.2 Historical diverged (do not execute from)

Closed/superseded PR heads, useful only as lineage:

- `work/lordchrist-rich-media-binding`, `...-v2` (superseded by #472)
- `work/svodka-reconciliation-diagnostics` (closed #465)
- `work/svodka-retire-completed-rich-oneoffs`, `...-v2` (superseded/rejected; accepted path is #480)
- `work/svodka-rich-successor-activation` (superseded by #460)
- `agent/milovi-post486-ci-repair` (closed #489)
- `agent/milovi-oneoff-canary-20260818` / `-v2`

### 7.3 Noise clusters (same SHA, many names)

Typical agent-crash signature — parallel retries of the same job:

- `agent/issue-323-golden-path-hardening-{2,final,final2,final3,main,real,real2,stop,x}`
- `agent/youtube-release-executor-rebased-{backup,final,merge-target,pr,pr2,stage,temp,work}`
- `agent/milovi-telegram-live-canary-{actual-pr,ci,final,pr,pr-ready,review-anchor,...}` (~14 refs still on `eac58db`)
- `tmp-do-not-use`, `tmp/noop`, `tmp-never-use`, `noop-audit-temp`
- old `arena/019fc79b-…`, `arena/019fed75-…`

These are not 50% features. They are abandoned scratch names. Safe cleanup is delete-or-fast-forward-to-current-`main` **except** the five keep-refs above. Never rewrite a `state/*` ref as hygiene.

---

## 8. Where agents actually fell over (recurring failure classes)

From current-state, postmortems and the last two weeks of PRs:

1. **Implementation vs artifact vs provider collapsed into one “done”.** Instagram and Shorts are the textbook cases.
2. **Missing last human gesture.** Milovi #500 produced a fully authorized bundle; nobody pressed `workflow_dispatch`. The lag gate then killed the identity.
3. **No local owner runtime in the agent sandbox.** #503 cannot finish without `fedor-milovanov` OAuth + Takeout/MP4s that must not be pasted into chat.
4. **Stale issue bodies reused as live truth.** #323 `8/12`, Svodka `pending`, README still talking about open #154/#232.
5. **Duplicate writers against one namespace.** The whole Milovi/Svodka/LordChrist architecture exists to stop this; leftover `follow-on-*` / one-shot workflows were retired for that reason.
6. **CI ceremony loops.** `#505` contains `noop` and “remove accidental out-of-scope file” commits; `#489` vs `#488` is a closed duplicate CI repair.
7. **Docs not updated when the runtime moved.** `current-state.md` missed the #500 → `20260820-002` transition; `README.md` and `docs/operations/README.md` still describe the Wave-16 / #154 world.

---

## 9. Documentation drift (high-signal)

| File | Drift |
| --- | --- |
| `docs/operations/current-state.md` | Same-day follow-up: Milovi paragraph now records `20260820-002` authorized-never-dispatched and forbids catch-up; Instagram #492 recorded as implementation-complete with 0 publications. |
| `README.md` | Same-day follow-up: status block no longer treats #154 as artifact-open. |
| `docs/operations/README.md` | Same-day follow-up: start-here now points at this reconnaissance; Wave-16 registers remain historical. |
| `docs/roadmap.md` / `automation-backlog.md` | Closed August-5 program; later Telegram/Instagram work is still invisible there on purpose. |
| `content/telegram/AGENTS.md` | Same-day follow-up: overlay now defers to `current-state.md` and marks the August-8 Svodka activation block historical. |
| `docs/operations/unified-integration-status.md` | 2026-07-25 draft PR #13 history. Archaeology only. |

`AGENTS.md` read-order is still correct: `current-state.md` first — but that file now needs a small Milovi memory sync before it can be trusted on #353.

---

## 10. GitHub / CI hygiene

- Source `main` is **not protected**; ruleset count **0** (#443 closed, admin mutation surface missing).
- Required CI on current `main` after #506: Python 3.11/3.12/3.13 CI green; PowerShell matrix green; Pillow and Svodka/Milovi quality green.
- `lordchrist-shorts-quality.yml` empty-job `push` failures pollute the Actions dashboard (§4.3).
- Svodka `svodka-scheduled-publisher.yml` still exists as “legacy publisher (manual recovery only)” and last scheduled ~9 days ago; do not treat those successes as new posts.
- Shared secret name `LORDCHRIST_TELEGRAM_BOT_TOKEN` is mapped into Milovi as `MILOVI_CAKE_TELEGRAM_BOT_TOKEN`. Intentional, not cross-project contamination — isolation is `chat_id` + profile + state branch.

---

## 11. Next safe work (priority, still unauthorized)

Nothing below is execution authority. It is the smallest honest queue.

### P0 — truth repair (repo-only)

1. Sync `docs/operations/current-state.md` Milovi paragraph: `20260820-001` stale; `20260820-002` authorized, never dispatched, now non-catch-up; publisher run count 0.
2. Stop treating README / Wave-16 / `content/telegram/AGENTS.md` as live status.
3. Optional branch hygiene: delete ephemeral refs aligned to old `fb2a8c0` / `eac58db` once a tool can delete refs; preserve the five keep-refs.

### P1 — if the owner wants Shorts on `@lordchrist`

Stay inside **#503** (`official_api_read` + `local_only`):

1. On the machine that already has `fedor-milovanov` OAuth, take a fresh `youtube scan` of `UCeSJsC6go2c9pdJCuUI1BYA`.
2. Run snapshot-readiness + inventory.
3. Bind only Takeout/local masters by `youtube_video_id` + SHA-256.
4. Keep release preview `release_authorized=false`.
5. A later Telegram `sendVideo` writer needs a **new** issue.

### P2 — if the owner wants Milovi Telegram growth

Stay inside **#353**, permanent writer only:

1. Do **not** publish `milovi-feed-20260820-002` now (lag exceeded; no-catch-up).
2. Promote marathon position 1 under a **fresh** identity for a current 10:30 or 20:00 MSK slot.
3. Separate release authorization, `initialize-state`, then one `publish`.
4. Positions 2–12 have no standing authority.
5. Dzen remains a later measured experiment.

### P3 — if the owner wants Instagram

Needs a **new** issue (do not reopen #492 as a writer):

1. Exact Professional account IDs.
2. Vertical masters for Poet P01–P06 and Lord God G01–G03.
3. Only then a guarded Meta publisher.

### P4 — do not do

- Blind-retry any Telegram/VK/YouTube/Instagram call.
- Catch up stale `milovi-feed-*` identities.
- Download YouTube as convenience masters for Shorts or Reels.
- Invent poem/Scripture quotes or clip timestamps.
- Execute from `state/*`, `work/*`, or old `agent/*` branches.
- Reopen #323 / Svodka / Black Man / rich canary because an old comment looks incomplete.

---

## 12. Bottom line

The repository is a mature, over-governed control plane with three live-or-closed media projects and a large paper factory in front of Instagram and LordChrist Shorts.

**What is really on the air**

- `@lordchrist` quote of the day (09:17 MSK);
- one LordChrist rich article (msg 1484);
- `@MiloviCake` historical canary (msg 26) and nothing from the 12-item marathon;
- Svodka stopped after two verified rich posts;
- historical YouTube/VK rollouts that must not be replayed.

**What the unfinished branches mostly are**

Scratch names. Unique unfinished *product* work is not hiding in those refs.

**What is genuinely unfinished**

1. Instagram: 0 live posts; content system only.
2. LordChrist Shorts: 0 Telegram videos; blocked on fresh owner inventory + media.
3. Milovi marathon: item 1 authorized 2026-08-20 20:00 MSK and never dispatched; identity now stale.
4. Dzen / Instagram publishers / GitHub branch protection: not built or not available.
5. Operator docs (`current-state`, README, Telegram AGENTS overlay) have drifted behind `main`.

The next useful agent hour is either a **docs truth-sync**, a **local #503 YouTube scan**, or a **fresh Milovi identity for a current slot** — each as its own exact scope, never as a catch-up of yesterday’s files.
