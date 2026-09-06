# Branch hygiene final role ledger — 2026-09-06

Status: **provider-inert repository hygiene evidence**.

Owning tracker: #531.

This file completes the **classification** side of #531. It does not claim physical branch deletion.

## Exact checkpoint

- repository: `FedorMilovanov/video-channel-manager`;
- baseline `main`: `6998d6d3d5fc8c29f870a14e1bf1337462c48653`;
- baseline branch inventory before this ledger branch was created: **146 refs**;
- classification result for those 146 refs: **8 KEEP / 138 DELETE candidates**;
- this audit branch, `ops/branch-hygiene-final-ledger-20260906`, is a transient 147th ref created from the exact baseline main and is itself **DELETE after this ledger is merged**;
- open pull requests at the checkpoint: #548 and #549, both LordChrist slot/cadence work;
- provider reads/writes authorized or performed by this ledger: **0 / 0**;
- durable `state/*` mutations: **0**.

The previous control artifact `docs/operations/branch-hygiene-control-audit-2026-09-06.md` remains the detailed proof for the initial absorbed-tip groups, superseded divergent branches, and the no-force-move boundary. This ledger closes the remaining role-classification gaps and provides a complete 146-ref partition.

## KEEP — 8 baseline refs

| Branch | Exact tip at checkpoint | Reason |
| --- | --- | --- |
| `main` | `6998d6d3d5fc8c29f870a14e1bf1337462c48653` | canonical code/runtime baseline |
| `state/lordchrist-telegram` | `429b347a4e3ea87ab21abfa664fb8b5ac2490371` | durable LordChrist provider state |
| `state/milovi-cake-telegram` | `15e68bc43f0cb2954645065c3f21b3195d0a0660` | durable Milovi provider state |
| `state/svodka-telegram` | `b7c060099036c2faf061209178c03d5b46c2edcf` | durable Svodka provider state |
| `agent/milovi-video-accepted-73c578eff825` | `f4f5512d7b60f1b9c61c293c07620b128536df27` | content-addressed accepted-media evidence |
| `agent/lordchrist-quote-slots-20260906` | `2a2878ea2a14b6354bebe01e0a2dc7da682805e7` | active open PR #548 head |
| `agent/lordchrist-slot-aware-production-20260906-v2` | `deb385b58e484222bf27b5d360561fbb6b507e18` | active open PR #549 head |
| `research/lordchrist-calvin-spurgeon-macarthur-series-v1` | `fb2a8c099e352350d0ad38fadd91da8ae0ae07cd` | temporary coordination retention while open #541 still owns successor-corpus/source-policy work; no unique commits are claimed |

The research ref is not permanent evidence. It must be reclassified after #541's successor-corpus lane reaches a durable disposition. It is kept now only to avoid racing active work.

## DELETE — divergent/superseded histories

These refs are not ancestors of current `main`, so each requires an explicit history disposition rather than an age/prefix heuristic.

