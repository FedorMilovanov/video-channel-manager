# First autonomous Lordchrist scheduled publication proof

Date: 2026-08-08
Status: VERIFIED

## Provider result

- channel: @lordchrist
- publication_id: lordchrist-bunyan-fire-grace
- dispatch_mode: scheduled
- workflow_run_id: 31245659459
- workflow_run_attempt: 1
- code_sha: 29c764095cc4153e610b7f1a399d07ced2785578
- workflow_sha: 29c764095cc4153e610b7f1a399d07ced2785578
- intent_id: eea0f5c3476cdfbe7db2ef765a544f22
- attempted_at_utc: 2026-08-08T07:13:10.387473Z
- published_at_utc: 2026-08-08T07:13:13.636289Z
- published_at_moscow: 2026-08-08T10:13:13.636289+03:00
- message_id: 1472
- message_url: https://t.me/lordchrist/1472
- provider_effect: verified
- final_state: published
- bot_id: 8716602202
- bot_username: preaching_mp3_bot
- chat_id: -1001295216957

## Release identity

- approved_queue_digest: sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20
- source_payload_sha256: sha256:8440879ba07abd424a3563c330858a149e73d397489aaa26fb18741ff786920a
- presentation_policy_id: lordchrist-editorial-v2
- presentation_policy_sha256: sha256:daec0eb71658d815fd5d73ce6863f49b1a942afbb36cb8358dc689a87a73acc8
- provider_payload_sha256: sha256:8102f0cfde5d0307c85051c126b7425c68767ea8a1d59f66eca51935e0e209c1

## Safety-path observations

The GitHub Actions run completed successfully. The run identified the event as `schedule`, used run attempt 1, passed target preflight, passed production gates, prepared one strict-order dispatch, rendered an exact provider payload, persisted durable intent and rendered evidence on `state/lordchrist-telegram` before `sendMessage`, received a verified Telegram result, then persisted the final published state.

The ledger after the run contains `published / verified` for this publication. The next strict-order queue entry remains `pending / impossible`; no unresolved `dispatching`, `unknown`, or `may_exist` state was introduced by the scheduled publication.

## Operational conclusion

The pre-proof freeze condition defined in issue #168 is satisfied. Post-proof hardening and research-post v2 integration may proceed, subject to normal reviewed/green changes and an independent research-post canary before any staged research queue is armed.
