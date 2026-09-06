# Branch hygiene control audit — 2026-09-06

Status: **provider-inert repository hygiene evidence**.

Owning tracker: #531.

Baseline used for this control pass:

- repository: `FedorMilovanov/video-channel-manager`;
- exact `main`: `adf87c56f0836c931dc524cc41f3e0f64adaa209`;
- `main.protected=false` at readback;
- repository rulesets: `[]` at readback;
- open pull requests at audit start: `0`;
- branch listing: `145` refs total across the complete GitHub branch listing;
- provider reads/writes authorized by this audit: `0 / 0`.

This document is an evidence ledger for branch deletion decisions. It does not authorize a provider mutation, a durable-state rewrite, or a force move of refs. A branch is not deletable merely because its name begins with `agent/`, `work/`, `feature/`, `fix/`, `tmp/`, or another prefix.

## Hard KEEP classes

The following refs are excluded from ordinary hygiene deletion:

- `main` — only supported repository runtime/code baseline;
- `state/lordchrist-telegram` — durable LordChrist state;
- `state/milovi-cake-telegram` — durable Milovi state;
- `state/svodka-telegram` — durable Svodka state;
- `agent/milovi-video-accepted-73c578eff825` — content-addressed accepted Milovi video evidence, explicitly referenced by the current operational contract;
- any other ref subsequently proven to be the sole durable home of unique artifact/evidence bytes or commits.

The active coordination ref `agent/lordchrist-quote-slots-20260906` is also **KEEP while its owning LordChrist slot/cadence scope is active**, even though its current tip is contained in current `main`. Hygiene must not race an active agent.

## Exact absorbed-tip proofs

The cleanup decision is based on exact commit ancestry, not branch-name heuristics.

| Exact tip | Relation to `main@adf87c56…` | Current verdict |
| --- | --- | --- |
| `fb2a8c099e352350d0ad38fadd91da8ae0ae07cd` | merge base is the tip; `main` ahead by 63, behind by 0 | absorbed; branch refs at this exact tip are deletion candidates unless evidence/runbook role says KEEP |
| `eac58db5aced0c08294f14d0cce36bac153eae01` | merge base is the tip; `main` ahead by 53, behind by 0 | absorbed; historical Milovi refs require role check, but have no unique commits |
| `6773eccde6b812024f5e7712b0e2dff6c72b1272` | merge base is the tip; `main` ahead by 10, behind by 0 | absorbed; feature/integration/ops refs at this tip are deletion candidates after role check |
| `c3e75b8cc805d9cc394a2f0c2156e65ec69d9c94` | merge base is the tip; `main` ahead by 11, behind by 0 | absorbed; exact temp/noop refs below are high-confidence DELETE candidates |

Several newer historical refs also point directly at commits already present in the current `main` history, including `7e4bcd95824b0010cd6346cc0f5c4dc001321883`, `83dd0ffe921c56806f1f24fc7ff58d9a236599a5`, `1fd68f5454e83d413fbced1dc0afa38f43a12b85`, `e4d8aceb5a32504182956b5e4985c9a72898ec22`, `5060ea31fe93c69c5f68fc2b7383018f54704299`, `ba958fc79cb211b5793107dac563a8646b71a80f`, and `3ea16008375f8e559c9491b7ab308f2fd6a75f9e`. Their branch refs still require the same PR/evidence/active-agent role check before deletion.

## High-confidence DELETE candidates

All refs in this table are branch-only cleanup candidates. Their exact tip is already contained in `main`, none is a durable `state/*` ref, and the names themselves identify disposable/no-op intent. A final exact reread immediately before deletion is still mandatory.