| Branch | Exact tip | Disposition proof | Verdict |
| --- | --- | --- | --- |
| `audit/mypy2-ci-fix` | `03c0b46ea1087eb72831d761655253f2471ba040` | PR #512 closed/unmerged; superseded by #513/#514 recovery path | DELETE after exact reread |
| `agent/pester-psgallery-bootstrap` | `2cd5995a553a95a4117361a5746de453ae444d90` | PR #522 closed/unmerged; superseded by #523 | DELETE after exact reread |
| `agent/milovi-post486-ci-repair` | `000efd66a3f160bb63f8badf60753b59e722e6c2` | PR #489 closed/unmerged and explicitly superseded by #488 | DELETE after exact reread |
| `agent/milovi-oneoff-canary-20260818` | `e255968ede4a4b571b1c75219e62ddade5790ebf` | six branch-only commits contain retired oneoff workflows/tests plus historical authorization material; both authorization JSON blobs are byte-identical to `main` (`288f850d...` and `0f4a265d...`), while the oneoff executable workflow is absent from `main` | DELETE after exact reread |
| `agent/milovi-oneoff-canary-20260818-v2` | `e255968ede4a4b571b1c75219e62ddade5790ebf` | same exact history/evidence proof as the unsuffixed oneoff ref | DELETE after exact reread |
| `work/lordchrist-rich-media-binding` | `1017df9da690855579323df2df154860e3b86d0b` | exact eight-commit diff contains only the early five-file provider-free binding package; no unique artifact/provider/state bytes; superseded by #470 -> merged #472 path | DELETE after exact reread |
| `work/lordchrist-rich-media-binding-v2` | `4aa172ed12514a12ee7a5d7d72002e3c41022e49` | PR #470 closed/unmerged and explicitly superseded by merged #472 | DELETE after exact reread |
| `work/svodka-reconciliation-diagnostics` | `ccf6549ad9950d3981fb8b2521c6286818a5b212` | PR #465 closed/unmerged after exact reconciliation succeeded; proposed diagnostic surface became dead | DELETE after exact reread |
| `work/svodka-retire-completed-rich-oneoffs` | `31d5091f18bc2eea7a46423d9530cb81e4380c32` | PR #478 closed/unmerged; superseded by current-main rebuild | DELETE after exact reread |
| `work/svodka-retire-completed-rich-oneoffs-v2` | `263d80f03bf922929578e9fc09141bbacf4a55cf` | PR #479 closed/unmerged; broad cleanup rejected; narrow #480 merged | DELETE after exact reread |
| `work/svodka-rich-successor-activation` | `f45dfc2aafdb38aed8d1db74ecf0889383d95f11` | PR #459 closed/unmerged and superseded by the fresh successor activation path | DELETE after exact reread |

### Milovi oneoff evidence-preservation proof

The two oneoff refs share tip `e255968e...` and are six commits ahead of merge base `ae4b5128e79c5f1b9e6f33a516a5443876e3e3a5`. Their unique file set includes the old oneoff workflows/tests, the historical oneoff operations note, and two authorization JSON files. The two evidence files are preserved in current `main` with exactly the same Git blob identities as the branch:

- `oneoff-canary-authorized-release-2026-08-18.json` -> blob `288f850dfee9e92400d8da6263810e07ef7f47f0` on both branch and `main`;
- `oneoff-canary-execution-authorization-2026-08-18.json` -> blob `0f4a265d6cea7712a6dc59a86163eed6a0a23392` on both branch and `main`.

The executable `.github/workflows/milovi-telegram-oneoff-canary.yml` is intentionally absent from current `main`. Therefore deleting the two historical refs cannot remove the immutable authorization evidence and does not resurrect or erase current provider authority.

## DELETE — fully absorbed tip `fb2a8c099e352350d0ad38fadd91da8ae0ae07cd`

Every ref below has zero branch-unique commits relative to current main ancestry. Current-main branch-name searches found no runbook/code dependency for the disposable families. Open PR heads are excluded above. Verdict for each is **DELETE after final exact-ref reread**.

