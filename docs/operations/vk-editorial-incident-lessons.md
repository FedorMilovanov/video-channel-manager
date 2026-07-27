# VK editorial incident lessons and permanent safeguards

This document records real failures observed while operating The Legendary Poet VK community and the permanent invariants added to Video Channel Manager.

## 1. Structured VK success responses

Observed response from `video.edit`:

```json
{"access_key": "…", "success": 1}
```

The original writer accepted only the scalar response `1` and therefore reported a false failure after VK had already committed the mutation.

Permanent rules:

- accept both scalar `1` and an object with `success: 1`;
- never treat an acknowledgement as final proof;
- read the target again and verify the exact live postcondition;
- classify a resumed operation as `already_applied` when live state already equals the reviewed after-state.

## 2. Do not resend unchanged fields

A title-only `video.edit` request originally included the unchanged description. VK normalized trailing whitespace and zero-width characters in several descriptions even though no editorial description change was intended.

Permanent rules:

- include `name` only when the title changes;
- include `desc` only when the description changes;
- verify both fields after the mutation;
- tests must inspect outgoing request parameters.

## 3. Partial success must be resumable

A process may fail after VK commits a mutation but before the local result journal is updated.

Permanent rules:

- every execution starts with a full live preflight;
- `before` means `ready`;
- `after` means `already_applied`;
- any third state means `conflict` and blocks all writes;
- execute repeats preflight under the single-writer lock immediately before the first mutation.

## 4. Handoff bundles must be one-file and failure-safe

Operators should not manually search for plans, logs, snapshots, reports, and journals.

Permanent rules:

- every wrapper writes one ZIP handoff in `finally`;
- the ZIP contains README, manifest, plan, reports, policy, preflight, apply log, result journal, and snapshots when available;
- manifest records SHA-256 and byte size for every member;
- Explorer opens with the ZIP selected;
- a failed run still produces a useful ZIP.

## 5. Never copy an artifact over itself

Observed failure:

```text
Cannot overwrite ...\00-source-vk-snapshot.json with itself.
```

The description wrapper extracted a snapshot directly into the future handoff directory and then passed it through the generic copy helper using the same destination name.

Permanent rules:

- extract source snapshots into a unique temporary directory outside `data\handoffs`;
- normalize source and destination absolute paths before every copy;
- skip an idempotent self-copy instead of raising;
- remove temporary extraction files in `finally` after the ZIP is written;
- static regression tests must assert these invariants in the PowerShell wrapper.

## 6. Description cleanup requires semantic-body preservation

Technical cleanup may change URLs, Markdown markers, footer blocks, hashtags, line endings, whitespace, and zero-width characters. It must not rewrite facts, interpretation, or punctuation in the content body.

Permanent rules:

- compute a content-only semantic body before and after cleanup;
- exclude only approved technical surfaces from this comparison;
- block the entire plan if the semantic body differs;
- factual and sensitive claims remain unchanged and are emitted as deferred review findings;
- execute requires a previously generated and reviewed plan.

The reviewed `2026-07-27 16:45:35` description dry-run contains 111 operations, zero conflicts, zero review-only exclusions, and exact semantic-body equality for every before/after pair. Its 148 factual or sensitive findings are deferred only and are not rewritten by this wave.

## 7. Never infer title semantics from media metadata

`SHORTS`, `КОРОТКАЯ`, `ФРАГМЕНТ`, `НЕПОЛНЫЙ`, `ПОЛНАЯ`, `БОЛЕЕ ПОЛНАЯ`, `ФИНАЛЬНАЯ`, and numbered versions are user-authored editorial labels. Duration and aspect ratio are not reliable substitutes for editorial intent: a vertical upload can be a SHORTS copy of a longer work, while a short horizontal upload can be a complete compact performance or a fragment.

Permanent rules:

- title automation is cosmetic by default;
- preserve existing semantic labels exactly;
- never add, remove, or replace semantic labels from duration, aspect ratio, pairing, or filename guesses;
- normalize `Version N` to `ВЕРСИЯ N` only because the numbered version identity remains unchanged;
- any actual semantic-label change requires the exact video ID in `title_semantic_label_reviewed_ids`;
- tests must fail closed when an unreviewed title operation changes the semantic-label set.

The current cosmetic title patch intentionally contains exactly three changes: removing the decorative `《》` from the Chinese title and replacing plain hyphen separators with the established `⚡` style in the full `Шабаш` and `Внимая Ужасам Войны...` uploads. It does not alter any version, SHORTS, short, fragment, incomplete, or full label.

## 8. Execute from the reviewed ZIP, not a manually found plan path

A one-file review workflow is incomplete if the operator must later search `data\reports` for the matching JSON plan.

Permanent rules:

- reviewed execute helpers select the latest matching completed dry-run ZIP by default;
- they extract `manifest.json`, `plan.json`, readable reports, policy, and source snapshot into a temporary directory;
- execute requires `status=dry_run_completed`, `mode=dry-run`, the exact component scope, the exact ready count, zero already-applied operations, and zero conflicts;
- manifest `plan_sha256`, embedded plan `plan_sha256`, and the file SHA-256 for `plan.json` must agree;
- every extracted artifact is checked against its manifest byte size and SHA-256;
- manifest checks are explicit per file rather than relying on PowerShell nested-array enumeration;
- the current repository policy must be byte-identical to the reviewed policy in the ZIP;
- title execute revalidates exact approved IDs, after-titles, unchanged descriptions, and preserved semantic labels;
- description execute revalidates unchanged titles, changed descriptions, semantic-body preservation, zero album/catalog operations, and exact source snapshot identity;
- the operator runs one short `-Execute` command and sends back one apply ZIP.

## 9. Treat `video.get` error 204 as a read failure, never as write state

Observed failure before the description writer started:

```text
VK API 204 in video.get: Access denied
```

The failed handoff contained no apply log, no result journal, no final snapshot, and no preflight counts. Therefore no mutation loop had started.

Permanent rules:

- retry only the exact read-only `video.get` error 204, not arbitrary provider or plan errors;
- use a bounded number of attempts with increasing delay;
- keep `-NoOpen` on internal retry attempts so Explorer is not spammed with failed bundles;
- never infer that error 204 means a token refresh is definitely required;
- after persistent failure, diagnose token identity, personal `video.get` permission, managed-community visibility, and community video access separately;
- recommend `video-manager vk login --account <alias>` only when token identity or video/groups permission is actually invalid;
- no write is permitted until a complete fresh preflight returns exact ready/already-applied/conflict counts;
- CI must pass compile, Ruff, formatting, mypy, and tests for all supported Python versions before retry instructions are issued.

## Operator rule

Operational documentation and signed artifacts are the source of truth. Never reuse a confirmation count, snapshot ID, or SHA-256 from chat memory or an older run.
