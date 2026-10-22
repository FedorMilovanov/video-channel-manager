# Branch hygiene ledger — 2026-10-21

Classification produced from the GitHub compare API (`main...<branch>`), not from ref age,
prefix or a shallow local clone. `state/*` refs are durable state and were never candidates.

The ledger has three waves with deliberately different standards of proof:

1. **Lossless wave** — deleted only when **every head-side blob of every file it changes is
   byte-identical to `main`**, so its content is fully contained in `main` and deletion cannot lose
   anything. This is proof by construction and needs no judgement.
2. **Superseded waves** — refs that are *not* byte-identical, so each one required an individual
   diff review, a stated reason, and the merged change that replaced it. Nothing here was deleted for
   age, for its name, or because it looked stale.

Each deleted ref is recorded below with its exact tip SHA, so a restoration is
`git push origin <sha>:refs/heads/<branch>` while the objects are still retained.

Deleted 24 refs:

| Branch | Tip SHA |
| --- | --- |
| `agent/instagram-facebook-state-sync-577` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-historical-editorial-552` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-historical-live-561` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-slot-aware-production-20260906-v2` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/lordchrist-spurgeon-v3-live-media-561` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `agent/retirement-archive-blob-integrity` | `b8250d9771bd48efef22913565a6020b7cf0fac1` |
| `arena/01a10838-video-channel-manager` | `59100ed6429ec02a7a78b7403b7cad65f377054e` |
| `arena/13447cc8-video-channel-manager` | `17c4521d44a305964fb0d7177c98e71c5e81636f` |
| `do-not-use` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `feat/lordchrist-historical-v3-archival-revisions-561` | `b8250d9771bd48efef22913565a6020b7cf0fac1` |
| `feat/lordchrist-quote-v4-readiness-20261004` | `ae05e10fef0aed1aa18cdeb97f3d5d5279a5be70` |
| `feature/lordchrist-successor-quote-corpus-v1-20260906` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `final-accidental` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `fix/instagram-cli-unicode-638` | `310b5e3a6ad7245d2585c965320497e68a3fb39f` |
| `fix/instagram-resumable-phase-diagnostics` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `fix/lordchrist-editorial-completeness-665` | `8807a466353b813d173fca5344da8f64a393d5d6` |
| `fix/lordchrist-quote-handoff-576` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `lane/lordchrist-history-human-editorial-561-20260907-copy` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `lane/lordchrist-spurgeon-v3-media-561-20260908` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `oops6` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `probe/lordchrist-historical-v3-final-sources-561` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `research/lordchrist-calvin-spurgeon-macarthur-series-v1` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `tmp-noop` | `254d90c8b0b72774dcb798e5b176cacb83288561` |
| `zzz-test-ignore` | `254d90c8b0b72774dcb798e5b176cacb83288561` |

## Deliberately kept

The remaining branches carry content that is **not** in `main` (older editorial drafts with unique
binaries, unreleased wave/provider work, or history superseded in intent but not byte-identically).
They are kept until each is closed on its own evidence, and no branch is deleted merely because it
looks stale. The audit lists them for individual disposition.

## Second wave: superseded drafts (deleted after individual review)

These refs are not byte-identical to `main`, so the blob rule above does not cover them. Each was
reviewed on its own diff and deleted because the work it carries is either obsolete (it targets a
retired release or a one-off workflow) or was deliberately replaced by merged work. The reason and the
superseding change are recorded per ref; nothing here was deleted for age or for its name.

| Branch | Tip SHA | Why it is superseded |
| --- | --- | --- |
| `agent/lordchrist-depth-v2-gatefix-680` | `843c4c4a6b62bb72310bc04a28c8575024ac5265` | superseded by #693/#694 (branch #680 closed as "[superseded]"); references retired presentation-policy-v3 and a one-off gatefix workflow |
| `agent/lordchrist-depth-v2-preflight-678` | `37303fc004d8c984c7740ed468e88438259c3562` | superseded by #693/#694; contains only the one-off lordchrist-depth-v2-preflight-678.yml workflow |
| `agent/lordchrist-depth-v2-rollout-678-final` | `a59c87addd0fe88d2521336ccbc6eb833cd6b070` | superseded by #693/#694; retired quote-v3 presentation policy and depth-v2-only rollout steps |
| `agent/lordchrist-depth-v2-rollout-678-ready` | `0358d789947297bf83b7e55afefe6862a843d697` | superseded by #693/#694; same content as -final with 13 extra draft commits |
| `agent/sync-vk-upload-state-622` | `8c4b5577cfab6ffc8842ee96c76ccb6965eba1c4` | docs-only; its current-state text predates #626/#629 and would revert them |
| `agent/sync-vk-v2-current-state` | `e8b34652e88d32af3f633f9778d2a6e4ba2d6609` | docs-only; its current-state/wave-contract text predates the merged #626/#629 wording |
| `agent/vk-known-rejection-retry-621` | `cf676f28c4fa9254b0181527b439dda5ba4939f9` | implementation of #628 replaced by the merged design in #699, which keeps the readiness assessment and does not revert it |
| `arena/01a1083a-video-channel-manager` | `e0bca5121b49cdb9da1b14c98a92c3cd138b7a05` | pre-restoration arena draft around quote-v4 activation; superseded by merged #693/#694 |
| `docs/instagram-current-state-625` | `e2281510bf9166b82f645cf4d889124e43ac4a03` | docs-only; checkpoint text from 2026-09-06 already superseded |
| `feat/lordchrist-quote-v4-stage-20261003` | `684b8588341f4284d13e789156a388591eca50f5` | one-off lordchrist-quote-v4-preflight.yml draft; main ships the v5 read-only preflight |
| `ops/lordchrist-depth-v2-readonly-preflight-678` | `8058949a1faf6245a5f614eada79f705de6085b2` | one-off lordchrist-depth-v2-readonly-preflight-678.yml workflow, replaced by the v5 preflight |
| `agent/lordchrist-rich-copy-editorial-standards` | `bad3a115787a323a7296f6257bff1ca153be3a84` | unique manual rich-copy material ported in #699; the rest is older README/standards drafts that must not replace main's |

