# VK postponed text editing: guarded workflow and 2026-08-06 retrospective

Status: repository-owned capability hardened by issue #152 / PR #153.  
Surface: existing **attachment-free** postponed VK wall posts only.  
Mutation: one exact `wall.edit` at a time with project/community/post binding.  
Default cadence: 25 seconds between mutation attempts.

Historical IDs and counts in this document are evidence. They never authorize another execution.

## Supported boundary

Schema v1 edits only the text of explicitly reviewed postponed posts that have no attachments. It preserves:

- exact `project_key`, `community_id`, `owner_id`, and `post_id`;
- postponed-surface membership;
- original `publish_date`;
- exact approved before/after text;
- full postponed count;
- relevant text/date/ordered raw-attachment fingerprints of every non-target published and postponed post.

Schema v1 rejects `allow_attachments=true` and rejects every target that currently has an attachment. Arbitrary attachment editing or preservation requires a future reviewed schema; the successful attachment-free cleanup is not evidence for that capability.

The editor never creates posts, edits published posts, moves a post between surfaces, reconstructs missing posts, selects targets by text similarity, or solves CAPTCHA.

## Repository entrypoints

Python CLI:

```powershell
video-manager-vk-postponed-text plan REQUEST.json --output PLAN.json --account legendary-poet
video-manager-vk-postponed-text reconcile PLAN.json --output RECONCILE.json --account legendary-poet
video-manager-vk-postponed-text apply PLAN.json `
  --output-dir data/operator/EXACT-RUN `
  --account legendary-poet `
  --confirm-plan-sha256 sha256:... `
  --enable-provider-writes
```

Repository-owned PowerShell wrapper:

```powershell
& .\scripts\Invoke-VkPostponedTextEdit.ps1 `
  -Command plan `
  -InputPath .\request.json `
  -OutputPath .\plan.json `
  -AccountAlias legendary-poet
```

Apply requires both the full lowercase 64-hex plan digest and `-EnableProviderWrites`:

```powershell
& .\scripts\Invoke-VkPostponedTextEdit.ps1 `
  -Command apply `
  -InputPath .\plan.json `
  -OutputDirectory .\data\operator\EXACT-RUN `
  -AccountAlias legendary-poet `
  -ConfirmPlanSha256 sha256:... `
  -EnableProviderWrites
```

The wrapper validates paths and arguments and invokes only `video_channel_manager.cli.vk_postponed_text`. It contains no token handling and no direct VK transport.

## Request contract

A request binds:

- exact project/community/owner identity;
- expected total postponed-row count;
- sorted unique target post IDs;
- exact or prefix line-removal rules;
- exact expected match count for every rule in every target;
- `allow_attachments: false`.

A line matching two rules is a conflict. A missing or extra match blocks planning. Full before/after text must be reviewed before apply.

## Plan contract

Planning is read-only. It captures complete published and postponed wall surfaces. Every operation contains:

- deterministic operation ID;
- exact owner/post ID;
- exact publication timestamp;
- exact before and after text and SHA-256 hashes;
- an empty attachment list;
- exact removed lines and original line numbers.

The plan contains its request digest, source snapshot, and self-digest. Apply accepts only the exact confirmed digest.

## Single-writer contract

All apply/resume runs for the same local account alias and VK community contend on one stable lock under the configured data directory:

```text
data/locks/vk/<account-alias>-<community-id>.lock
```

The lock path is independent of the result/output directory. Two runs cannot bypass exclusivity by choosing different journal folders.

## Reconciliation states

Every target is classified from fresh live data:

- `before` — exact reviewed before text, owner, date, no attachments;
- `after` — exact reviewed after text, owner, date, no attachments;
- `conflict` — absent, published instead, changed identity/date, any attachment present, or third text state.

Resume skips `after`, dispatches only `before`, and stops before writing on any conflict.

## Mutation protocol

For each pending operation:

1. Wait the configured inter-operation delay.
2. Re-read the complete postponed surface and verify its total count.
3. Prove the target is still exact `before` and attachment-free.
4. Re-check immediately that `publish_date` remains farther away than `minimum_future_seconds`.
5. Persist an intent journal in a non-overwriting file.
6. Call `wall.edit` once with explicit owner, post, message, original publication date, and an empty attachment parameter.
7. Wait the postflight delay.
8. Re-read and classify exact outcome.
9. Persist a terminal child state before updating the aggregate result.

