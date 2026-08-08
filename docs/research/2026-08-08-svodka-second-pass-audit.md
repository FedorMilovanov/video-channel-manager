# СВОДКА — second-pass production audit — 2026-08-08

Scope: `@deep_info_life` / `СВОДКА`, generic Telegram multi-channel runtime, pilot queue 2026-08-09..15.

This document is a second-pass overlay. It does not replace `2026-08-08-svodka-technical-verification-ledger.md`; it records defects found after the first 70-source pass and the fixes applied directly to canonical runtime/workflow files.

## Safety state at the end of this pass

- Telegram profile remains `provider_writes_authorized=false`.
- `content/telegram/svodka/approved-release-2026-08.json` is intentionally absent.
- `state/svodka-telegram` exists, but its publication ledger is intentionally absent before an authorized release.
- No Telegram provider mutation was performed by this audit.
- Scheduled publishing remains intentionally absent until a verified manual canary exists.
- One shared Telegram bot (`@preaching_mp3_bot`, bot id `8716602202`) intentionally serves multiple channels. The shared credential is not a project selector; exact channel isolation is provided by profile + numeric chat id + binding + release + state + concurrency.

## Defects found and closed

| # | Finding | Severity | Resolution |
|---:|---|---|---|
| 1 | `Svodka quality` failed `ruff format --check` only on `svodka_queue.py`. | blocking CI | Canonical source formatted directly; no repair workflow. |
| 2 | Ledger workflow confirmed `INITIALIZE:<digest>`, while generic CLI required `INITIALIZE:<release_id>:<digest>`. Ledger initialization would always fail after release approval. | blocking activation | CLI contract unified to exact `INITIALIZE:<release_digest>` and regression tests added. |
| 3 | Profile declared `svodka-telegram-publisher`, while ledger-init/canary used `svodka-telegram-state`. A future scheduler could become a second concurrent writer. | blocking before scheduler | All Svodka state/provider writers use the profile canonical concurrency group with `cancel-in-progress: false`; regression added. |
| 4 | Future agents could misclassify the intentional shared Telegram bot token as cross-channel contamination. | operational ambiguity | Shared-bot invariant documented in Telegram migration runbook and nested runtime/workflow `AGENTS.md`. |
| 5 | Authorized generic release did not record which exact write-disabled candidate was reviewed. | release provenance | `reviewed_candidate_sha256` added; Svodka authorization records the exact candidate digest; authorized generic releases require provenance. |
| 6 | Authorization CLI checked profile identity but not the current pinned target binding. An old candidate could be approved after a binding change. | release provenance | `authorize-svodka-release` now requires `--binding` and exact digest/chat/bot match. |
| 7 | Quality and manual preflight built candidates with different `release_id` values, so otherwise-identical review candidates had different digests. | blocking review reproducibility | Both paths now use canonical `RELEASE_ID=svodka-pilot-2026-08`, the same candidate path and artifact name. |
| 8 | Local pre-provider failures in `send-once` could occur before outcome classification, leaving a durable intent as false `may_exist` even though no HTTP call began. | recovery correctness | Runtime now classifies all local pre-provider `ValueError` paths as explicit `not_dispatched` outcomes. |
| 9 | Ledger CLI could initialize an unauthorized candidate if called directly outside the guarded workflow. | defense in depth | CLI now rejects ledger initialization unless `release_authorized=true`. |
| 10 | Poll payload depended on Telegram defaults for `allows_revoting` and `members_only`, but these semantics are returned by current Bot API and are part of user-visible behavior. | P1 exact-payload semantics | Poll schema v4 freezes both flags into provider digest/request and verifies the returned Poll fields. Quiz defaults to `allows_revoting=false`; regular poll freezes `true`; `members_only=false` is explicit. |

## Review/release invariants after hardening

The intended chain is now:

`canonical queue` → `canonical target-bound review candidate` → `reviewed_candidate_sha256` → `authorized release` → `exact release digest` → `ledger` → `fresh target proof` → `durable intent` → `one provider call` → `durable exact outcome`.

The candidate identity is canonical across quality and manual preflight. Promotion requires the current pinned binding. The release payloads themselves remain deterministic and the profile digest intentionally excludes only the live-write enable bit.

## Current Telegram API verification

Primary API reference checked against the repository on 2026-08-08:

1. https://core.telegram.org/bots/api
2. https://core.telegram.org/bots/api-changelog
3. https://core.telegram.org/bots/api#sendpoll
4. https://core.telegram.org/bots/api#poll
5. https://core.telegram.org/bots/api#inputpolloption
6. https://core.telegram.org/bots/api#getme
7. https://core.telegram.org/bots/api#getchat
8. https://core.telegram.org/bots/api#getchatadministrators
9. https://core.telegram.org/bots/api#chatmemberadministrator
10. https://core.telegram.org/bots/api#message

Observed current contract:

