# Operational automation backlog

This backlog converts the 2026-07-31 lessons into durable repository improvements.

## P0 — required before the next operational ZIP handoff

- [x] Add root `AGENTS.md` with exact identities and current verified state.
- [x] Add living `current-state.md`.
- [x] Add postmortem and permanent rules.
- [x] Add operational artifact standard.
- [x] Add ZIP verifier and regression tests.
- [x] Add PR and incident-report templates.
- [ ] Run the bundle verifier against the next produced ZIP and retain its JSON output beside the handoff artifact.

## P1 — complete the current transfer safely

- [ ] Inspect `upload-result.json` for the 26-item long-form queue.
- [ ] Reconcile accepted, processing, and unknown ledger records against live VK.
- [ ] Update `current-state.md` with exact verified upload counts and target IDs.
- [ ] Build a live VK Clips inventory that covers the actual Clips surface.
- [ ] Compare all 108 canonical YouTube Shorts against real VK Clip IDs.
- [ ] Produce a separate immutable Shorts manifest and ledger.

## P2 — reduce manual wrapper failures

- [ ] Add a repository command that builds a flat operational ZIP and immediately verifies it.
- [ ] Generate launch commands from the actual archive member list instead of duplicating path assumptions.
- [ ] Add launcher contract tests for required sibling files and `$PSScriptRoot` use.
- [ ] Add channel-identity preflight that compares expected handle, public channel ID, OAuth channel ID, and returned item channel IDs.
- [ ] Add endpoint-coverage metadata to every inventory schema.
- [ ] Add reusable checkpoint discovery so successful audits are reused automatically.

## P3 — catalog organization after transfer verification

- [ ] Build VK playlist taxonomy and exact placement plan.
- [ ] Repair transfer title artifacts such as trailing `()`.
- [ ] Render VK-native descriptions from canonical records.
- [ ] Build postponed wall-post plans with idempotency and deduplication.
- [ ] Build MP3 extraction, loudness normalization, ID3, and artwork workflow.
- [ ] Test VK audio-upload capability with one controlled file.

## Definition of done

A backlog item involving a provider write is complete only when:

- exact source and target IDs are recorded;
- immutable inputs and SHA-256 are stored;
- a durable ledger exists;
- postconditions are verified by provider reread;
- no unknown outcome remains silent;
- `current-state.md` and the project-memory changelog are updated;
- relevant tests pass in CI.
