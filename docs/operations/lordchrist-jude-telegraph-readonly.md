# Jude 1:5: bounded Telegraph account inspection

This is a **read-only diagnostic**, not a publisher, duplicate-proof certificate, date proposal or
release authority. The owning content is PR [#783](https://github.com/FedorMilovanov/video-channel-manager/pull/783);
the current execution boundaries are in the [release calendar](2026-11-21-release-calendar.md)
and [current state](current-state.md). It never modifies Telegram, Telegraph, Actions variables,
protected state or source content.

After this workflow has been reviewed and merged to current `main`, and exact-main CI has passed,
its owner may invoke `lordchrist-jude-telegraph-readonly.yml` on `main`. It uses the retained
Telegraph token **inside GitHub Actions only**, with the read-like `getAccountInfo` and
`getPageList` methods; the token never appears in the URL or output. There is no Telegram token,
provider-write method, schedule, state push or release-variable access. A current-main check before
and after the scan and a state-ref check after it constrain the observation. No result is printed
if those checks fail.

The probe:

1. checks the exact Jude article and cover Git blobs, queue identity and canonical channel binding;
2. checks the durable ledger's previously verified **#1619** / 1525 article receipt, then requires
   that exact page in the retained account's list, establishing an account anchor rather than
   trusting an account display name;
3. reads the full account title list **twice**, up to 4,000 pages, with consistent page counts,
   unique canonical paths and no changed titles; a malformed, incomplete, redirected, unavailable
   or changing response stops without treating it as absence;
4. reports the number of literal exact-title matches and possible related-title matches. It emits
   **no page URLs, other titles, access tokens or unlisted page inventory** in public logs or the
   Actions notice. A match requires private owner reconciliation; it is not an invitation to
   create or send anything.

`ledger_status=no_entry` means only that this observed ledger had no entry. Even if both match
counts are zero, only **titles in this one account** were inspected. Changed titles, page bodies,
other accounts, other writers, private/removed Telegram posts and concurrency after the check are
not covered. Two scans are not an atomic provider snapshot. The report cannot settle old run
[43098273140](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/43098273140),
prove release-variable values, decide whether another article went out today, or authorize a
publication. Recheck all relevant state immediately before any separately authorized operation;
never replay or cancel an unknown effect blindly.
