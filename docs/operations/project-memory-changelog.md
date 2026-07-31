# Project memory changelog

This file records durable updates to the repository's operational memory.

## 2026-07-31

### Added

- Root `AGENTS.md` with canonical YouTube/VK identities, current verified counts, closed deletion state, transfer queue identity, and non-negotiable safety rules.
- `docs/operations/current-state.md` as the first-stop operational status board.
- `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md` with successful outcomes, failed attempts, root causes, and permanent rules.
- `docs/operations/operational-artifact-standard.md` defining ZIP, launcher, manifest, ledger, resume, postcondition, and handoff requirements.
- `docs/operations/README.md` as an index for operational documentation.
- `scripts/verify_operational_bundle.py` for pre-handoff ZIP validation.
- Regression tests for valid bundles, nested roots, missing entrypoints, path traversal, secret leakage, checksum mismatches, and critical operational-memory references.
- Pull-request checklist, operational incident issue form, run-report template, incident-report template, and decision-log template.
- Prioritized automation backlog.

### Repository workflow completed

- PR #30, `Complete operational memory and reporting workflow`, passed CI on Python 3.11, 3.12, and 3.13 and was squash-merged into `main`.
- Merge commit: `dcc91326ab50f9ead0a97f0e3aa7cae8a1ff652f`.

### Active operational issues

- [Issue #31 — verify the 26-video upload result and reconcile the ledger](https://github.com/FedorMilovanov/video-channel-manager/issues/31)
- [Issue #32 — inventory the real VK Clips surface and derive the exact Shorts queue](https://github.com/FedorMilovanov/video-channel-manager/issues/32)
- [Issue #33 — organize and publish the verified VK catalog after transfer completion](https://github.com/FedorMilovanov/video-channel-manager/issues/33)

Issue #33 is explicitly blocked by #31 and #32.

### Current operational status

- VK duplicate cleanup: complete and verified (`403` deleted, `0` unresolved).
- Public YouTube inventory: `1781` items (`1673` long-form, `108` Shorts).
- VK ordinary-video inventory after cleanup: `2879`.
- Verified long-form upload queue: `26` items.
- Upload completion: unverified until local `upload-result.json` is reviewed.
- Shorts upload: blocked pending inventory of the real VK Clips surface.

### Required future updates

After each operational run, update `docs/operations/current-state.md` and append a dated entry here containing:

- manifest SHA-256;
- attempted, accepted, processing, verified, failed, and unknown counts;
- result and ledger paths;
- whether resume is safe;
- any new provider, identity, endpoint-coverage, launcher, or packaging failure;
- exact next action.
