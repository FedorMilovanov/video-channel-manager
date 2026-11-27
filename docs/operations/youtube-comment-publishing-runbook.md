# YouTube comment publishing runbook

This is the current operator route for reviewed YouTube comments. Follow [AGENTS](../../AGENTS.md), the [editorial standard](../youtube-comment-editorial-standard.md), [project identity registry](project-identity-registry.md), [shared quota contract](youtube-shared-project-quota.md), and [release/failure ownership](routine-release-and-failure-ownership.md).

## 1. Prove the execution route

Resolve the exact current `main` commit and its existing successful required CI, then use a clean verified runtime at that commit. Reuse this admission within the same work wave while the runtime and applicable policy remain unchanged; do not launch CI for the comment or wait for unrelated open PRs. Do not switch to a historical feature branch or disturb another operator's worktree. Check the canonical absolute VCM data root, exact registered account/channel and official OAuth permissions. Do not copy tokens, force a login, or select another alias to evade a refusal. A dry-run or green CI is not execution authority.

The historical standalone comment apply script is retired. Do not run its historical entrypoint or import it as an alternate executor.

## 2. Read and review the exact target

Use the canonical official client; where the video ID is known, use bounded exact-target reads rather than a full channel scan. Confirm public video ID, owner channel, current exact title and a complete strict moderation inventory (including held comments). An incomplete inventory does not prove absence.

Review the current description and all owner comments for distinct value and duplicate text. Preserve links and existing comments. Normally one useful comment is enough; zero is valid, a second requires a genuinely distinct evidence-backed subject. At most one may be pinned; this command does not pin. Keep source citations and exact reviewed text; do not manufacture facts or approval.

## 3. Freeze one reviewed comment plan

Use the existing `video_channel_manager.platforms.youtube.comment_plan` builder and validator (`make_comment_operation`, `build_comment_plan`, `validate_comment_plan`). Bind the exact registered account, channel, video ID, title, source snapshot and its timestamp, reviewed text, source IDs, and review timestamp. The plan must contain exactly one operation.

| Mode | Required reviewed owner map |
| --- | --- |
| `reviewed-first-comment` | Explicit empty `expected_owned_comments: {}`, proven by complete strict moderation inventory |
| `reviewed-additional-comment` | Nonempty exact owner comment ID to canonical text SHA-256 map |
| `reviewed-comment-update` | Nonempty complete owner map, exact existing comment ID, exact reviewed before-text and distinct new text |

Use canonical comment text digests, not a hash of an arbitrary raw HTTP response. Freeze and validate the resulting plan; manual changes require a newly reviewed plan and digest. Never use a new plan to bypass a previous uncertain effect.

For bulk Panorama comment work, use the existing reviewed Wave operator contract only for its admitted scope; do not repurpose that route for other projects. Use the update mode only for the existing exact ID; it shares the canonical lock, quota and mutation history with creates. A replacement create is not an update.

## 4. Optional standalone preflight (read-only)

```text
video-manager youtube apply-comment-add PLAN --account ALIAS --confirm-channel CHANNEL_ID
video-manager youtube apply-comment-update PLAN --account ALIAS --confirm-channel CHANNEL_ID
```

Choose the command matching the reviewed plan mode; the two commands invoke the same guarded execution core. For an ordinary owner-authorized operation with a reviewed exact plan, a separate dry-run is optional: the execute invocation performs these checks under lock before dispatch. Use standalone preflight for uncertainty, batch review or diagnosis, not as a second approval.

The command validates the plan, project binding, public title/identity, current complete owner-comment set and earlier intent evidence under the channel lock. An existing exact match is skipped; changed state or incomplete evidence blocks dispatch. Inspect the actual result and exit status. Dry-run creates no receipt and performs no POST.

## 5. Execute the authorized exact mutation

An explicit owner instruction to post or correct the requested comment supplies the bounded write scope; do not request the same permission again. Use the existing reviewed plan, verified runtime, integrated preflight and shared quota admission/verification reserve. Derive the exact technical confirmation arguments internally. No new PR or CI run merely for a comment operation; actual code changes follow the normal engineering process. Draft-only requests and unresolved effects remain blocked:

