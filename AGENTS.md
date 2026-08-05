# Repository agent instructions

Before work on Fedor Milovanov's YouTube/VK workflow, read in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
3. `docs/operations/audit-register-v2-2026-08-04.json`
4. `docs/operations/current-state.md`
5. `docs/operations/automation-backlog.md`
6. GitHub issue #64 and the issue owning the exact operation
7. `docs/operations/local-credential-sources.md`
8. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
9. `docs/operations/operational-artifact-standard.md`
10. `docs/operations/operational-package-acceptance.md`
11. `docs/operations/retirement-registry-v1.json`

The audit register and `current-state.md` override old chats, screenshots, ZIPs, remembered counts, and superseded audits. Historical material teaches; it never authorizes execution.

## Exact project boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

Canonical identities:

- `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- `legendary-poet`: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

Never mix channels, communities, owners, tokens, links, manifests, ledgers, results, comments, descriptions, or footers. The shared VK token alias is a credential label, not a project selector.

## Credential boundary

The configured VK token source remains outside this repository:

- file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`;
- key: `VK_API_TOKEN`.

Never copy, print, commit, package, log, or place the token value on a command line. Do not request manual token entry while the configured source exists.

## Current verified sequence

Verified code baseline: `main@eeab53b779e5ea4af5d3dcc08d79e41812739e04`.

- Waves 0–8F: completed;
- Wave 9 read-only evidence contract: completed;
- Package A — Wave 9A + Wave 9B + Wave 10 tooling/governance: completed at `read_only_package_self_tested`;
- Package A PR #110 merged as `8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`;
- Package A state sync PR #111 merged as `024a978f7c57a52f03e4cae8e6cb8175d8e96976`;
- Wave 11 operational-package truth and managed-community preflight: completed at `self_tested_source_bound_governance`;
- Wave 11 PR #113 merged as `eeab53b779e5ea4af5d3dcc08d79e41812739e04`;
- Wave 11 exact-head CI `30967195938`: `782 passed, 1 xfailed` on Python 3.11/3.12/3.13; all three PowerShell environments green;
- provider queries during Wave 11 implementation/CI: `0`;
- provider writes during Wave 11 implementation/CI: `0`;
- write plans created during Wave 11 implementation/CI: `0`;
- fresh live Wave 9A/9B reconciliation remains pending exact local ledgers/results and fresh bounded provider snapshots.

Green CI proves contracts and regression fixtures, not current YouTube/VK state.

## Package A boundaries

Supported read-only commands:

```text
video-manager-package-a reconcile --manifest <package-a-manifest.json>
video-manager-package-a verify-output --output <package-a-output-directory>
```

Package A creates immutable reconciliation evidence, a no-blind-replay recovery ledger, and a read-only operator board. Package A output never authorizes a provider mutation by itself.

## Wave 11 operational-package truth

Every package declares exactly one evidence level:

1. `editorial_prepared`;
2. `preview_validated`;
3. `self_tested`;
4. `canary_verified`;
5. `batch_verified`.

A filename, ZIP, preview, confirmation prompt, final stdout line, or green CI cannot promote evidence. Use the repository-owned verifier:

```text
python -m video_channel_manager.tools.operational_package_acceptance <archive.zip> ...
```

A passing result fixes `provider_writes_authorized=false` and `automatic_execution=false`. It validates structure and claims; it does not authorize execution.

PowerShell orchestrates one repository-owned implementation. It does not duplicate provider permission, retry, pagination, postflight, or state-classification logic. A generated Downloads-only `executor.py` is not a supported provider adapter.

## VK managed-community permission rule

Managed-community enumeration uses exactly `groups.get(filter=moder, extended=1)` with bounded pagination. `filter=admin` is not an equivalent capability check and produced a documented false rejection. The returned managed list is normalized, then the exact registered community and owner are verified separately.

## Sermon-month incident boundary

`LordGod-VK-SERMON-MONTH` v1/v2/v3 is retired, non-executable historical evidence. Do not rerun it.

