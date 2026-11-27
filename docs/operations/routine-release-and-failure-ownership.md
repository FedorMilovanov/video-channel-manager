# YouTube release status and failure diagnosis

Use the existing `AGENTS.md` owner-scope and provider mutation contract. Report the exact target, each requested deliverable's verified or pending state, and the first real blocker; a draft or PR is not a provider result. Check executor availability before preparing the payload.

## Routine editorial operations

For an explicit owner request on existing YouTube objects, follow `GET → validate exact owner/object and changed fields → existing guarded mutation → independent GET`. The agent produces any required plan, intent, digest and confirmation arguments within the requested scope. Do not ask for another approval of the same request, open a PR for provider data, or launch CI for a title, description, tags, playlist rename, aligned subtitle or comment edit. A supported verified runtime and actual required checks remain prerequisites; if a real code defect prevents execution, fix it once via the usual PR/CI process, then resume the original operation. Do not build a parallel writer. Only report genuine blockers; unknown outcomes, missing rights/evidence, scope expansion, protected release changes and client/provider refusals retain their existing handling below.

## Exact caption readback

Use `video-manager youtube captions VIDEO_ID --account ALIAS --confirm-channel CHANNEL_ID` for one complete owner-bound caption inventory. To archive one of its exact track IDs in SRT, append `--download-track CAPTION_ID --output NEW_FILE.srt`. No provider mutations, no automatic translation, no existing-file overwrite. The response distinguishes actual track IDs and snippets (including ASR, draft and processing status); a refused or incomplete list is not proof of missing captions. The shared inventory validator also serves the existing Panorama localization-preservation check. Do not equate an ASR track or a downloaded file with an accepted human subtitle.

For a new reviewed track use `video-manager youtube add-caption VIDEO_ID --srt FILE.srt --language LANG --name NAME --account ALIAS --confirm-channel CHANNEL_ID`. Default is a read-only preview; append `--execute` within the owner's exact requested operation. The existing channel lock, quota guard and durable intent apply. It validates timed UTF-8 SRT against exact duration, preserves existing tracks, and performs one official multipart insert without the retired sync parameter. Only serving manual track plus independent downloaded cue digest proves completion. If processing or ambiguous, the next invocation reconciles the prior language intent by GET only; never another POST while pending. Existing different manual tracks are preserved; replacement and deletion are outside this command. Editorial accuracy and rights remain prerequisites.

## Diagnose the actual failing boundary

| Evidence | Classification | Required response |
| --- | --- | --- |
| Explicit client-side safety rejection before dispatch | Client/tool authorization block | Preserve the exact error and existing evidence. Do not replay, disguise, split, encode or reroute the rejected action to defeat the decision. Use only the client's supported review/appeal mechanism if applicable; otherwise report the unresolved block and continue genuinely independent work. |
| Device offline, network failure or remote call timeout | Transport incident | Distinguish confirmed pre-dispatch from unknown outcome. Reconcile the existing call/process ID and durable state before any new invocation. Do not assume failure means no effect. |
| Repository preflight/validator denial | Workflow evidence or policy gap | Identify the exact guard and missing evidence. Supply truthful evidence when available; fix actual defects with regression tests, never weaken the guard or invent approval. |
| OAuth scope/target mismatch | Authorization or identity | Verify canonical account/absolute data root and exact target. Use official authorization flow if needed; no token copies or alias substitution. |
| Explicit provider quota refusal | Provider quota | Apply the shared project stop policy and preserve verification reserve. No account/project switching to avoid it. |
| Provider accepted/unknown result or missing readback | Unresolved provider effect | Preserve any returned remote ID and journal. Reconcile read-only; never blindly replay. |
| Provider-verified exact postcondition | Verified child | Retain evidence and advance only the next unmet child within the original authorized scope. |

Do not diagnose a client rejection as a provider quota failure, and do not infer an exact safety-filter trigger from generic error wording. Absence in a bounded device log is supporting evidence, not a complete audit. Review/appeal is a separate client-mediated decision, not a new authorization supplied by the repository.

## YouTube release status

`youtube_release_operations.status` returns a versioned **diagnostic projection**, not a raw journal or executable plan. It reports `initialization_required`, `review_pending_child`, `reconcile_read_only` or `complete` based on the validated existing state machine; a pending child is not permission to execute it. The output deliberately excludes all runtime data (including resumable upload URLs), raw responses and attempt-local parameters. It does not change persisted state, create a provider client or grant execution authority. `provider_writes_performed=0` describes only the status operation, not the historical release.

The supported local-only CLI is `video-manager youtube release-status --plan <exact-plan.json> --data-dir <absolute-canonical-data-root>`. It requires the explicit data root rather than guessing from the working directory, validates the plan and matching journal identity, and returns a machine-readable diagnostic report. A matching planned journal with no initialized release returns `initialization_required`, without a provider absence claim or executable next child. A missing, obsolete, conflicting or invalid journal exits with a diagnostic error, not proof of provider absence. Initialized playlist children must match the immutable plan. No OAuth or provider quota is used. This command cannot publish, reconcile, or authorize execution.

If a child is `may_exist`, report that child and no executable next child. Verified-child count excludes the separate successful existing-target absence proof; completion is derived from the canonical state machine, not the count. A completed release can contain explicit confirmed-absence evidence. Never replace the canonical ledger with the projection.

## Incident record and escalation

Keep one concise record: exact task/project, source SHA and media SHA when applicable, failure boundary and literal error (without secrets), dispatch evidence, known provider effect, last verified child, next allowed step, unresolved evidence. No raw credentials, session URLs or broad desktop history in chat, tickets or support reports. An engineering PR is not proof a third-party safety issue has been fixed. For a client-side rejection, see the vendor's [supported troubleshooting guidance](https://desktopcommander.app/help/troubleshooting/tool-call-blocked-by-safety-checks) and [OpenAI support](https://help.openai.com/en/articles/6614161-how-can-i-contact-support).