```text
video-manager youtube apply-comment-add PLAN --account ALIAS --confirm-channel CHANNEL_ID --execute --confirm-plan-sha256 SHA
video-manager youtube apply-comment-update PLAN --account ALIAS --confirm-channel CHANNEL_ID --execute --confirm-plan-sha256 SHA
```

Use the exact digest emitted by the frozen plan, not a placeholder. The existing executor reserves quota, checks owner identity/state, persists intent before a single POST (create) or PUT (update), and independently verifies exact comment ID, text hash and full owner inventory. First-create effect identity binds the channel and video independently of editable text. Additional creates preserve all prior owner comments. Updates preserve the existing comment ID and all other owner comments; the reviewed before digest and target ID bind the update identity. No second writer, blind retries or automatic pinning.

## 6. Reconcile uncertain outcomes

A missing receipt, transport failure or ambiguous POST or PUT is not evidence that the comment is absent. Preserve all existing intents and receipts, including the historical text-keyed journal namespace. Reconcile the exact video and comment through read-only checks. If the exact matching comment becomes visible, the original frozen plan and digest with the required execution confirmation can record the missing local receipt after independent direct and full-inventory readback; this recovery does not send another mutation. Dry-run never records a receipt. If the effect remains uncertain or the reviewed owner set differs, stop. Do not delete journals, change text, switch accounts or create another plan to evade the stop.

Report verified provider result and comment ID separately from repository implementation and local preflight. Public rendering and pin state are separate checks.

## 7. Exact reply to an existing comment

A reply is not a second top-level comment. Use the same reviewed plan builder with
\`action="reply"\`, \`mode="reviewed-comment-reply"\`, \`expected_comment_id\` and
\`expected_comment_text\` for the **parent**, \`expected_parent_author_channel_id\`
for its author, and explicit \`expected_owned_comments\` for the owner's replies
under that parent (empty only after complete reply inventory). Do not use this map
for the video's top-level comments. Preserve the observed parent text, which may
be provider-rendered plain text for another author's comment; only its author can
receive the original raw text.

Read \`YouTubeCommentWriter.read_reply_context\` for exact video/parent membership,
author, unchanged text, reply eligibility and complete bounded
\`comments.list(parentId=...)\` pagination. Require the thread's reported reply
count to agree; disagreement, missing author, malformed response or page cap
blocks the operation. This is the provider-visible inventory, not a promise that
YouTube exposes every hidden moderation state. Require raw text for the owner's
own replies; other viewers' plain display text is acceptable for inventory.

\`\`\`text
video-manager youtube apply-comment-reply PLAN --account ALIAS --confirm-channel CHANNEL_ID
video-manager youtube apply-comment-reply PLAN --account ALIAS --confirm-channel CHANNEL_ID --execute --confirm-plan-sha256 SHA
\`\`\`

For an ordinary authorized reply, the first (dry-run) invocation is optional; the execute invocation performs integrated preflight before dispatch. The same channel lock, shared quota journal, reviewed plan, intent namespace and
reconciliation rules apply. Reply effect identity binds channel/video/parent and
text hash; changed text cannot escape an unresolved prior attempt on the video.
Reserve the 50-unit reply POST and complete bounded verification reads. Verify
the exact returned reply ID, original owner text/hash and parent ID plus full
reply inventory; the receipt records the parent ID. If the inventory temporarily
lags the direct read, poll within the existing bounded verification schedule.
No blind POST retries, no alternate top-level comment, no implicit pinning.
If the response remains uncertain, use the original frozen plan to reconcile
an exact positive match without sending another POST.

## API references

- https://developers.google.com/youtube/v3/docs/commentThreads/list
- https://developers.google.com/youtube/v3/docs/commentThreads/insert
- https://developers.google.com/youtube/v3/docs/comments/list
- https://developers.google.com/youtube/v3/docs/comments/update
- https://developers.google.com/youtube/v3/guides/implementation/comments
- https://developers.google.com/youtube/v3/docs/errors