```text
agent/album-pipeline-state-sync
agent/bible-app-ecosystem-marathon-foundation
agent/black-man-youtube-release-retrospective
agent/black-man-youtube-retrospective-current-main
agent/black-man-youtube-upload
agent/finalize-youtube-hardening-status
agent/fix-comment-coverage-semantics
agent/fix-import-and-closure-proof
agent/fix-legendary-poet-cover-download
agent/fix-youtube-description-formatting
agent/foundation-v1
agent/github-governance-readonly-probe
agent/github-sbom-async-probe
agent/issue-323-authority-sync-after-355
agent/issue-323-d48-observed-wall-copy
agent/issue-323-golden-path-hardening-2
agent/issue-323-golden-path-hardening-final
agent/issue-323-golden-path-hardening-final2
agent/issue-323-golden-path-hardening-final3
agent/issue-323-golden-path-hardening-main
agent/issue-323-golden-path-hardening-real
agent/issue-323-golden-path-hardening-real2
agent/issue-323-golden-path-hardening-stop
agent/issue-323-golden-path-hardening-x
agent/issue-323-identity-migration-playbook
agent/issue-323-interim-postmortem-memory
agent/issue-323-phase-order-replay-governance
agent/issue-323-preserve-operator-clip-descriptions
agent/issue-323-single-owner-wall475-cleanup
agent/lordchrist-research-pre-send-freshness
agent/lordchrist-verified-telegram-poster
agent/night-hardening-v1
agent/operational-attempt-history
agent/preserve-youtube-description-contract-2
agent/resi-live-manifest-watch
agent/shared-vk-browser-profile-rule
agent/svodka-custom-emoji-catalog-canary
agent/svodka-freshness-recovery-gap
agent/svodka-native-rich-canary-final
agent/svodka-native-rich-canary-mergework
agent/svodka-operational-truth-cleanup-stage
agent/svodka-premium-emoji-harvest
agent/telegram-link-preview-response-semantics-v2
agent/telegram-lock-coherent-maintenance
agent/unified-editorial-pipeline
agent/vk-catalog-only
agent/vk-delete-megawave
agent/vk-delete-orchestrator
agent/vk-editorial-plan
agent/vk-owner-probe-management-preflight-5253
agent/vk-postponed-text-edit
agent/vk-reviewed-mapping-20260727
agent/vk-wall-content-audit
agent/vk-wall-wave-202608
agent/wave-3-tree-probe
agent/wave-7-fault-injection
agent/windows-download-handoff-defaults
agent/youtube-comment-postflight-recovery
agent/youtube-copy-authoring-standard
agent/youtube-duplicate-comment-dossier
agent/youtube-live-rollout-hardening
agent/youtube-live-rollout-hardening-v2
agent/youtube-night-hardening-v1
agent/youtube-project-identity-gate
agent/youtube-recovery-certificate-v2
agent/youtube-release-executor-adoption
arena/019fc79b-video-channel-manager
arena/019fed75-video-channel-manager
codex/issue-323-durable-verified-recovery
work/fix-generic-receipt-time
work/generic-ledger-authorization-guard-20260808
work/lordchrist-legacy-scheduler-hardening
work/lordchrist-reconciliation-publication-time
work/lordchrist-research-v2-current-main
work/lordchrist-research-v2-healthy-main
work/lordchrist-telegram-hardening
work/post-proof-repo-hardening-20260808
work/svodka-outcome-artifact-integrity
work/svodka-outcome-artifact-integrity-v2
work/svodka-outcome-artifact-recovery-current-20260808
work/svodka-pin-ubuntu-2404-20260808
work/svodka-remove-self-mutating-workflows-20260808
work/svodka-scheduler-catchup-20260808
work/telegram-publisher-hash-lock
```

Count: **84 refs**.

## DELETE — other fully absorbed exact-tip groups

### `eac58db5aced0c08294f14d0cce36bac153eae01` — 14 refs

```text
agent/milovi-323-daily-postponed-rollout
agent/milovi-323-finalize-anomaly
agent/milovi-canary-forensics-20260818
agent/milovi-canonical-feed-control-plane-20260819
agent/milovi-telegram-daylight-rollout
agent/milovi-telegram-live-canary-actual-pr
agent/milovi-telegram-live-canary-ci
agent/milovi-telegram-live-canary-final
agent/milovi-telegram-live-canary-pr
agent/milovi-telegram-live-canary-pr-ready
agent/milovi-telegram-live-canary-review-anchor
agent/milovi-telegram-live-recovery
agent/milovi-telegram-photo-bootstrap
agent/milovi-telegram-photo-byte-proof
```

### `e4d8aceb5a32504182956b5e4985c9a72898ec22` — 8 refs

