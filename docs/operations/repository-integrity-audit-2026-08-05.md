# Repository integrity audit — 2026-08-05

## Scope

Wave 14 performs repository-only polish after the completed Wave 13 operational graph. It does not query or mutate YouTube or VK and does not execute historical packages.

## Verified baseline

- completed-state merge: `07388521e8d3a2c5d501382227c35bdce6e6470e`;
- completed-state PR: #129;
- exact PR head: `44a1590fac0e8fe8b563d35cfd68f2bed4727743`;
- exact-head CI: `30994245235`;
- Python 3.11/3.12/3.13: `796 passed, 1 xfailed`;
- Ruff, formatting, strict mypy, dependency audit, and all three PowerShell environments: green;
- provider queries/writes/write plans: `0/0/0`.

## Findings corrected

1. `docs/roadmap.md` still used initial-project wording such as `completed in this PR` and presented Milestones 1–6 as a live roadmap.
2. The root README documented guarded write paths without a sufficiently prominent current statement that provider writes and mutation plans are unauthorized.
3. `docs/security.md` described mutation controls as future implementation rather than mandatory conditions for any separately authorized future operation.
4. `docs/operations/current-state.md` recorded PR #128 but omitted the actual completed-state PR #129 and its stronger final CI baseline.
5. Repository-wide JSON validity and local Markdown-link integrity were not enforced by one general regression.

## Automated integrity contract

The Wave 14 regression:

- parses every tracked JSON file as UTF-8/UTF-8-BOM JSON;
- checks local Markdown links after removing fenced and inline code;
- accepts external URLs, anchors, and explicit documentation placeholders;
- requires the root README to link the canonical current state and state that provider writes are unauthorized;
- rejects stale initial-roadmap wording;
- requires the security model to distinguish capability from authorization;
- requires current state to retain exact PR #129 closure proof.

## Permanent boundary

Historical runbooks, scripts, packages, commands, and code examples document capability and evidence. They do not authorize execution. Any future provider mutation begins from a new explicit request and a new exact project-bound issue.
