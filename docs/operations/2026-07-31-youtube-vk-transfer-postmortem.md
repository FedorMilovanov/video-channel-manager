# YouTube → VK inventory and transfer postmortem

Date: 2026-07-31

## Executive summary

The workflow eventually produced a reliable public YouTube inventory, a stable VK ordinary-video inventory, an exact 26-item long-form upload queue, and a separate warning that Shorts were not safe to upload from the current evidence.

The main failures were not provider outages. They were boundary, identity, coverage, reuse, and packaging errors in the operational wrappers.

## What succeeded

### Destructive cleanup

- Exact reviewed delete set: `403` VK videos.
- Final result: `403 confirmed_deleted`, `0 unresolved`.
- Stable ordinary-video inventory after cleanup: `2879`.
- Protected primary IDs remained excluded.
- Durable SQLite ledger prevented same-ID repeat.

### Read-only inventories

- YouTube public channel pages yielded `1781` items.
- Long-form public items: `1673`.
- Canonical Shorts IDs: `108`.
- VK ordinary-video inventory: `2879`.
- Successful heavy audits were preserved and reused rather than rescanned on every attempt.

### Long-form matching

- Exact boundary ID found: `KobOzfBqzic`.
- Boundary confirmed already present in VK.
- `27` newer long-form items identified.
- `26` verified missing.
- One ambiguous item resolved as already present by title identity and one-second duration delta:
  - YouTube `s512Opa8Eu4`
  - VK `-60805374_456241938`
- Immutable queue SHA-256 produced:
  `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`.

### Safety decisions

- The provisional 65-item Shorts list was not executed.
- The ordinary VK video endpoint returned zero clips while clips were visible in the UI, so endpoint absence was correctly treated as incomplete evidence.
- Ambiguous items were excluded from upload.
- No result was declared complete without a result artifact.

## What failed and why

### Attempt 1: OAuth client path

Symptom:

`Cannot read OAuth client file: secrets\client_secret.json`

Cause:

The launch script inherited the caller's working directory and passed a relative secret path.

Correction:

Resolve the OAuth file to an absolute path before invoking the CLI.

Permanent rule:

Operational scripts may not depend on the user's current directory.

### Attempt 2: Shorts IDs missing from OAuth inventory

Symptom:

The `/shorts` page returned IDs absent from the 131-video OAuth inventory.

Cause:

The stored OAuth alias pointed at a different or incomplete channel inventory.

Correction:

Treat canonical public channel pages as the transfer source and use OAuth only to fetch metadata for exact page IDs.

Permanent rule:

Validate channel identity before trusting an authenticated inventory. Record both expected and observed channel IDs.

### Attempt 3: foreign channel ID during deep Shorts extraction

Symptom:

A recursively resolved page object reported a different `channel_id`.

Cause:

The extractor followed objects beyond the exact canonical page membership list.

Correction:

Use a two-pass process:

1. flat canonical page IDs;
2. exact metadata resolution only for those IDs.

Permanent rule:

No resolved ID may enter a manifest unless it was present in the canonical flat page list.

### Attempt 4: exact boundary-title failure

Symptom:

The boundary title was not found by byte-for-byte title comparison.

Cause:

Punctuation and title representation differed.

Correction:

Use exact IDs whenever possible; normalized title matching is diagnostic only.

Permanent rule:

A title is not an identity.

### Attempt 5: fuzzy boundary failure

Symptom:

Even fuzzy matching could not find the expected sermon in the 131-video inventory.

Cause:

The source inventory itself was incomplete, so no matching algorithm could recover an absent item.

Correction:

Inventory the entire public `/videos` surface and compare all public items.

Permanent rule:

Before debugging matching logic, verify that the source record exists in the source dataset.

### Attempt 6: nested ZIP entrypoint

Symptom:

PowerShell could not find `run-upload-26.ps1` at the documented path.

Cause:

The ZIP contained an extra top-level directory while the handoff command assumed a flat archive.

Correction:

Repackage the archive flat and add repository-side bundle verification.

Permanent rule:

A handoff is incomplete until the exact documented launch path is tested against the produced ZIP structure.

## Root causes

1. **Identity was implicit.** Public handle, public channel ID, and OAuth channel ID were not validated as one identity before scanning.
2. **Surface coverage was implicit.** Ordinary VK videos and VK Clips were treated as if one endpoint covered both.
3. **Titles were overused as keys.** Exact source IDs should have been the primary boundary and match identity.
4. **Wrappers were not self-locating.** Relative paths depended on caller state.
5. **Artifact structure was not verified.** ZIP packaging and launch instructions were generated separately.
6. **Successful checkpoints were initially underused.** Heavy scans should always be reusable inputs.
7. **Completion criteria were not explicit enough.** Provider acceptance, processing, and verified remote existence are separate states.

## Improvements adopted

- Root `AGENTS.md` with exact identities, status, and non-negotiable rules.
- `docs/operations/current-state.md` as a living operational status board.
- This postmortem as durable failure memory.
- `docs/operations/operational-artifact-standard.md` for future packages.
- `scripts/verify_operational_bundle.py` to verify ZIP entrypoints, required siblings, flatness, duplicate roots, secret leakage indicators, and SHA-256.
- Explicit status vocabulary:
  - `planned`
  - `downloaded`
  - `upload_url_acquired`
  - `accepted`
  - `processing`
  - `verified`
  - `rejected`
  - `unknown`
- Separate manifests and ledgers for long-form and Shorts/Clips.
- Public canonical pages as source membership; APIs as metadata and write providers.

## Required evidence for future handoffs

Every future operational package must include:

- immutable manifest and SHA-256;
- exact source and target identities;
- exact launch command;
- entrypoint present at that path;
- required-file self-check;
- dry-run or read-only preflight mode;
- ledger path;
- result path;
- resume behavior;
- unknown-outcome reconciliation policy;
- statement of surfaces not covered by the inventory;
- tested bundle verification output.

## Current unresolved work

- Verify the final result of the 26-item long-form uploader.
- Inventory live VK Clips separately.
- Derive the exact missing Shorts set.
- Organize verified VK videos into playlists.
- Repair titles and descriptions.
- Build postponed wall posts.
- Build MP3 extraction and metadata workflow.
