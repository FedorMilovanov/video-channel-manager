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

The active coordination ref `agent/lordchrist-quote-slots-20260906` is also **KEEP while its owning LordChrist slot/cadence scope is active**, even though its current tip was already contained in `main` when this audit started. Hygiene must not race an active agent.

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

## Large absorbed groups requiring role-only classification

A large fraction of the 145 refs share exact tips that are already ancestors of `main`. These refs do **not** need code-merging work; the remaining question is evidence retention only.

Examples at `fb2a8c099e352350d0ad38fadd91da8ae0ae07cd` include many historical `agent/*` and `work/*` refs for YouTube, VK, Svodka, LordChrist research, audit and hardening work. Because all those refs share an exact fully absorbed tip, the unique-commit gate is already satisfied as `0 unique branch commits`; each still needs an evidence/runbook-reference verdict before deletion.

Examples at `6773eccde6b812024f5e7712b0e2dff6c72b1272` include old `feature/*`, `integration/*`, `ops/*`, `refactor/*`, and fix refs. They are likewise fully absorbed in code ancestry and now require only the evidence/reference check.

Historical Milovi refs at `eac58db5aced0c08294f14d0cce36bac153eae01` are also fully absorbed in code ancestry. They should not be deleted in bulk: some names may still be cited by forensic material, while others are ordinary stale working refs.

## Unique/outlier tips — KEEP pending exact classification

The branch listing also contains refs whose tips are not part of the four large absorbed groups above, for example:

- `audit/mypy2-ci-fix` → `03c0b46ea1087eb72831d761655253f2471ba040`;
- `agent/pester-psgallery-bootstrap` → `2cd5995a553a95a4117361a5746de453ae444d90`;
- `agent/milovi-post486-ci-repair` → `000efd66a3f160bb63f8badf60753b59e722e6c2`;
- `work/lordchrist-rich-media-binding` → `1017df9da690855579323df2df154860e3b86d0b`;
- `work/lordchrist-rich-media-binding-v2` → `4aa172ed12514a12ee7a5d7d72002e3c41022e49`;
- `work/svodka-reconciliation-diagnostics` → `ccf6549ad9950d3981fb8b2521c6286818a5b212`;
- `work/svodka-retire-completed-rich-oneoffs` → `31d5091f18bc2eea7a46423d9530cb81e4380c32`;
- `work/svodka-retire-completed-rich-oneoffs-v2` → `263d80f03bf922929578e9fc09141bbacf4a55cf`;
- `work/svodka-rich-successor-activation` → `f45dfc2aafdb38aed8d1db74ecf0889383d95f11`.

These remain **KEEP pending exact compare + PR/evidence inspection**. No deletion verdict is inferred from age or prefix.

## Deletion execution boundary

The currently connected GitHub mutation surface exposes branch creation and ref movement but no branch/ref deletion operation. Repointing an obsolete branch to `main` would not be deletion and would destroy forensic meaning, so it is explicitly prohibited as a cleanup substitute.

Therefore this pass records exact deletion candidates and retention rules but does **not** fake completion of #531. Actual deletion must use a genuine delete-ref/branch operation from a repository-admin/client surface that supports it, followed by a fresh complete branch listing.

## #531 completion procedure

Before #531 may close:

1. finish exact compare + evidence/PR role classification for every remaining outlier tip;
2. reread every intended DELETE ref immediately before deletion;
3. confirm no open PR head or active-agent scope uses it;
4. delete only the exact approved refs using a real ref-deletion operation;
5. relist all branches;
6. prove `main`, all three `state/*` refs, and all explicit evidence refs are unchanged;
7. record final retained/deleted counts and close #531 only from that evidence.

No provider effect is possible or authorized in this workflow.
