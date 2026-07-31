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
- Regression tests for valid bundles, nested roots, missing entrypoints, path traversal, secret leakage, and checksum mismatches.

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
