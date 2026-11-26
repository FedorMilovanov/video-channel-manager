# YouTube comment publishing runbook

This is the current operator route for reviewed YouTube comments. Follow [AGENTS](../../AGENTS.md), the [editorial standard](../youtube-comment-editorial-standard.md), [project identity registry](project-identity-registry.md), [shared quota contract](youtube-shared-project-quota.md), and [release/failure ownership](routine-release-and-failure-ownership.md).

## 1. Prove the execution route

Resolve the exact current `main` commit and its successful required CI, then use a clean verified runtime at that commit. Do not switch to a historical feature branch or disturb another operator's worktree. Check the canonical absolute VCM data root, exact registered account/channel and official OAuth permissions. Do not copy tokens, force a login, or select another alias to evade a refusal. A dry-run or green CI is not execution authority.

The historical standalone comment apply script is retired. Do not run its historical entrypoint or import it as an alternate executor.

## 2. Read and review the exact target

Use the canonical official client; where the video ID is known, use bounded exact-target reads rather than a full channel scan. Confirm public video ID, owner channel, current exact title and a complete strict moderation inventory (including held comments). An incomplete inventory does not prove absence.

Review the current description and all owner comments for distinct value and duplicate text. Preserve links and existing comments. Normally one useful comment is enough; zero is valid, a second requires a genuinely distinct evidence-backed subject. At most one may be pinned; this command does not pin. Keep source citations and exact reviewed text; do not manufacture facts or approval.

## 3. Freeze one reviewed create plan

Use the existing `video_channel_manager.platforms.youtube.comment_plan` builder and validator (`make_comment_operation`, `build_comment_plan`, `validate_comment_plan`). Bind the exact registered account, channel, video ID, title, source snapshot and its timestamp, reviewed text, source IDs, and review timestamp. The plan must contain exactly one create operation.

| Mode | Required reviewed owner map |
| --- | --- |
| `reviewed-first-comment` | Explicit empty `expected_owned_comments: {}`, proven by complete strict moderation inventory |
| `reviewed-additional-comment` | Nonempty exact owner comment ID to canonical text SHA-256 map |

Use canonical comment text digests, not a hash of an arbitrary raw HTTP response. Freeze and validate the resulting plan; manual changes require a newly reviewed plan and digest. Never use a new plan to bypass a previous uncertain effect.

For bulk Panorama comment work, use the existing reviewed Wave operator contract only for its admitted scope; do not repurpose that route for other projects. For updates to existing comments, this single-create command is not an update executor. Require a supported exact-target route and exact reviewed before-state; if no current route is available, report the blocker instead of reviving the retired script or creating a replacement comment.

## 4. Canonical preflight (read-only)

```text
video-manager youtube apply-comment-add PLAN --account ALIAS --confirm-channel CHANNEL_ID
```

The command validates the plan, project binding, public title/identity, current complete owner-comment set and earlier intent evidence under the channel lock. An existing exact match is skipped; changed state or incomplete evidence blocks dispatch. Inspect the actual result and exit status. Dry-run creates no receipt and performs no POST.

## 5. Separately authorized exact create

Only after the exact plan and write scope are authorized, current-main quality is verified, preflight succeeds, and the shared quota guard has sufficient admission/verification capacity:

```text
video-manager youtube apply-comment-add PLAN --account ALIAS --confirm-channel CHANNEL_ID --execute --confirm-plan-sha256 SHA
```

Use the exact digest emitted by the frozen plan, not a placeholder. The existing executor reserves quota, checks owner identity/state, persists intent before a single POST, and independently verifies exact comment ID, text hash and full owner inventory. First-create effect identity binds the channel and video independently of editable text. Additional creates preserve all prior owner comments. No second writer, blind retries or automatic pinning.

## 6. Reconcile uncertain outcomes

A missing receipt, transport failure or ambiguous POST is not evidence that the comment is absent. Preserve all existing intents and receipts, including the historical text-keyed journal namespace. Reconcile the exact video and comment through read-only checks. If the exact matching comment becomes visible, the original frozen plan and digest with the required execution confirmation can record the missing local receipt after independent direct and full-inventory readback; this recovery does not send another POST. Dry-run never records a receipt. If the effect remains uncertain or the reviewed owner set differs, stop. Do not delete journals, change text, switch accounts or create another plan to evade the stop.

Report verified provider result and comment ID separately from repository implementation and local preflight. Public rendering and pin state are separate checks.

## API references

- https://developers.google.com/youtube/v3/docs/commentThreads/list
- https://developers.google.com/youtube/v3/docs/commentThreads/insert
- https://developers.google.com/youtube/v3/docs/comments/list
- https://developers.google.com/youtube/v3/docs/comments/update
- https://developers.google.com/youtube/v3/guides/implementation/comments
- https://developers.google.com/youtube/v3/docs/errors
