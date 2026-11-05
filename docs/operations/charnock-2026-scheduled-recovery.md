# @lordchrist / Stephen Charnock — incident closure and controlled recovery

Owner decision, 2026-11-05: **The eight Charnock posts №06–13 were intended to be scheduled, not published in a burst.** An agent dispatched them between 07:12–07:26 MSK and the owner deleted Telegram messages 1596–1603. Historical ledger receipts must NOT be erased or relabeled as never-published.

## Required outcome

- **Never** replay 2026-11-05 provider dispatches. No manual `PUBLISH:lordchrist-telegraph-charnock-*` path exists after this repair.
- Keep the full corrected latest-editorial Telegraph articles №06–13 that were actually created; their exact URL, canonical document Git blob, document SHA-256, original deleted Telegram ID, and Moscow date are pinned in `content/telegram/lordchrist/telegraph-v1/charnock/charnock-reschedule-2026.json`.
- Replace each owner-deleted Telegram announcement with **one** new message, only on its originally reviewed Tuesday/Friday date at 12:00 Moscow. Dedicated `lordchrist-charnock-scheduled-reissue.yml` is schedule-only; there is **no manual live dispatch**, no catch-up, no provider mutation without separate immutable-manifest SHA-256 approval and enabled gate.
- Persist one durable intent **before** `sendMessage`. Ambiguous responses or failed state pushes block replay. After sent receipt, obtain independent public Telegram readback before marking verified; preserve the original deleted receipt and its ID.
- Edit the **existing Telegram post** for early editions 01b/history-01/02/03/04; original Telegraph author tokens were lost, so a corrected **new Telegraph URL** is needed. Keep the historical original URL/ID in the ledger and create/edit exactly one per approval via PR #784 corrective workflow; do not send a new announcement.
- Never silently swap back to older text. Bind current corrected document SHA and audited replacement map in every release; if any byte changes, stop for fresh review.
- 05 is already published and must not be resent. `history-02` has no prior public post and must never be inferred as approved.
- Jude 1:5 is a **different** publication ID (`lordchrist-telegraph-jude-1-5-20261105`) that was merged in PR #783; its independent automation is scheduled **2026-11-07 14:00 Moscow**. Do not publish it through Charnock's recovery or alter its date. All actual @lordchrist writers share the `lordchrist-telegram-publisher` serialization group and `state/lordchrist-telegram` durable branch.

## Safety status and reactivation

Incident hold: `lordchrist-telegraph-poster.yml` disabled manually, `LORDCHRIST_TELEGRAPH_POSTING_ENABLED=false` with exact approval vars removed, `LORDCHRIST_CORRECTION_ENABLED=false`. Do not loosen this just to make a preview pass. PR #784 and its CI precede any correction provider writes. For the separate scheduled recovery, release authority is the reviewed exact manifest digest plus `LORDCHRIST_CHARNOCK_RECOVERY_ENABLED=true`; it is never an unrestricted token to post a queue.

Release completion is per article: exact revised Telegraph page verified, originally deleted Telegram ID remains historical, new replacement Telegram ID confirmed and publicly readable on its scheduled date, durable ledger marked `scheduled_reissue.state=verified`. Do not call the overall series closed before all eight date-scoped deliveries and five early correction edits are verified.


## Workflow parser repair after merge of #784 (2026-11-05)

The first main-branch push containing the two new Charnock Actions workflows
reported workflow-file failures before starting any jobs (runs 42059688291
and 42059690985). No Charnock provider call was made by those runs. The
source was unquoted YAML plain scalars containing the pip option
`--only-binary=:all:` immediately before whitespace. PR #794 changes the
install steps to valid YAML block scalars without changing their commands,
approval gates, or schedule. It also adds a CI-tested PyYAML syntax parse
for every workflow file, including a regression for the original error.
The publication hold remains until the repaired workflows are registered
and the exact merged main passes CI.


## Delayed public readback after Telegram edit (2026-11-05)

The first corrective run, `42064895183`, created the corrected №01b Telegraph page and received
a successful `editMessageText` response for **the original Telegram message 1582**. Its immediate
public-widget readback failed while the change was still propagating. Do not dispatch
another edit: the ledger intentionally remained `telegram_claimed`. Later independent
public readback confirmed the exact new link and absence of the former link, and the
original claim was reconciled in `state/lordchrist-telegram` commit `d71c814b`
without a second provider mutation.

Future corrections must make the edit only once and use bounded **read-only**
public-readback retries. Exhausting that window is a fail-closed, manual-reconciliation
condition; it never authorizes a second `editMessageText`.
