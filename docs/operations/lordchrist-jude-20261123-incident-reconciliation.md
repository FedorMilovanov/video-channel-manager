# Jude 1:5 — reconciliation of the stalled 11 November GitHub run

Date: **23 November 2026**. Exact LordChrist queue identity: `lordchrist-telegraph-jude-1-5-20261105`. Exact original article Git blob: `dd15da234a74eb474963d275c6a9bccfcadb9985`. The cover is `909106bc78e05e323815e96fdf7e01dc7dd22eff`. This is a one-off approved **manual release**, not a scheduler/catch-up.

## Old queued run and immutable prevention of future mutation

GitHub Actions run [43098273140](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/43098273140) was requested on 11 November at SHA `ba435ff17e726c803674c79273eb0ac07f2478bd`. At this review it reports `queued`, `run_attempt=1`, no conclusion, **zero jobs and zero artifacts**. A previous ordinary cancel request returned `Cannot cancel a workflow run that is completed`, contradicting GET. Neither that response nor `queued` is recorded as a verified cancellation; no force-cancel success is asserted.

The **immutable old workflow source** at `ba435ff17e726c803674c79273eb0ac07f2478bd:.github/workflows/lordchrist-telegraph-poster.yml` already contained a hard `current_main == GITHUB_SHA` assertion in the first publishing gate **before the first external-provider stage** (lines 135–140), and repeated that gate immediately before both `send-page` and `send-telegram` (lines 252 and 327). That old SHA is not current main. Thus, even if GitHub eventually schedules this anomalous old run, the old immutable publishing workflow must reject it **before any provider mutation**, unless someone deliberately resets `main` to the obsolete SHA. No such reset is part of this release. Do not rerun that run.

## External and durable observations (bounded)

- Protected `state/lordchrist-telegram` Telegraph ledger read on 23 November: **17 entries, no Jude ID or claim**. An absence in this ledger alone is not proof of external absence.
- Independently verified official account inspection on [run 45014714988](https://github.com/FedorMilovanov/video-channel-manager/actions/runs/45014714988), completed 22 November: stable two-scan account inventory with **20 pages**, **0 exact-title matches**, **0 related-title matches**; verified account anchor to an existing owner receipt. It covered a single owned account and **did not** inspect other accounts, page contents or all Telegram histories.
- The earlier 13 Charnock chapter posts have Telegram IDs through 1603 in the ledger. The user's present instruction explicitly requires issuing Jude now rather than assuming another Sunday cron.
- Repo variables already bind `LORDCHRIST_TELEGRAPH_APPROVED_PUBLICATION_ID` to the exact Jude ID, `LORDCHRIST_TELEGRAPH_APPROVED_ARTICLE_BLOB_SHA` to `dd15da...`, and `LORDCHRIST_TELEGRAPH_POSTING_ENABLED=true`. None of these variables bypass the staged durable state or main/CI gate.

## Narrow decision and remaining hard requirements

Remove only the static **exact-Jude-ID** staging prohibition introduced by PR #1082. Keep the same-blob **renamed-ID prohibition**, keep the backlog report conservative (no automatic date suggestions), keep both before-provider durable-claim pushes, same serialized writer, `GITHUB_RUN_ATTEMPT == 1`, current-main successful `ci.yml` and owner binding. Reject any existing state identity on `prepare-page` and any incomplete/foreign state on subsequent stages. No alternate publisher, manual Telegra.ph creation, provider token disclosure, historical replay, or Charnock release changes.

**This reconciliation is not a publication.** After merging this reviewed change and checking the exact current-main CI and fresh protected state, use only the existing `lordchrist-telegraph-poster.yml` with `action=publish`, the exact Jude publication ID, and `confirm=PUBLISH:lordchrist-telegraph-jude-1-5-20261105`. Record one new workflow ID, then require both a Telegra.ph URL and a verified `@lordchrist` Telegram `message_id` in the durable ledger. Any ambiguous intent blocks retries. Disable the temporary Telegraph posting variable after the attempt without disturbing another owner-authorized operation.
