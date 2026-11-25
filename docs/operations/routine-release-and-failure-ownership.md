# Routine release operations and failure ownership

Status: operational contract; does not grant provider execution authority or override any platform, tool or client safety decision. Applies to all registered project keys. The existing platform-specific runbooks, state locks, rights/editorial review and quota guards remain authoritative.

## One owner request, one bounded operation

An explicit owner request identifying the project, exact input and desired effect is scope authority for that operation. The agent carries out routine evidence collection, plan construction and verification without asking the owner to copy internal hashes or repeat an unchanged approval. This does not supply absent content review, rights evidence, human listening, provider permissions or a client-side authorization/approval gate. Do not represent an agent-generated attestation as independent review.

Use the current-main repository-owned platform workflow and shared data root. The operator-facing result should be the exact target, accepted input identity, verified completed children, first unresolved child, blocking reason and next required action. Internal manifests and hashes are retained in machine state, not re-entered by the owner. No new provider client, parallel writer or special-case command for each release. If a supported workflow lacks an ordinary entrypoint, record that engineering gap separately; it is not permission to improvise a provider write.

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

## Implementation lanes

- #1126 owns the status projection and this operational contract; no live provider action.
- #1116 owns explicitly authorized additional YouTube comments; retain single-comment default and exact-state safeguards.
- #1119 owns its three existing Shorts; do not mix unrelated new media or publication permissions into that issue.
- A future unified publication interface must compose the existing verified platform state machines and be independently tested for no-replay, incomplete evidence, exact target identity, concurrent writer exclusion, client refusal, quota denial, and postflight. Its purpose is ordinary maintainable operation, not getting a rejected action past a client safety check. No claim of such an interface being deployed until actual exact-main evidence exists.
