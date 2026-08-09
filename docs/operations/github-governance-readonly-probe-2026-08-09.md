# GitHub governance read-only probe — 2026-08-09

This is immutable read-only evidence. It does **not** authorize any repository, provider, credential, state-branch, or deployment mutation.

## Probe identity

- Repository: `FedorMilovanov/video-channel-manager`
- Temporary PR: `#227` — closed without merge by contract
- Probe head: `6981086edf54dcc1ebf40bcdcf243293194d77b3`
- GitHub Actions workflow run: `31319720291`
- Probe job: `93260619336`
- Result: `success`
- Workflow token permissions shown by GitHub Actions: `Contents: read`, `Metadata: read`
- Checkout: none
- Provider access: none
- Repository write API: none

After evidence capture, PR #227 was closed without merge and its ephemeral branch was aligned to the exact current `main`, as required by the repository branch-lifecycle contract.

## Observed GitHub REST results

The successful probe printed only HTTP statuses and non-secret summary fields:

```text
BRANCH_HTTP=200
MAIN_PROTECTED=false
BRANCH_PROTECTION_KEYS=enabled,required_status_checks
PROTECTION_HTTP=403
PROTECTION_MESSAGE=Resource not accessible by integration
RULESETS_HTTP=200
RULESETS_COUNT=0
SBOM_HTTP=404
SBOM_MESSAGE=Not Found
```

## Interpretation

### Main branch protection

`GET /repos/FedorMilovanov/video-channel-manager/branches/main` returned HTTP 200 with `protected=false`.

For the current repository state, the GitHub branch object therefore does not mark `main` as protected. The more detailed legacy branch-protection endpoint returned HTTP 403 to the read-only GitHub App integration, so its nested detail object was not separately readable. That 403 is an access limitation for the detail endpoint; it is not evidence that `main` is protected.

### Repository rulesets

`GET /repos/FedorMilovanov/video-channel-manager/rulesets` returned HTTP 200 and an empty list (`RULESETS_COUNT=0`). No repository ruleset was present in the observable repository state at probe time.

### Dependency Graph and SBOM export

This repository is public. GitHub's current supply-chain documentation states that Dependency Graph is enabled by default for public repositories and cannot be disabled; GitHub's security/settings documentation also describes it as permanently enabled for public repositories.

The probe's `GET /repos/FedorMilovanov/video-channel-manager/dependency-graph/sbom` request nevertheless returned HTTP 404 `Not Found`. GitHub documents `404` as one possible response for the SBOM export endpoint and documents that the endpoint otherwise needs only Contents read permission and can be used without authentication for public resources.

Therefore:

- do **not** interpret the 404 as evidence that Dependency Graph is disabled;
- treat the Dependency Graph feature itself as policy-enabled for this public repository;
- treat SBOM export availability from this endpoint as **UNVERIFIED / unavailable in this probe** until a later read-only probe returns a successful export.

Official documentation consulted for this interpretation:

- `https://docs.github.com/en/code-security/concepts/supply-chain-security/supply-chain-security`
- `https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-security-and-analysis-settings-for-your-repository`
- `https://docs.github.com/en/rest/dependency-graph/sboms`

## Closure result

The previous blanket statement that branch protection, rulesets, and Dependency Graph were all externally `UNVERIFIED` is now too coarse.

Current evidence supports this narrower state:

- `main` protected flag: **verified false** at probe time;
- repository rulesets: **verified zero** at probe time;
- Dependency Graph feature: **enabled by GitHub policy for a public repository**;
- SBOM export endpoint availability: **UNVERIFIED / unavailable in the successful read-only probe (HTTP 404)**.

No write-capable governance setting was changed by this probe.