| Branch | Exact tip | Verdict |
| --- | --- | --- |
| `noop-audit-temp` | `c3e75b8cc805d9cc394a2f0c2156e65ec69d9c94` | DELETE |
| `tmp/noop` | `c3e75b8cc805d9cc394a2f0c2156e65ec69d9c94` | DELETE |
| `tmp-do-not-use` | `c3e75b8cc805d9cc394a2f0c2156e65ec69d9c94` | DELETE |
| `tmp-never-use` | `c3e75b8cc805d9cc394a2f0c2156e65ec69d9c94` | DELETE |
| `agent/tmp-do-not-use` | `c3e75b8cc805d9cc394a2f0c2156e65ec69d9c94` | DELETE |
| `agent/audit-branch-hygiene-20260906` | `7e4bcd95824b0010cd6346cc0f5c4dc001321883` | DELETE after confirming no later movement |

### Additional same-day absorbed DELETE candidates

These refs were checked after the initial audit artifact was frozen. Each points directly at a commit already contained in current `main`; none is an open PR head at this disposition checkpoint and exact current-main code search found no dependency on the branch name.

| Branch | Exact tip | Verdict |
| --- | --- | --- |
| `fix/milovi-exact-human-provenance` | `5060ea31fe93c69c5f68fc2b7383018f54704299` | DELETE after final exact-ref reread |
| `fix/milovi-exact-human-provenance-v2` | `ba958fc79cb211b5793107dac563a8646b71a80f` | DELETE after final exact-ref reread |
| `agent/milovi-exact-six-public-readback-20260906` | `83dd0ffe921c56806f1f24fc7ff58d9a236599a5` | DELETE after final exact-ref reread |
| `agent/milovi-exact-six-thumbnails-20260906` | `1fd68f5454e83d413fbced1dc0afa38f43a12b85` | DELETE after final exact-ref reread |

### Pre-delete dependency proof for the high-confidence set

At the initial audit checkpoint the only open pull request was the hygiene PR itself; none of the original six candidate refs was an open PR head. Exact repository code searches against the pre-audit `main` found no existing references to `noop-audit-temp`, `tmp/noop`, `tmp-do-not-use`, `tmp-never-use`, `agent/tmp-do-not-use`, or `agent/audit-branch-hygiene-20260906`. The later same-day absorbed candidates were also checked against current-main code search and open-PR heads before receiving their disposition. Therefore no current runbook/evidence dependency was found for these exact names. This audit document's own mention of the refs is disposition evidence, not a dependency requiring the branches to remain executable.

This does not remove the final reread requirement immediately before actual deletion.

## Large absorbed groups requiring role-only classification

A large fraction of the 145 baseline refs share exact tips that are already ancestors of `main`. These refs do **not** need code-merging work; the remaining question is evidence retention only.

Examples at `fb2a8c099e352350d0ad38fadd91da8ae0ae07cd` include many historical `agent/*` and `work/*` refs for YouTube, VK, Svodka, LordChrist research, audit and hardening work. Because all those refs share an exact fully absorbed tip, the unique-commit gate is already satisfied as `0 unique branch commits`; each still needs an evidence/runbook-reference verdict before deletion.

Examples at `6773eccde6b812024f5e7712b0e2dff6c72b1272` include old `feature/*`, `integration/*`, `ops/*`, `refactor/*`, and fix refs. They are likewise fully absorbed in code ancestry and now require only the evidence/reference check.

Historical Milovi refs at `eac58db5aced0c08294f14d0cce36bac153eae01` are also fully absorbed in code ancestry. They should not be deleted in bulk: some names may still be cited by forensic material, while others are ordinary stale working refs.

## Divergent outliers — explicit dispositions

The initial pass correctly kept the following refs because each retained commits outside `main`. A later exact PR/history pass has now disposed every one explicitly; none is being reclassified merely because equivalent functionality happens to exist in `main`.

