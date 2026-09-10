# Branch salvage audit — 2026-09-11

This is a point-in-time historical audit. It does **not** replace `AGENTS.md`,
`docs/operations/current-state.md`, an owning issue, or current provider execution
authority.

Snapshot baseline: `main@254d90c8b0b72774dcb798e5b176cacb83288561`.

Provider calls/writes performed by this audit: **0**.

## Active / do not take over

### `agent/vk-flood-video-wave-594`

Active implementation branch for Issue #594 and PR #604. At the pre-write audit
snapshot it was based on current main with no behind commits and continued to move
during the audit. It owns the Legendary Poet YouTube -> VK flood-control/native-video
hardening lane. Do not start competing VK upload/wall/Wave work from another branch.

### Instagram Legendary Poet / Issue #581

Issue #581 is still an active provider/operator lane even when no long-lived
`agent/instagram-*` branch is visible. The latest repository correction, #605/#606,
was merged into current main and the real failed `-03` canary was then reconciled
read-only as terminal provider failure. Absence of an open Instagram PR therefore
must **not** be interpreted as free ownership of the live-canary lane.

## Durable refs that are not code-development branches

Keep these state refs as state-only baselines:

- `state/lordchrist-telegram`
- `state/svodka-telegram`
- `state/milovi-cake-telegram`

Never use them as code/runtime sources.

## Content-addressed evidence ref — retain

### `agent/milovi-video-accepted-73c578eff825`

Retain. This branch is intentionally referenced by current repository contracts as
the accepted 16/16 Milovi Telegram video reservoir. The current workflow instructions
bind `sendVideo` eligibility to this exact content-addressed ref and evidence digest
`sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`.

Its large behind count is expected and is **not** evidence that the branch should be
rebased, aligned to main, or deleted.

## Superseded refs with no unique current work

The following refs are behind current main and have zero commits ahead. They contain
no unique branch work to salvage and must not be used as execution/recovery baselines:

- `agent/instagram-facebook-state-sync-577`
- `agent/lordchrist-historical-editorial-552`
- `agent/lordchrist-slot-aware-production-20260906-v2`
- `agent/lordchrist-spurgeon-v3-live-media-561`
- `fix/instagram-resumable-phase-diagnostics`
- `lane/lordchrist-history-human-editorial-561-20260907-copy`
- `lane/lordchrist-spurgeon-v3-media-561-20260908`
- `research/lordchrist-calvin-spurgeon-macarthur-series-v1`

The ad-hoc aliases `do-not-use`, `final-accidental`, `oops6`,
`probe/lordchrist-historical-v3-final-sources-561`, `tmp-noop`, and
`zzz-test-ignore` also point at an old main ancestor and carry no separate current
implementation authority.

Where branch deletion is supported, these refs are retirement candidates. Where it
is not supported, root `AGENTS.md` permits aligning an ephemeral ref to exact
current main, but that mutation is deliberately outside this audit.

## Divergent historical refs

### `agent/lordchrist-historical-live-561`

The branch reports two commits ahead, but the material that looked unique has already
landed independently on main:

- `second-pass-2026-09-07.json` is the same audit payload on main; the branch copy
  differs only by a trailing newline.
- the Stam post payload is already present on main with the accepted wording.

No branch code/content should be merged wholesale. This ref is a retirement
candidate after ordinary provenance retention.

### `feature/lordchrist-successor-quote-corpus-v1-20260906`

Historical prototype only. Its `telegram_quote_successor.py` is an older, much
smaller predecessor of the current main implementation; current
`telegram_quote_runtime.py` imports the evolved main module and current successor
activation is already bound to release
`lordchrist-successor-quotes-v1-integrity-v2`.

Do not resurrect or cherry-pick this prototype.

### `fix/lordchrist-quote-handoff-576`

Historical handoff implementation. Current main already contains the successor
activation/runtime and later production safety work. The branch activation payload
matches the current release identity/target semantics but carries the superseded
owning issue. Do not merge the old workflow/runtime versions back over current main.

### `feat/lordchrist-historical-v3-archival-revisions-561`

Do **not** merge this branch wholesale and do not execute its acquisition workflow.

Its remaining unique files are preliminary phase-1 acquisition/probe evidence, not
missing production implementation:

- the phase-1 evidence explicitly says `artifact_complete=false` and records only
  three acquired assets;
- the probe manifest includes unfinished probe material, including a zero/placeholder
  upstream SHA for one candidate;
- current main contains the later
  `media-acquisition-manifest-v2-2026-09-09.json` and
  `media-render-receipt-v2-2026-09-09.json`, plus the evolved historical-media
  runtime used by the completed archival-v3 release.

Because those preliminary files are unique historical provenance, retain the ref
until a deliberate archival-retention decision is made. They are **not** a backlog to
finish and are not a source for provider execution.

## Decision rule for future agents

Before claiming work from any non-state branch:

1. compare it to exact current `main`;
2. inspect current open PRs/issues and recent issue comments, not branch names alone;
3. treat `ahead=0` as no salvageable code work;
4. treat an old divergent branch as historical evidence until unique changes are
   proven current and useful;
5. never infer that Issue #581 is free merely because an Instagram branch was merged
   and deleted;
6. preserve the Milovi accepted-video evidence ref exactly;
7. do not compete with Issue #594 / PR #604 while that lane remains active.

This audit authorizes no provider mutation and no branch deletion/force-update.


## Post-audit retirement actions

The point-in-time classifications above were followed by repository-only ref cleanup.
No provider or durable-state mutation occurred.

### Zero-ahead stale refs

Issue #609 fast-forwarded the audited zero-ahead stale refs to exact
`main@254d90c8b0b72774dcb798e5b176cacb83288561` with `force=false` after
fresh open-PR ownership checks. A follow-up applied the same proof to six inert alias
refs (`do-not-use`, `final-accidental`, `oops6`,
`probe/lordchrist-historical-v3-final-sources-561`, `tmp-noop`,
`zzz-test-ignore`). No unique commits were discarded.

### Semantically superseded divergent LordChrist refs

Issue #612 aligned exactly three divergent refs to that same current-main commit only
after semantic supersession and open-PR ownership were re-proved. Their retired tips
are recorded here so provenance remains addressable even though the branch names now
point to main:

- `agent/lordchrist-historical-live-561` retired tip
  `6ce072e9b1a3d23941dfaaecd78a419584ace1b0`;
- `feature/lordchrist-successor-quote-corpus-v1-20260906` retired tip
  `0fab4b04d23c8ef7d218fddd711fc3b597f3cb09`;
- `fix/lordchrist-quote-handoff-576` retired tip
  `9c50d9643442984770ac5c4f1f24f27cc815d23d`.

The retained archival-v3 provenance ref, Milovi accepted-video evidence ref,
protected `state/*` refs, active Instagram lane, and active VK lane were not
modified.
