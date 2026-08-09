# GitHub governance read-only probes — 2026-08-09

This is immutable read-only evidence. It does **not** authorize any repository, provider, credential, state-branch, deployment, or governance-setting mutation.

## Probe 1 — repository governance and legacy SBOM endpoint

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

Observed GitHub REST results:

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

After evidence capture, PR #227 was closed without merge and its ephemeral branch was aligned to exact current `main`.

## Probe 2 — current asynchronous SBOM generation endpoint

GitHub announced on 2026-04-14 that SBOM export generation had moved to asynchronous generation/fetch endpoints. The legacy endpoint result therefore was rechecked against the current documented API instead of being treated as the final answer.

- Temporary PR: `#229` — closed without merge by contract
- Probe head: `d83f01d4d43f33e27cfc983e95ddbde1b13f56c4`
- GitHub Actions workflow run: `31321188514`
- Probe job: `93264322804`
- Result: `success`
- Workflow token permissions shown by GitHub Actions: `Contents: read`, `Metadata: read`
- Checkout: none
- Provider access: none
- Repository write API: none

The probe called the current documented endpoint:

```text
GET /repos/FedorMilovanov/video-channel-manager/dependency-graph/sbom/generate-report
X-GitHub-Api-Version: 2026-03-10
```

Observed result:

```text
GENERATE_HTTP=404
GENERATE_MESSAGE=Not Found
```

The probe was deliberately bounded. It would have validated an exact same-repository `sbom_url`, polled the documented fetch endpoint, refused automatic authenticated redirects, and stopped at a safe HTTPS 302 without sending the GitHub token to the storage host. Because generation returned 404, no fetch URL existed and no further request was made.

After evidence capture, PR #229 was closed without merge and its ephemeral branch was aligned to exact current `main`.

## Interpretation

### Main branch protection

`GET /repos/FedorMilovanov/video-channel-manager/branches/main` returned HTTP 200 with `protected=false`.

For the observed repository state, the GitHub branch object therefore does not mark `main` as protected. The more detailed legacy branch-protection endpoint returned HTTP 403 to the read-only GitHub App integration, so its nested detail object was not separately readable. That 403 is an access limitation for the detail endpoint; it is not evidence that `main` is protected.

### Repository rulesets

`GET /repos/FedorMilovanov/video-channel-manager/rulesets` returned HTTP 200 and an empty list (`RULESETS_COUNT=0`). No repository ruleset was present in the observable repository state at probe time.

### Dependency Graph

This repository is public. GitHub's current supply-chain/security documentation states that Dependency Graph is enabled by default for public repositories and cannot be disabled / is permanently enabled for public repositories.

Dependency Graph feature state is therefore not inferred from the SBOM endpoint result.

### SBOM REST export

GitHub's current SBOM REST documentation states that both the legacy export endpoint and the asynchronous generation/fetch endpoints require only `Contents` repository permission (read), and can be used without authentication when only public resources are requested. The documentation lists HTTP 404 as `Resource not found` for these surfaces.

Two independent read-only probes therefore establish the current REST-export observation rather than leaving it `UNVERIFIED`:

- legacy `GET /dependency-graph/sbom` -> HTTP 404 `Not Found`;
- current `GET /dependency-graph/sbom/generate-report` -> HTTP 404 `Not Found`.

**Current status:** GitHub SBOM **REST export is verified unavailable through both documented generation surfaces at these probe points**. This is not evidence that Dependency Graph itself is disabled.

This statement is intentionally scoped to the documented REST export surfaces that were actually probed. It does not claim anything about an untested future GitHub UI behavior or a later GitHub service change.

## Official documentation consulted

- `https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-graph`
- `https://docs.github.com/en/rest/dependency-graph/sboms`
- `https://github.blog/changelog/2026-04-14-sbom-exports-are-now-computed-asynchronously/`

## Closure result

Current evidence supports the following exact external governance state:

- `main` protected flag: **verified false** at probe time;
- repository rulesets: **verified zero** at probe time;
- Dependency Graph feature: **enabled by GitHub policy for a public repository**;
- SBOM REST export: **verified unavailable at the two read-only probe points (HTTP 404 on both documented generation surfaces)**.

There is no remaining blanket GitHub-governance `UNVERIFIED` item in this audit. Future GitHub configuration or service changes must be established by fresh read-only evidence rather than assumed from this historical probe.

No write-capable governance setting was changed by either probe.