| Branch | Exact tip | Unique-history disposition | Verdict |
| --- | --- | --- | --- |
| `audit/mypy2-ci-fix` | `03c0b46ea1087eb72831d761655253f2471ba040` | PR #512 closed/unmerged and explicitly superseded by merged #514 after #513 restored the baseline | DELETE after final reread |
| `agent/pester-psgallery-bootstrap` | `2cd5995a553a95a4117361a5746de453ae444d90` | PR #522 closed/unmerged and explicitly superseded by #523 | DELETE after final reread |
| `agent/milovi-post486-ci-repair` | `000efd66a3f160bb63f8badf60753b59e722e6c2` | PR #489 closed/unmerged, explicitly says its changes should not merge, and is superseded by #488 | DELETE after final reread |
| `work/lordchrist-rich-media-binding` | `1017df9da690855579323df2df154860e3b86d0b` | exact 8-commit merge-base diff contains only the five text files of the provider-free rich-binding package, no binary/provider/state evidence; later v2 PR #470 is explicitly superseded by merged current-main rebuild #472 | DELETE after final reread |
| `work/lordchrist-rich-media-binding-v2` | `4aa172ed12514a12ee7a5d7d72002e3c41022e49` | PR #470 closed/unmerged and explicitly superseded by merged #472 | DELETE after final reread |
| `work/svodka-reconciliation-diagnostics` | `ccf6549ad9950d3981fb8b2521c6286818a5b212` | PR #465 closed/unmerged after exact message-28 reconciliation succeeded; closure records the proposed diagnostic workflow as dead surface | DELETE after final reread |
| `work/svodka-retire-completed-rich-oneoffs` | `31d5091f18bc2eea7a46423d9530cb81e4380c32` | PR #478 closed/unmerged and explicitly superseded by a rebuild from current main | DELETE after final reread |
| `work/svodka-retire-completed-rich-oneoffs-v2` | `263d80f03bf922929578e9fc09141bbacf4a55cf` | PR #479 closed/unmerged because the broad cleanup was intentionally rejected; correct narrow replacement #480 is merged | DELETE after final reread |
| `work/svodka-rich-successor-activation` | `f45dfc2aafdb38aed8d1db74ecf0889383d95f11` | PR #459 closed/unmerged and explicitly superseded by the fresh activation path; successor #460 is merged | DELETE after final reread |

The unsuffixed LordChrist branch required the strongest additional check because it had no direct PR-head record. Its exact merge-base-to-tip diff (`23f9317e77931c859da845258bcc11981dd14cc5` -> `1017df9da690855579323df2df154860e3b86d0b`) proves all eight unique commits are confined to:

- `content/telegram/channels/lordchrist-rich-target-binding.json`;
- `content/telegram/lordchrist/rich-v1/media/media-registry.json`;
- `src/video_channel_manager/lordchrist_rich_successor.py`;
- `tests/test_lordchrist_rich_media_registry.py`;
- `tests/test_lordchrist_rich_successor.py`.

That establishes there are no unique artifact bytes, provider receipts, or durable-state evidence hidden on that branch. The successor chain #470 -> #472 provides the durable implementation disposition.

A branch may be functionally superseded while still containing commits that are not ancestors of `main`. Such a ref is deletable only after those commits receive an explicit abandoned/superseded/evidence disposition such as the records above. Squash divergence alone is neither a KEEP reason nor a DELETE reason.

## Deletion execution boundary

The currently connected GitHub mutation surface exposes branch creation and ref movement but no branch/ref deletion operation. Repointing an obsolete branch to `main` would not be deletion and would destroy forensic meaning, so it is explicitly prohibited as a cleanup substitute.

Therefore this pass records exact deletion candidates and retention rules but does **not** fake completion of #531. Actual deletion must use a genuine delete-ref/branch operation from a repository-admin/client surface that supports it, followed by a fresh complete branch listing.

## #531 completion procedure

Before #531 may close:

1. finish evidence/PR/runbook role classification for the remaining absorbed branch names;
2. reread every intended DELETE ref immediately before deletion;
3. confirm no open PR head or active-agent scope uses it;
4. delete only the exact approved refs using a real ref-deletion operation;
5. relist all branches;
6. prove `main`, all three `state/*` refs, and all explicit evidence refs are unchanged;
7. record final retained/deleted counts and close #531 only from that evidence.

The named divergent-outlier disposition gate is complete; remaining #531 work is absorbed-name role classification plus physical delete/ref readback through a genuine deletion surface.

No provider effect is possible or authorized in this workflow.