- Bot API 10.2 is current (2026-07-14).
- `correct_option_ids` is current quiz API; reverting to old singular `correct_option_id` would be wrong.
- Poll exposes `is_anonymous`, `allows_multiple_answers`, `allows_revoting`, `members_only`, `correct_option_ids`, `explanation` and `description`.
- `sendPoll` supports those corresponding fields; the runtime now freezes and verifies all ones used by Svodka whose returned semantics are observable.
- `getChatAdministrators(return_bots=true)` is current API and is needed to inspect bot administrators reliably.
- `can_post_messages` remains the channel-specific administrator right used by preflight.

## GitHub Actions / CI primary verification

Exact current documentation checked in this pass:

11. https://docs.github.com/en/actions/concepts/security/github_token
12. https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
13. https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/control-workflow-concurrency
14. https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
15. https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments
16. https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts
17. https://docs.github.com/en/actions/reference/security/secure-use
18. https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs

Decisions retained:

- quality remains `contents: read` and provider-secret-free;
- mutating state workflows share one concurrency group;
- provider mutation is not retried blindly;
- candidate/proof are review artifacts, not authorization by themselves;
- a workflow rerun must not silently become a second scheduled side effect;
- production Environment approval remains optional future hardening, not a prerequisite to prove the pilot runtime.

## Factual pilot primary-source recheck

The canonical 14-item queue was re-read against these exact primary/official endpoints:

19. Venus rotation/orbit: https://science.nasa.gov/venus/venus-facts/
20. Venus solar day: https://science.nasa.gov/earth/climate-change/nasa-climate-modeling-suggests-venus-may-have-been-habitable/
21. Goldfish day-to-day memory: https://pubmed.ncbi.nlm.nih.gov/935220/
22. Goldfish discrimination learning: https://onlinelibrary.wiley.com/doi/10.1901/jeab.1979.31-259
23. Wombat cube mechanics: https://pubs.rsc.org/en/content/articlelanding/2021/sm/d0sm01230k
24. Lunar laser ranging: https://www.nasa.gov/missions/laser-beams-reflected-between-earth-and-moon-boost-science/
25. Cephalopod hearts/hemocyanin: https://ocean.si.edu/ocean-life/invertebrates/octopuses-squids-and-relatives
26. Cephalopod chromatophores: https://ocean.si.edu/ocean-life/invertebrates/how-octopuses-and-squids-change-color
27. 2026-08-12 eclipse path: https://science.nasa.gov/eclipses/future-eclipses/total-solar-eclipse-on-august-12-2026/
28. Eclipse science: https://science.nasa.gov/science-research/heliophysics/nasa-science-soars-during-august-total-solar-eclipse/
29. Lightning temperature: https://www.nesdis.noaa.gov/about/k-12-education/severe-weather/what-causes-lightning-and-thunder
30. Crow threatening-face memory: https://www.sciencedirect.com/science/article/pii/S0003347209005806
31. Sunflower heliotropism: https://www.ucdavis.edu/news/sunflowers-move-clock
32. Shark lineage: https://ocean.si.edu/ocean-life/sharks-rays/sharks
33. Tardigrade space exposure: https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Research/Tiny_animals_survive_exposure_to_space
34. Eiffel thermal expansion: https://engineering.purdue.edu/MSE/about-us/gotmaterials/Buildings/patel.html
35. Eiffel asymmetric solar movement: https://www.toureiffel.paris/en/news/history-and-culture/why-does-eiffel-tower-change-size
36. Banana botanical classification: https://www.kew.org/plants/cavendish-banana
37. Dolphin social memory: https://pmc.ncbi.nlm.nih.gov/articles/PMC3757989/

Some publisher/NCBI endpoints may challenge automated readers, but they remain the canonical URLs already represented in the queue/evidence ledger. Official NASA/NOAA/Smithsonian/ESA/Purdue/Eiffel pages were directly re-read where applicable.

Editorial result of this pass: no new STOP was found after the earlier Eiffel rewrite and eclipse/source corrections. The queue remains draft/write-disabled until release review.

## Remaining activation gates, not hidden defects

These are intentionally still closed:

1. Obtain a green `Svodka quality` result on the exact current `main` SHA. The connector available to this audit exposes code/status data but does not expose ordinary push-triggered workflow runs reliably, so green must not be claimed without the actual run.
2. Run one fresh read-only Telegram preflight against the exact shared bot and `@deep_info_life` target.
3. Review the exact `svodka-review-candidate` artifact and retain its digest.
4. Authorize that exact candidate with the current pinned binding and commit the resulting immutable release.
5. Enable the profile write gate only after the release exists.
6. Initialize the ledger with `INITIALIZE:<release_digest>`.
7. Send one exact manual canary only.
8. Require durable `published + provider_effect=verified` receipt for that canary.
9. Add/enable scheduled publication only after that verified manual canary.

Until steps 1–8 are proven, absence of a scheduled publisher is correct behavior, not unfinished automation.
