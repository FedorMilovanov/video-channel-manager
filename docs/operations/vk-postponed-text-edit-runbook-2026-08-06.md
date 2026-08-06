# VK postponed text editing: guarded workflow and 2026-08-06 retrospective

Status: repository-owned supported capability after issue #147.  
Surface: existing postponed VK wall posts only.  
Mutation: `wall.edit` with exact project/community/post binding.  
Default cadence: 25 seconds between mutation attempts.

This document records both the reusable operating contract and the evidence from the Lord God quote cleanup. Historical IDs and counts teach the workflow; they do not authorize a new execution.

## Supported outcome

The capability edits only the text of explicitly reviewed postponed wall posts. It preserves:

- exact `owner_id` and `post_id`;
- postponed surface membership;
- original `publish_date`;
- every canonical attachment identity;
- every non-target published and postponed wall object.

It never edits published posts, creates posts, republishes a missing post, infers target IDs from text similarity, or solves CAPTCHA automatically.

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

PowerShell calls the package-owned CLI directly:

```powershell
$env:PYTHONPATH = Join-Path $Repo "src"
py -3.11 -X utf8 -m video_channel_manager.cli.vk_postponed_text `
  plan .\request.json `
  --output .\plan.json `
  --account legendary-poet
```

PowerShell is only the shell around the package implementation. No standalone PowerShell provider client is supported.

## Request contract

A request binds:

- exact `project_key`;
- exact community and owner IDs;
- expected total postponed-row count;
- sorted unique target post IDs;
- line-removal rules;
- exact expected match count for each rule in every target post;
- whether canonical attachments are allowed.

Example rule pair:

```json
[
  {
    "match": "exact",
    "value": "Авторский литературно-буквальный перевод с английского.",
    "expected_per_post": 1
  },
  {
    "match": "prefix",
    "value": "Источник: https://",
    "expected_per_post": 1
  }
]
```

A line matching two rules is a conflict. A missing or extra match blocks plan creation. The plan records the exact removed line and original line number for every operation.

## Plan contract

Plan generation is read-only. It captures both wall surfaces and requires a complete snapshot. Every operation contains:

- deterministic operation ID;
- exact owner/post ID;
- exact publication timestamp;
- exact before and after text;
- SHA-256 of both texts;
- sorted canonical attachment identities;
- exact removed-line evidence.

The plan includes its source snapshot, request digest, and plan self-digest. Apply requires the exact printed plan SHA-256.

## Reconciliation states

Every target is classified from fresh live data:

- `before` — exact reviewed before text, date, owner, and attachments;
- `after` — exact reviewed after text, date, owner, and attachments;
- `conflict` — absent from postponed, published instead, changed date, changed attachments, or text matching neither approved state.

A resumable run skips `after`, dispatches only `before`, and stops before writing when any target is `conflict`.

## Mutation protocol

For each pending operation:

1. Wait the configured inter-operation delay.
2. Re-read the complete postponed surface.
3. Prove the post is still exact `before`.
4. Persist an intent journal.
5. Call `wall.edit` once with explicit `owner_id`, `post_id`, `message`, `publish_date`, and `attachments`.
6. Wait the postflight delay.
7. Re-read the postponed surface and classify the exact result.
8. Mark `verified`, `confirmed_absent`, `captcha_required_confirmed_absent`, or `unknown_requires_reconciliation`.

A successful HTTP response is not completion. Only exact live readback is completion.

## Retry policy

There is no blind mutation retry.

A transient failure such as HTTP 429 may be retried only when postflight proves the post remains exact `before`. Before a controlled retry, the implementation waits and performs another exact read.

Transport loss, invalid JSON, incomplete reads, queue-count changes, or any third text state stop the operation for reconciliation.

VK error 14 stops with `stopped_captcha_required`. The core implementation does not perform CAPTCHA OCR, browser automation, URL reconstruction, or bypass. Wait for the provider restriction to clear, run read-only reconciliation, and invoke the same confirmed plan again. Existing `after` operations are skipped.

## Final postcondition

A successful result proves:

- every target is exact `after`;
- postponed count before and after is identical;
- all non-target postponed objects are unchanged;
- all published objects are unchanged;
- no target left the postponed surface;
- durable per-operation journals and final result exist.

## 2026-08-06 Lord God operation

Exact identity:

- project: `lord-god-strength`;
- community: `60805374`;
- owner: `-60805374`;
- target postponed posts: `12513` through `12541`;
- target count: `29`;
- full postponed count: `66`;
- non-target postponed count: `37`;
- approved plan SHA-256: `sha256:8dcbe984cb24e003770fa3897ff3b7da351a34d92d4931ac3cb9a5707d2c1cbb`.

Requested visible change:

- remove the translation/editorial line;
- remove the visible source URL line;
- preserve quotation, author, sermon title/number, Scripture reference, sermon date, publication date, and post identity.

Final live proof:

- total verified targets: `29`;
- pending targets: `0`;
- non-target postponed objects unchanged: `37`;
- postponed before/after: `66/66`;
- final status: `succeeded`.

## What went wrong and why

### 1. Audit summary count was misread

The audit stdout field `already scheduled: 9` described video scheduling classification, not the raw postponed-wall row count. The source artifact contained 66 postponed rows. Counting the wrong metric initially produced a false expectation of 29 total postponed rows.

Permanent rule: use the raw surface collection and its explicit row count for wall-edit scope. Never infer wall-row count from content-audit category summaries.

### 2. The first external package removed only one service line

The first cleanup plan removed the translation line but retained `Источник`. The desired outcome was clarified only after previewing the actual after text.

Permanent rule: plan preview must show full exact before/after content. Apply is forbidden until every visible line removal is explicit and reviewed.

### 3. Empty PowerShell variables produced misleading follow-on output

When a ZIP was missing, the operator continued past the first exception and later formatted `$null` as if a plan existed. This produced false lines such as a blank post and a 1970 timestamp.

Permanent rule: run guarded blocks with `Set-StrictMode`, `$ErrorActionPreference = "Stop"`, required-path checks, and explicit native exit-code checks. Never print success after a failed prerequisite.

### 4. Rapid mutation cadence triggered HTTP 429

The first apply verified three edits and then received HTTP 429 on the fourth. Postflight proved the fourth post remained exact before-state.

Permanent rule: 429 is not permission to replay. Reconcile first. A retry is allowed only after exact absence is proved. The supported default cadence is 25 seconds, not the earlier rapid loop.

### 5. Result accounting called confirmed absence “unknown”

An early local executor reported `unknown: 1` even though the operation record said `provider_effect: confirmed_absent`. That made a known no-effect result look ambiguous.

Permanent rule: result schemas keep `confirmed_absent`, `captcha_required_confirmed_absent`, and `unknown_requires_reconciliation` separate. Aggregate counters must not merge them.

### 6. CAPTCHA appeared after partial success

A slower resume verified five additional edits and then VK returned error 14 at post 12521. The exact postflight remained before-state, so partial success was durable and the stopped operation was safe to resume.

Permanent rule: preserve verified children and resume from the first non-verified operation. Never rerun the whole batch.

### 7. CAPTCHA image handling was not reliable

Provider URLs opened `image_not_supported` or returned 404. Reconstructing an API CAPTCHA URL did not recover a usable challenge.

Permanent rule: the core writer does not solve, transform, reconstruct, OCR, or bypass CAPTCHA. Stop, retain exact state evidence, wait, reconcile, and resume later.

### 8. ZIP/version treadmill delayed the real fix

Multiple local ZIP versions were used to patch behavior around the same provider operation.

Permanent rule: once the failure mode is understood, move the implementation into repository-owned code and tests. PowerShell stays an orchestrator. Future fixes land in the module, not a new standalone provider client.

### 9. Conservative pacing completed the operation

After a pause, the final run used a 25-second inter-operation delay. It verified posts 12531–12541 without another CAPTCHA and produced the final 29/29 proof.

Permanent rule: provider pacing is an operational control. Keep the conservative default; changing it requires new evidence.

## Stop conditions

Stop without another mutation when:

- the full wall snapshot is incomplete;
- postponed count differs from the plan;
- a target is absent from postponed;
- owner, date, attachment identity, or text differs;
- a provider effect cannot be exactly reconciled;
- CAPTCHA is required;
- any non-target object changes;
- the post is too close to scheduled publication;
- the confirmed plan digest differs.

## Never do this

- Do not use an inline `Invoke-RestMethod` or standalone Python writer.
- Do not omit `publish_date` on a postponed edit.
- Do not omit or invent attachment identities.
- Do not select posts by a broad text regex without exact IDs.
- Do not treat HTTP success, stdout, or a screenshot as provider proof.
- Do not retry an unknown effect.
- Do not automate CAPTCHA solving.
- Do not mix the `legendary-poet` credential alias with the Legendary Poet project identity.
- Do not edit published posts with this capability.
