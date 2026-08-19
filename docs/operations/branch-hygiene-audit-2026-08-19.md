# Branch hygiene audit — 2026-08-19

Historical audit evidence. This file records the branch-lifecycle cleanup performed after the August Telegram/VK/YouTube closure work. It does **not** grant provider execution authority and does not replace `docs/operations/current-state.md`.

## Baseline

- Repository: `FedorMilovanov/video-channel-manager`
- Audited `main`: `fb2a8c099e352350d0ad38fadd91da8ae0ae07cd`
- Total branch refs enumerated through the GitHub connector: **134**
- Ref mutation rule used: fast-forward only; **no force updates**
- Ref deletion was unavailable in the connected GitHub tool, so ephemeral refs with no unique work were aligned to exact current `main`, per `AGENTS.md`.

## Exact partition of the 134 refs

The inventory closes without an unclassified remainder:

- **111 ephemeral refs** — proven `ahead_by=0` with no unique files and aligned to exact audited `main`.
- **6 historical diverged refs** — intentionally preserved because they are closed/superseded/rejected PR lineage or otherwise useful historical evidence.
- **13 Milovi Telegram refs** — deliberately excluded from this audit because issue `#353` is owned by another agent/scope.
- **3 durable state refs** — preserved and never used as code/runtime sources.
- **1 `main` ref**.

Total: `111 + 6 + 13 + 3 + 1 = 134`.

## Preserved durable state refs

These are machine-state history and were not moved:

- `state/lordchrist-telegram`
- `state/milovi-cake-telegram`
- `state/svodka-telegram`

## Preserved historical diverged refs

These were **not** force-aligned because their divergence is intentional historical lineage rather than active backlog:

1. `work/lordchrist-rich-media-binding`
   - older LordChrist rich-media binding lineage;
   - media registry and successor behavior were carried forward to the current implementation;
   - its old target binding uses the superseded rich-profile digest `sha256:a02f33ce...`, while current `main` uses `sha256:0de6ac7a...`;
   - retained as pre-successor history.

2. `work/lordchrist-rich-media-binding-v2`
   - head of closed, unmerged PR `#470`;
   - explicitly superseded by merged PR `#472` (`work/lordchrist-rich-media-binding-v3`).

3. `work/svodka-reconciliation-diagnostics`
   - head of closed, unmerged PR `#465`;
   - diagnostics targeted the message-28 reconciliation path, which later completed and whose executable one-shot workflow was retired;
   - retained only as historical diagnostics lineage.

4. `work/svodka-retire-completed-rich-oneoffs`
   - head of closed PR `#478`;
   - superseded after `main` advanced; the cleanup was rebuilt from current `main`.

5. `work/svodka-retire-completed-rich-oneoffs-v2`
   - head of closed, unmerged PR `#479`;
   - deliberately rejected after exact-head tests proved the broad retirement removed historical reproducibility/recovery contracts;
   - the accepted narrow retirement is merged PR `#480`.

6. `work/svodka-rich-successor-activation`
   - head of closed, unmerged PR `#459`;
   - explicitly superseded by fresh current-main activation PR `#460`.

These refs must not be used to execute, deploy, recover, or start new work. Any genuinely useful future change must be rebuilt from current `main`.

## Milovi Telegram refs excluded from this audit

The following 13 refs were intentionally left untouched because they belong to issue `#353` / the separate Milovi Telegram agent scope:

- `agent/milovi-canary-forensics-20260818`
- `agent/milovi-oneoff-canary-20260818-v2`
- `agent/milovi-oneoff-canary-20260818`
- `agent/milovi-telegram-daylight-rollout`
- `agent/milovi-telegram-live-canary-actual-pr`
- `agent/milovi-telegram-live-canary-ci`
- `agent/milovi-telegram-live-canary-final`
- `agent/milovi-telegram-live-canary-pr`
- `agent/milovi-telegram-live-canary-pr-ready`
- `agent/milovi-telegram-live-canary-review-anchor`
- `agent/milovi-telegram-live-recovery`
- `agent/milovi-telegram-photo-bootstrap`
- `agent/milovi-telegram-photo-byte-proof`

This exclusion is deliberate, not an audit gap.

## Svodka residual state debt is not branch backlog

The old `svodka-pilot-2026-08` ledger still has 14 historical entries in `pending / provider_effect=impossible` with no intent, workflow run, or message id. These are expired state records, **not 14 posts to publish**.

The repository-owned cleanup path is the provider-free manual `svodka-skip-expired.yml` workflow with exact release digest and confirmation. It must not be replaced by direct state-JSON editing or any Telegram replay.

At audit time the connected GitHub tool exposed Actions logs/reruns but no `workflow_dispatch` operation, and the local environment had no `gh` CLI. Therefore that state-only dispatch remains an external operational boundary rather than unfinished repository implementation.

## Closure interpretation

After this audit:

- old branch names must not be treated as evidence of unfinished work;
- `main` is the only supported code/runtime baseline;
- the six preserved diverged refs are historical evidence, not active branches;
- the 13 Milovi Telegram refs remain outside this audit by ownership boundary;
- the three `state/*` refs remain durable state only;
- branch deletion, if desired later, is mechanical cleanup once a tool with delete-ref capability is available.
