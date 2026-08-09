# Current operational state

Updated: 2026-08-09  
Audited runtime baseline: `main@aa47760109f65e93f241a2d9e6ee8d7bd62827c7`  
Repository/coverage continuity proof: `main@73c0b831ff7e2168ea09ed8e390d386d1750e9a8`, exact-head CI #3781 SUCCESS; the 77% gate was restored by covering the provider-free Lordchrist outcome CLI rather than lowering the threshold.  
Control audit: [`../lordchrist/audits/2026-08-09-telegram-control-audit.md`](../lordchrist/audits/2026-08-09-telegram-control-audit.md)  
Defect continuation: [`../lordchrist/audits/2026-08-09-defect-register-continuation.json`](../lordchrist/audits/2026-08-09-defect-register-continuation.json)  
Svodka runbook: [`svodka-readiness.md`](svodka-readiness.md)  
Black Man album historical state: [`audit-register-v12-2026-08-07.json`](audit-register-v12-2026-08-07.json)  
VK postponed-text state: [`audit-register-v11-2026-08-07.json`](audit-register-v11-2026-08-07.json)

This file is the current operational truth. Older chats, screenshots, ZIP names, issue wording and audit snapshots remain evidence only and never authorize execution.

## Telegram

### Lordchrist legacy quote publisher

`@lordchrist` has a guarded production quote publisher with durable verified history on `state/lordchrist-telegram`.

At this control point:

- verified manual message `1470`;
- verified scheduled message `1472`;
- later strict queue entries pending;
- no unresolved `may_exist` entry found in the reviewed ledger state;
- schedule `09:17` / `21:17` Europe/Moscow;
- one verified publication per Moscow date;
- provider mutation retries `0`;
- publisher and recovery share `lordchrist-telegram-publisher`, `cancel-in-progress:false`, `queue:max`, `ubuntu-24.04`;
- current-main CI is proved before provider access and again immediately before mutation;
- exact run/attempt provider outcome evidence is archived before final state persistence;
- manual `confirmed_published` reconciliation requires evidence-backed provider publication time distinct from operator resolution time.

### Lordchrist research-v2

Research-v2 is a provider-inert content/release track on the shared generic Telegram runtime, not a third sender.

- profile: `content/telegram/channels/lordchrist.json`;
- `provider_writes_authorized=false`;
- exact target-bound five-item candidate: `sha256:2eb3825390b8f4e70b847d9d1b328ea4e203bce0f1c88e036ea97ae667809cd0`;
- validation remains read-only;
- no research activation or canary is authorized by this state record.

### Svodka

`@deep_info_life` remains not live-enabled.

- `provider_writes_authorized=false`;
- approved release absent at the control point;
- publication ledger absent at the control point;
- exact target chat `-1003527567039`;
- shared bot `8716602202 / @preaching_mp3_bot`;
- canonical pilot queue remains 14 items;
- skipped-send and archived-outcome recovery are separate provider-free paths;
- activation still requires exact-current-main quality, fresh target proof, exact candidate review, approved immutable release, write enablement, ledger initialization and one verified strict-next manual canary.

## Telegram runtime and supply chain

`requirements/telegram-publisher.txt` is exact-version and hash-bound with pip `--require-hashes`. Production/minimal workflow installs keep this lock in its own binary-only pip transaction; test-only packages are installed separately and cannot be appended after the hash lock. General CI builds an isolated Python 3.11 Telegram runtime from the lock, smoke-tests the guarded CLI without provider access, runs `pip check` and dependency audit, then executes the normal Python/PowerShell quality matrices.

Historical green CI never substitutes for an exact-current-main gate where a workflow requires one.

## GitHub governance

`.github/CODEOWNERS` exists for critical automation, Telegram runtime/content and audit paths.

Effective branch protection/rulesets and the current Dependency Graph setting are external GitHub state and remain **UNVERIFIED** by the available connector. CODEOWNERS presence alone does not prove required review or force-push/deletion protection. Verify those settings independently before a new high-risk activation.

## YouTube / Black Man album

Canonical YouTube provider identity is now machine-bound in the existing project profile registry. Provider guards must prove the exact `project_key + OAuth alias + channel_id` triple before using credentials or treating a target as project-owned. The gate is provider-inert and was merged as `aa47760109f65e93f241a2d9e6ee8d7bd62827c7`.

- `audit-register-v12-2026-08-07.json` is preserved as the immutable historical proof of the local seven-track album pipeline introduced by PR #157; its old `next_allowed_actions` describe that 2026-08-07 snapshot and do not override this file;
- PR #197 is open non-provider-write YouTube copy/handoff/editorial work and must be rebuilt/revalidated on current `main` using the canonical project identity gate before any guarded metadata writer is mergeable;
- PR #171 remains a draft private-upload implementation, has not been authorized for execution, and requires canonical project binding plus stable same-media upload-journal identity before it can be considered mergeable;
- PR #158 is a stale draft state-sync from an older baseline and is superseded by this file; its unique v12 evidence has been preserved separately.

