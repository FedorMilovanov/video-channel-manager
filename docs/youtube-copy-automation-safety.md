# YouTube copy automation safety

This document defines what the deterministic bot may change without editorial interpretation.
It complements `youtube-description-rendering-standard.md`: a human editor may decide punctuation scope from meaning, while the bot must act only when that scope is mechanically provable.

**Project/surface precedence:** the file above documents The Legendary Poet's own first-literary-paragraph rule. On the Lord God YouTube channel, however, the **first two nonempty raw Studio lines** must be substantive unmarked sentences; removing emphasis only from paragraph one may leave line two invalid. A copy plan for that channel must additionally pass the [Lord God agent surface decision contract](operations/lord-god-youtube-agent-decision-contract.md) and the code's `presentation_issues()` + source-preservation gates. Do not apply Poet v3.1 playlist-first layout to Lord God Shorts, move an ambiguous comma automatically, or infer provider write approval from a passing safe autofix.

## Automatic rules

The bot may automatically:

1. remove `*...*` and `_..._` markers from the first paragraph so SHARE previews do not expose formatting markers;
2. trim spaces immediately inside paired emphasis markers;
3. collapse three or more consecutive line breaks to one empty line;
4. move a colon inside a known link label such as `*VK:*`, `*Telegram:*`, `*RUTUBE:*`, or `*Плейлист ...:*`;
5. remove an extra full stop after an emphasized phrase that already ends in `?`, `!`, or `…`;
6. preserve URLs, underscores inside URLs, literal `***` poem titles, wording, facts, links, and later-paragraph emphasis.

## Review-only punctuation

The bot must not automatically move commas, full stops, semicolons, or explanatory colons across `*` or `_` merely because they follow a closing marker.

Examples that remain unchanged automatically:

```text
сборник *«Радуница»*, который...
экземпляр *«Вечера»*, по свидетельству...
*18 сентября 1912 года*, у Ахматовой...
термин *magnitizdat*, becoming...
игра _The Witcher 3: Wild Hunt_.
```

These marks belong to the surrounding sentence unless a human editor decides otherwise. The validator reports them as `punctuation_scope_review` warnings, not automatic errors.

## Plan blocking

A video with any remaining error-level finding after deterministic fixes is excluded from automatic operations. The report records the proposed safe fixes and the unresolved errors, but the executor receives no operation for that video.

## Live-state guards

For each operation the executor accepts exactly two canonical live states:

- the planned before-state: ready to write;
- the planned after-state: already applied, so the run is idempotent.

Any third description state is a hard conflict and is never overwritten. Full-record YouTube revision drift is tolerated only when the description still matches the before-state, because YouTube may refresh etags or server-managed metadata independently.

## Write safety

An executing batch uses:

- one local process lock per account/channel;
- a backup written before the first mutation;
- incremental result logging before and after each attempt;
- bounded post-write verification retries for eventual consistency;
- a final whole-batch postflight;
- rollback of every attempted operation, including the operation whose immediate verification failed;
- description-state guarded rollback that does not depend on unstable full-record revisions;
- distinct `failed_rolled_back` and `failed_partial_rollback` statuses.

The local lock does not prevent manual YouTube Studio edits or writers on another computer. Description-state checks and final postflight remain the authoritative protection.

## Ruleset rebuild

After an automation rule changes, run `scripts/rebuild_youtube_copy_plan.py` on a completed apply result. It recomputes each original description with the current rules and produces a guarded corrective plan only for outputs that differ. It does not revert the whole batch.