```text
agent/youtube-release-executor-rebased-backup
agent/youtube-release-executor-rebased-final
agent/youtube-release-executor-rebased-merge-target
agent/youtube-release-executor-rebased-pr
agent/youtube-release-executor-rebased-pr2
agent/youtube-release-executor-rebased-stage
agent/youtube-release-executor-rebased-temp
agent/youtube-release-executor-rebased-work
```

### `6773eccde6b812024f5e7712b0e2dff6c72b1272` — 11 refs

```text
feature/vk-description-rendering-v1
feature/vk-readonly-v1
feature/youtube-comment-publishing-v1
feature/youtube-oauth-v2
fix/issue-323-finalizer-successor-preflight
integration/youtube-vk-unified-v1
integration/youtube-vk-unified-v2-finalize-staging
integration/youtube-vk-unified-v2
ops/link-operational-issues-20260731
ops/project-memory-20260731
refactor/issue323-durable-promotion-dispatcher
```

### `c3e75b8cc805d9cc394a2f0c2156e65ec69d9c94` — 5 refs

```text
agent/tmp-do-not-use
noop-audit-temp
tmp/noop
tmp-do-not-use
tmp-never-use
```

### Other individually absorbed refs — 5 refs

| Branch | Exact tip | Verdict |
| --- | --- | --- |
| `agent/audit-branch-hygiene-20260906` | `7e4bcd95824b0010cd6346cc0f5c4dc001321883` | DELETE after exact reread |
| `agent/milovi-exact-six-public-readback-20260906` | `83dd0ffe921c56806f1f24fc7ff58d9a236599a5` | DELETE after exact reread |
| `agent/milovi-exact-six-thumbnails-20260906` | `1fd68f5454e83d413fbced1dc0afa38f43a12b85` | DELETE after exact reread |
| `fix/milovi-exact-human-provenance` | `5060ea31fe93c69c5f68fc2b7383018f54704299` | DELETE after exact reread |
| `fix/milovi-exact-human-provenance-v2` | `ba958fc79cb211b5793107dac563a8646b71a80f` | DELETE after exact reread |

## Partition proof

The 146-ref baseline is completely partitioned:

- KEEP: `8`;
- divergent/superseded DELETE: `11`;
- absorbed `fb2a8c...` DELETE: `84`;
- absorbed `eac58d...` DELETE: `14`;
- absorbed `e4d8ac...` DELETE: `8`;
- absorbed `6773ec...` DELETE: `11`;
- absorbed `c3e75b...` DELETE: `5`;
- other individually absorbed DELETE: `5`.

Total: `8 + 11 + 84 + 14 + 8 + 11 + 5 + 5 = 146`.

After this ledger branch was created there are 147 refs; `ops/branch-hygiene-final-ledger-20260906` is the sole additional transient branch and is pre-authorized only for branch cleanup **after its PR is merged**.

## Execution boundary

The connected GitHub action surface was re-discovered at this checkpoint. It exposes `update_ref` and file deletion, but **no genuine branch/ref deletion mutation**. `update_ref` is not deletion. Force-moving obsolete refs to `main` would destroy forensic meaning and is prohibited.

Therefore #531 is now blocked only on a real delete-ref/delete-branch surface plus post-delete verification. It must remain open until that operation actually occurs.

When a genuine deletion surface is available, execute exactly this sequence:

1. re-read current `main`, all open PR heads, all three `state/*` tips and all DELETE refs;
2. remove any ref that moved or became an active PR/evidence dependency from the deletion batch;
3. delete each remaining exact DELETE ref individually, never by prefix;
4. do not delete `research/lordchrist-calvin-spurgeon-macarthur-series-v1` while #541 successor-corpus scope remains live;
5. re-list every branch;
6. prove `main`, the three `state/*` refs and `agent/milovi-video-accepted-73c578eff825` are unchanged;
7. record deleted/retained counts and close #531 only from that readback.

No provider effect is possible or authorized by this ledger.
