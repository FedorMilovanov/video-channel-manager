# 2026-08-08 Svodka archived outcome byte-integrity audit

## Finding

The archived provider-outcome recovery introduced after Svodka PR #193 proved GitHub Actions artifact metadata before recovery, but the state-mutation boundary still relied on `actions/download-artifact` to obtain/extract the artifact. The recovery code therefore did not independently compare the downloaded ZIP bytes with the exact digest and size already accepted from GitHub artifact metadata.

The repair in this branch makes that comparison explicit before any recovered outcome can be written or applied.

## Live GitHub artifact semantics proof

The byte/digest assumption was checked against a real artifact produced by this repository, not only against mocked tests.

Source CI run: `31272976018`.

Artifact:

- name: `mypy-3.11`
- artifact id: `9026181667`
- REST `size_in_bytes`: `177`
- REST digest: `sha256:d8ec3f15fdfde9eddb4b94fade8193d1657b55014b9fe63040bf45cd290fc1fb`

The artifact was independently downloaded through the GitHub artifact download endpoint. The downloaded ZIP was exactly `177` bytes and its independently computed SHA-256 was exactly `d8ec3f15fdfde9eddb4b94fade8193d1657b55014b9fe63040bf45cd290fc1fb`. The archive contained the expected `mypy.log` member.

This proves on the live repository that the REST artifact `size_in_bytes` and `digest` fields bind the ZIP bytes returned by the artifact download endpoint, which is the contract used by `verify_provider_outcome_archive()`.

## Redirect credential boundary

The authenticated GitHub API request is prevented from automatically following the artifact redirect. Only the initial GitHub request carries the bearer credential. The redirected storage request is required to use HTTPS, have a hostname, contain no embedded username/password, and is sent without `Authorization`.

This avoids forwarding the repository Actions credential to the signed artifact-storage host.

## Recovery integrity contract

Before recovered state mutation, the provider-outcome archive must now satisfy all of the following:

- exact proved artifact id;
- bounded archive size;
- exact downloaded byte length equal to proved GitHub metadata;
- exact downloaded ZIP SHA-256 equal to proved GitHub metadata;
- valid ZIP structure;
- one accepted provider-outcome JSON member;
- bounded uncompressed JSON size;
- valid `GenericProviderOutcome` schema;
- subsequent exact publication/provider-payload match against the persisted dispatch.

Normal provider sending is unchanged. This is provider-free post-effect recovery hardening only.

## CI history

The first combined run on head `8b65f4f6ed82c5c957a5084a0d339d0e4ab1446f` reached `1101 passed, 1 xfailed` with Ruff correctness, mypy and dependency audit green; its only repository-CI failure was Ruff formatting in the newly added integrity test. That formatting defect was corrected on the branch before the final exact-head run.

After PR #195 changed `main`, no earlier #196 run is considered final proof. A new exact-head synthetic-merge CI against the post-#195 `main` is required before merge.