A successful HTTP response is not completion. Only exact live readback is completion.

## Retry policy

There is no blind mutation retry.

A transient failure such as HTTP 429 may be retried only after:

1. exact postflight proves the first mutation had no effect;
2. the retry delay completes;
3. a second exact read still shows `before`;
4. publication distance is checked again immediately before the second dispatch.

If delayed reconciliation discovers exact `after`, the same journal is rewritten to `verified_after_delayed_reconciliation` with `provider_effect=verified`.

Transport loss plus failed/incomplete readback, invalid JSON, count change, or a third state stops as `unknown_requires_reconciliation`. It is never retried.

VK error 14 stops as `stopped_captcha_required` after exact no-effect readback. No OCR, browser automation, URL reconstruction, or bypass is supported.

## Final postcondition

A successful result proves:

- every target is exact `after` and remains postponed;
- postponed count equals the immutable baseline;
- relevant raw non-target fingerprints are unchanged, including attachment order and access-key-bearing payload data;
- all child journals are terminal and agree with aggregate results;
- `live-before.json`, `live-after.json`, and `result.json` exist.

## Stop conditions

Stop without another mutation when:

- a full wall read is incomplete;
- postponed count differs from plan;
- a target is absent or no longer attachment-free;
- owner, ID, date, or text differs;
- provider effect cannot be reconciled;
- CAPTCHA is required;
- publication is too close;
- a non-target fingerprint changes;
- output directory belongs to another plan;
- confirmed plan digest differs;
- another writer owns the account/community lock.

## 2026-08-06 Lord God operation

Exact identity:

- project `lord-god-strength`;
- community `60805374`, owner `-60805374`;
- credential alias `legendary-poet` — credential name only, not project selector;
- target postponed IDs `12513` through `12541`;
- 29 attachment-free targets;
- postponed baseline `66`;
- non-target postponed rows `37`;
- approved plan SHA `sha256:8dcbe984cb24e003770fa3897ff3b7da351a34d92d4931ac3cb9a5707d2c1cbb`.

Final live proof:

- `29/29` exact after-state;
- `0` pending;
- postponed count `66/66`;
- 37 non-target postponed rows unchanged;
- published first quote post untouched;
- final status `succeeded`.

No replay is needed or authorized.

## Incident lessons

1. `already scheduled: 9` was a video-audit category, not wall-row count; raw surface count was 66.
2. The first preview removed only the translation line and exposed that the visible source line also needed removal.
3. Continuing after a missing ZIP produced misleading `$null`/1970 output; strict fail-fast orchestration is mandatory.
4. Rapid writes triggered HTTP 429 after three verified edits; readback proved the fourth had no effect.
5. Confirmed absence was once aggregated as unknown; these states must remain separate.
6. Partial success survived rate limits and CAPTCHA and must always be resumed, never replayed from the beginning.
7. CAPTCHA URLs returned `image_not_supported`/404; core code never reconstructs or solves challenges.
8. Repeated external ZIP versions delayed the durable fix; production behavior belongs in repository code and tests.
9. A 25-second cadence completed the final 11 edits without another CAPTCHA.
10. Second-pass audit found that output-directory locks, one-time publication checks, stale delayed journals, and broad attachment claims were insufficient; issue #152 hardened all four.
11. GitHub Actions #3208/#3209 remained queued and cancel endpoints returned HTTP 502; infrastructure failure explains missing proof but never equals green CI.

## Never do this

- Do not rerun the completed local packages or historical plan.
- Do not use inline `Invoke-RestMethod` or a standalone provider writer.
- Do not omit `publish_date`.
- Do not edit a target with attachments under schema v1.
- Do not select targets by broad regex or content similarity.
- Do not treat HTTP success, stdout, screenshot, or modal closure as provider proof.
- Do not retry an unknown effect.
- Do not automate CAPTCHA solving.
- Do not confuse the `legendary-poet` credential alias with the Legendary Poet project.