An upload plan, private video ID, rendered description, thumbnail or playlist target is not permission for a new YouTube write.

## VK and local MP3

The completed Lord God postponed-text cleanup remains closed evidence. Reusable VK support is the guarded attachment-free postponed wall text-edit capability; historical cleanup packages are not replay authorization.

Supported MP3 capability remains `local_only_read_only_intake_and_manifest`. It may inspect and inventory local MP3 files and build deterministic manifests; it does not authorize remote upload, metadata mutation, playlist changes or browser automation.

## Project and credential boundary

Credential names or shared tokens are never destination selectors. Project key, exact provider identity, immutable plan/release, durable state and target binding select the destination.

Telegram may intentionally use the same bot for multiple channels. A bot token authenticates the bot; exact profile/chat/binding/release/state isolate the channel.

YouTube OAuth aliases are similarly credentials/configuration selectors, not project identity. The canonical project/account/channel gate must pass before a guarded YouTube provider operation may rely on an alias.

Never print, package, commit or log provider credentials.

## Durable side-effect boundary

Before any external mutation, bind the exact project/target, freeze the intended payload, persist durable intent and prove the relevant authorization gates. After mutation, verify the provider-visible postcondition. Ambiguous effects remain possibly existing and require read-only reconciliation; they are never a reason for a blind retry.

A timeout, exception, screenshot, process exit, CI result, preview, issue body or artifact name is not a provider postcondition.

## Historical compatibility anchors

The strings below are preserved **verbatim as historical continuity evidence only**. They describe closed Wave 14 / state-sync checkpoints and must not be interpreted as the current provider graph or current write authorization.

Historical Wave 14 marker: `WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`.

Historical completed-state proofs retained for repository-memory regressions:

- `main@626f83c6e5c068d7faa8b6d14163b42916faa769`;
- PR #131; merge `80f701b6926a5a9c788b99c69634b54d63ed1862`; CI `31000834701`; `801 passed, 1 xfailed`; `451 files already formatted`;
- PR #129; tested state `44a1590fac0e8fe8b563d35cfd68f2bed4727743`; merge `07388521e8d3a2c5d501382227c35bdce6e6470e`; CI `30994245235`; `796 passed, 1 xfailed`; `449 files already formatted`; provider queries/writes/write plans: `0/0/0`;
- predecessor ledgers `audit-register-v7-2026-08-05.json` and `audit-register-v6-2026-08-05.json`.

Historical Wave 14 wording preserved for chain-of-custody tests:

- `No operational continuation is pending` — historical closed-wave conclusion only; later explicitly reviewed work supersedes it.
- `Provider writes remain unauthorized` — historical Wave 14 authorization statement only; it is not a claim about every later independently gated provider surface.
- the historical VK credential model used one shared **user access token**; that credential `is not a project selector`.
- OAuth alias `fedor-milovanov` and OAuth alias `legendary-poet` remained distinct YouTube account selectors.
- #31 — Lord God long-form reconciliation.
- #32 — non-authoritative Lord God 108-item Shorts auto-upload scope.
- #119 — Legendary Poet Shorts/Clips reconciliation.
- #38 — shared VK native Clip/ordinary-video provider-mode.
- `Do not group #32/#38 as Legendary Poet`.
- #33 — broad Lord God catalog/editorial/postponed-wall continuation.
- #99 — unproved Legendary Poet article-wall launcher continuation.
- #123 — deferred YouTube playlist mutation scope.
- repository-wide JSON/Markdown integrity regressions.
- `SEPARATE_EXPERIMENTAL_SYSTEM` remained the historical classification for VK Audio browser/internal-web automation.

These anchors exist so later current-state rewrites cannot erase the evidence chain. The sections above this block are the current operational interpretation.

## Historical memory

Immutable historical anchors remain under:

- `docs/operations/audit-register-v12-2026-08-07.json` (preserved former PR #158 evidence only);
- `docs/operations/audit-register-v11-2026-08-07.json` and predecessors;
- `docs/lordchrist/audits/2026-08-08-*`;
- `docs/research/2026-08-08-svodka-*`;
- Wave 14–16 records referenced by `AGENTS.md`.

Their historical status text may be superseded by this file and newer continuation records; their evidence must not be rewritten to imitate current state.

## Next allowed actions

Repository-controlled Telegram findings from the latest handoff are closed by exact-tested merges or explicitly recorded as external unknowns. Keep Svodka and Lordchrist research activation closed until their own activation gates are satisfied. Finish the local-only Black Man album provenance fixes before salvaging the guarded YouTube upload draft, and rebuild stale YouTube metadata work against the canonical project identity gate.

Nothing in this document is authorization for a new provider mutation.