## Third wave: reviewed as superseded by merged work

| Branch | Tip SHA | Why it is superseded |
| --- | --- | --- |
| `fix/vk-wall-fail-fast-flood-remote` | `11e68253b3d993eb9a60046964a3a0cd9f8bb7f7` | 98 % of its added lines already exist in `main` via #652/#659; `assert_method_circuit_closed` is in `platforms/vk/writer.py` and used by both wall providers, so only a reworded doc line differs. |
| `feat/lord-god-vk-content-wave` | `a6f741784f0f3c4c0e168585a523c24eae19eb79` | 96 % merged via #646/#652/#653/#659; the residue is an older draft of `prepare_lord_god_content_wave.py` and a stale boundary register entry. |
| `feat/lordchrist-depth-v3-context-fixes-20261003` | `7abb6e606fb5ef03181e09c3aa4b215bf7ce83f1` | A pre-#694 design of the same idea: its release JSON is pinned to a 15/45 boundary with `lordchrist-quote-v4` and amended sequences 17/32, while the merged and live #694 release is quote-v5 over a 17/43 boundary with 32/36 restored. |

## Correction (2026-10-22): one deletion in this ledger was wrong and was reverted

`agent/milovi-video-accepted-73c578eff825` was deleted in the third wave as a byte-identical duplicate
of `agent/milovi-video-accepted-f0e25d9c905f`. That was a mistake, and it was reverted by pushing the
recorded tip SHA back:

```
git push origin f4f5512d7b60f1b9c61c293c07620b128536df27:refs/heads/agent/milovi-video-accepted-73c578eff825
```

Byte-identical duplication is not a sufficient reason to delete a ref when a **name** is the contract.
This ref is content-addressed evidence: its name is the prefix of the accepted evidence digest
`sha256:73c578eff82563...`, and it is referenced by

- the runtime binding `milovi_telegram_feed.VIDEO_ARTIFACT_REF` / `VIDEO_EVIDENCE_SHA256`, which gates
  every Milovi `sendVideo`;
- `content/telegram/milovi-cake/accepted-video-reservoir-2026-08.json` (`artifact_ref`);
- `content/telegram/milovi-cake/marathon-wave-2026-08.json` (`evidence_branch`);
- `.github/workflows/AGENTS.md` and `docs/operations/current-state.md`.

Twenty references in `main` pointed at a ref that no longer existed, and the accepted evidence digest
could not be re-verified from the repository at all. The class of mistake is now closed structurally
rather than by memory:

- `docs/operations/protected-evidence-refs.json` lists every ref that hygiene must not delete, with the
  reason, the exact tip where it is immutable, and the restore command;
- `tests/test_milovi_evidence_binding.py` fails if a protected ref appears in this ledger's deletion
  tables, and re-verifies the accepted evidence identity offline.

## Kept — content-addressed evidence, and why it is not debt

Both Milovi refs stay, and neither is a stale work branch:

- `agent/milovi-video-accepted-73c578eff825` — the accepted artifact store: 16 MP4 blobs whose git blob
  SHAs are exactly the `git_blob_sha1` values in the reservoir (64 746 496 bytes of media). The
  reservoir, the runtime binding and the workflow contract name this ref, so it is a permanent locator.
- `agent/milovi-video-accepted-f0e25d9c905f` — a later re-materialization proving reproducibility: all
  16 artifact blobs are byte-identical, and only the evidence generation differs
  (`sha256:f0e25d9c905fc95...` versus the accepted `sha256:73c578eff8256...`).

The accepted evidence file itself is now versioned in `main`
(`content/telegram/milovi-cake/video-conversion-evidence-2026-08.json`), so the digest is checkable
without network access.

Final ref count: `main` + 3 durable `state/*` refs + 2 content-addressed evidence refs.