The supplied transcript reports a later v3 `FINAL_OK — 30/30`, first post `-60805374_12482`, and last post `-60805374_12511`. The original v3 result directory and exact provider readbacks were not supplied, so the outcome remains `operator_transcript_reported`, not independently `batch_verified`.

Representative PowerShell and Python fragments may exist only inside the Markdown learning archive. Never copy them into `scripts/` or `src/` as a shortcut.

## Live reconciliation owners

- #31 — Lord God long-form reconciliation;
- #32/#38 — Legendary Poet Shorts/Clips reconciliation;
- #33 — later reviewed catalog/publication gate;
- #64 — canonical roadmap.

Retained Lord God facts are inputs, not fresh conclusions:

- `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` → `-60805374_456241938`;
- local evidence directory `data\vk-upload\verified-longform-26`;
- reviewed manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`.

Retained Legendary Poet facts are inputs, not fresh conclusions:

- 56 exact YouTube Shorts;
- 41 retained exact pairs;
- 15 retained missing candidates;
- 0 retained ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`.

Do not use retired V1/V2/V3/V4, the historical “48 clips” package, or sermon-month v1/v2/v3.

## Separate VK Audio boundary

VK Audio browser/internal-web work remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. It is not part of Package A or Wave 11.

## Branch and merge discipline

- Substantial work uses one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Merge only after exact-head six-job green CI.
- Synchronize operational memory in a separate narrow PR.
- Guard squash merges by unchanged expected head, reviewed scope, and clean review threads.
- Never mix live provider reconciliation with reliability, archive, or governance refactors.

## Non-negotiable safety rules

1. Never mix project identities, credentials, IDs, journals, links, or manifests.
2. Never expose or request manual entry of the configured VK token.
3. Never rerun completed deletion, reset, article-wave, transfer, or retired executors.
4. Never infer absence from an endpoint that does not cover the relevant surface.
5. Use exact IDs and bounded inventories, not screenshots, titles, or relative dates.
6. Never upload an ambiguous match.
7. Never repeat an intent-persisted, accepted, processing, verified, or unknown mutation; reconcile first.
8. Keep long-form and Shorts/Clips in separate manifests and ledgers.
9. Video upload and wall publication are separate operations.
10. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
11. Public text may use only the selected project's registered links; unknown links fail closed.
12. A successful HTTP response is not a postcondition; verify the exact remote effect.
13. Machine state belongs in journals/results, not only stdout.
14. Counts, ZIP names, final console lines, extensions, containers, save responses, and CDN URLs are not immutable identity.
15. Historical code is never a supported entrypoint.
16. `already_correct` requires exact per-field readback.
17. Cache reuse requires exact manifest/file/source/probe agreement.
18. Thumbnail success requires exact selected-thumbnail postflight.
19. Package A and live Wave 9A/9B remain read-only.
20. A dashboard, acceptance report, preview, canary claim, or green CI is not mutation authorization.
21. Evidence levels must not be collapsed or upgraded without retained machine evidence.
22. PowerShell must not become a second provider implementation.
23. VK managed-community discovery uses `filter=moder`; exact project identity is a separate gate.
24. Unknown outcomes stop automatic execution and require reconciliation.
25. Every batch operation requires its own durable result; one `FINAL_OK` line is supplementary only.

## Execution and handoff rules

- Read-only inventory first; writes only from a separately reviewed exact-ID plan.
- Persist mutation intent before dispatch and preserve unknown outcomes.
- Preserve successful intermediate stages and resume from durable state.
- Every handoff states truth level, project, exact entrypoint, manifest/archive SHA-256, inputs, outputs, result paths, canary behavior, and recovery behavior.
- Operational ZIPs are flat unless launch instructions explicitly say otherwise.
- Launchers verify their own location and required siblings before network work.
- After every wave, update `current-state.md`, the machine register, backlog, issue #64, owning issues, and regression coverage.
