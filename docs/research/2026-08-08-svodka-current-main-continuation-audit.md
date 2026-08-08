# СВОДКА — current-main continuation audit — 2026-08-08

This record continues, rather than rewrites, `docs/research/2026-08-08-svodka-full-restart-audit.md`.

Audited base before this provider-inert regression/audit branch: `main@8f7677faca9b77dd651ed11c375e636fc7b02b75`.

Scope: current repository state for `@deep_info_life` / `СВОДКА`, the shared generic Telegram runtime, exact release review, durable state gates, scheduler timing/recovery, the 14-item pilot queue for 2026-08-09..15, and a fresh primary/official-source revalidation.

No Telegram provider mutation is authorized or performed by this audit branch.

## Current live safety state

Re-proved against the audited base:

- project/profile: `svodka` / `@deep_info_life`;
- exact chat id: `-1003527567039`;
- shared bot: `@preaching_mp3_bot`, bot id `8716602202`;
- the shared bot intentionally serves more than one Telegram channel; the token authenticates the bot and is not a destination selector;
- destination isolation remains profile + exact numeric chat + immutable target binding + release + state branch + concurrency group;
- `content/telegram/channels/svodka.json` remains `provider_writes_authorized=false`;
- `content/telegram/svodka/approved-release-2026-08.json` is absent;
- `state/svodka-telegram/content/telegram/svodka/publication-ledger.json` is absent;
- therefore Svodka is still unarmed even though the scheduled workflow is installed.

## Current-main changes since the earlier full-restart audit

### 1. Exact reviewed candidate is now an operator input

The operational `authorize-svodka-release` path now requires the exact reviewed candidate digest through `--expected-candidate-sha256`.

Authorization is delegated to the shared provider-inert `authorize_release_candidate()` helper. That helper independently proves:

- exact candidate digest;
- current project/channel/profile digest;
- timezone and daily verified limit;
- current target binding belongs to the selected profile;
- exact target-binding digest;
- exact chat id;
- exact bot id and bot username;
- non-empty reviewer identity;
- timezone-aware review timestamp;
- candidate is not already authorized.

The Svodka CLI additionally performs early profile/binding checks, but those are not the sole authorization boundary.

### 2. Generic review signature drift was caught and repaired

A parallel generic hardening change strengthened `authorize_release_candidate()` to require explicit `profile=` and `binding=` arguments. The already-merged Svodka caller temporarily had the old call signature.

The mismatch was found by re-auditing current `main`, fixed by passing the already-loaded exact Svodka profile and binding, and proved by full repository CI before merge.

### 3. Ledger initialization closes its current-main TOCTOU window

`Svodka initialize publication ledger` already required exact-current-main `Svodka quality` before the operation. It now repeats that proof after local ledger construction and immediately before the durable state commit/push.

If `main` advances while the workflow is running, the locally created ledger cannot be committed to `state/svodka-telegram` by the stale run.

### 4. Bounded scheduler catch-up uses the existing state machine

Primary scheduled checks remain:

- 10:30 Europe/Moscow;
- 19:30 Europe/Moscow.

The same scheduled workflow now has bounded catch-up events:

- 11:17 Europe/Moscow;
- 20:17 Europe/Moscow.

The catch-up is not a second sender and has no alternate ledger. Every event uses the same `svodka-telegram-publisher` single-writer group and the same gates.

The 47-minute recovery point is inside the existing 120-minute provider freshness budget. It is intended only to recover a primary scheduled event that is delayed, dropped, or fails before durable provider intent.

Duplicate safety remains fail-closed:

- if the primary run already published and verified the slot, strict-next moves to a future item and catch-up is provider-ineligible;
- if the primary run left `dispatching` / `may_exist`, strict-next is blocked and catch-up cannot retry it;
- a GitHub rerun of a scheduled workflow attempt is still forbidden; catch-up is a separate scheduled run with attempt 1;
- daily verified limit remains 2 in Europe/Moscow;
- provider mutation transport retries remain zero.

### 5. Canary-before-scheduler boundary remains early

Before the first verified manual canary, scheduler activity ends before automatic stale-state mutation and before Telegram preflight.

After a manual canary, scheduler state recovery may skip only structurally expired pending items as `skipped/impossible`, then evaluates the new strict-next item against the 120-minute freshness gate.

### 6. All state-only writers are current-main bound

The following durable-state paths re-prove current-main exact-SHA quality immediately before their state push when a state delta exists:

- ledger initialization;
- manual expired-slot recovery;
- automatic scheduled expired-slot recovery;
- skipped-send reconciliation.

Provider outcome persistence after a real Telegram call is intentionally different: once a provider call may have happened, its result/evidence must be persisted even if `main` advances, rather than being discarded as stale code.

## CI evidence for the current hardening chain

The earlier red Svodka screenshot belonged to a superseded pre-repair baseline. The current chain has exact-head full-repository CI proofs:

1. Svodka exact release review + ledger provenance hardening:
   - PR #186;
   - exact head `49c24c4886247e0d470ce0e2ee5267505c6465c0`;
   - CI run `31255108062` / #3615: SUCCESS.
2. Compatibility fix after generic review binding hardening:
   - PR #188;
   - exact head `740da7a20d1b7a6845e48c142a65b9bb433b9c7f`;
   - CI run `31255375372` / #3621: SUCCESS.
3. Bounded same-runtime scheduler catch-up + runbook sync:
   - PR #190;
   - exact head `b1e53fa61708356d817c82345d29bc5838c0e175`;
   - CI run `31255600844` / #3625: SUCCESS;
   - Python 3.11/3.12/3.13, PowerShell Windows 5.1, PowerShell Windows 7 and PowerShell Linux 7 all passed;
   - Ruff correctness, Ruff formatting, strict typing, tests and dependency audit passed inside the CI matrix.

The exact activation `main` SHA must still have an actual completed successful `Svodka quality` run. A full-repository PR CI success does not substitute for that runtime gate.

## Fresh primary/official technical references

The technical assumptions used by the current runtime were rechecked against primary documentation:

1. https://docs.github.com/en/rest/actions/workflow-runs
2. https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
3. https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
4. https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/control-workflow-concurrency
5. https://docs.github.com/en/actions/concepts/security/github_token
6. https://docs.github.com/en/actions/reference/security/secure-use
7. https://core.telegram.org/bots/api
8. https://core.telegram.org/bots/api-changelog
9. https://core.telegram.org/bots/api#getchatadministrators
10. https://core.telegram.org/bots/api#sendmessage
11. https://core.telegram.org/bots/api#sendpoll
12. https://core.telegram.org/bots/api#poll
13. https://core.telegram.org/bots/api#message

Retained technical conclusions:

- GitHub scheduled workflows may be delayed under load; schedule is not an exact wall-clock guarantee.
- `workflow_dispatch` remains visible on the Svodka scheduler only for diagnostics; the mutating job itself requires event `schedule` on `main`.
- exact workflow-run/head-SHA checks are supported by the GitHub Actions REST surface used by the runtime gate;
- current Telegram Bot API supports the poll fields frozen by Svodka, including `correct_option_ids`, `description`, `allows_revoting` and `members_only`;
- ambiguous mutation transport/postflight outcomes remain `may_exist` and are never blindly retried.

## Fresh primary/official source revalidation of the 14-item pilot

The current queue was rechecked against primary papers and official institutional sources rather than relying only on the prior audit text:

14. Venus rotation/orbit: https://science.nasa.gov/venus/venus-facts/
15. Venus solar-day distinction: https://science.nasa.gov/earth/climate-change/nasa-climate-modeling-suggests-venus-may-have-been-habitable/
16. Goldfish next-day relearning / long-term-memory measure: https://pubmed.ncbi.nlm.nih.gov/935220/
17. Goldfish prolonged discrimination learning: https://onlinelibrary.wiley.com/doi/10.1901/jeab.1979.31-259
18. Wombat cubic-feces mechanics: https://pubs.rsc.org/en/content/articlelanding/2021/sm/d0sm01230k
19. Lunar laser ranging / ~3.8 cm per year: https://www.nasa.gov/missions/laser-beams-reflected-between-earth-and-moon-boost-science/
20. NASA lunar/tidal context: https://science.nasa.gov/solar-system/moon/10-things-what-we-learn-about-earth-by-studying-the-moon/
21. ILRS tidal dissipation / expanding lunar orbit: https://ilrs.gsfc.nasa.gov/about/reports/tides.html
22. Smithsonian cephalopod hearts / hemocyanin: https://ocean.si.edu/ocean-life/invertebrates/octopuses-squids-and-relatives
23. Smithsonian chromatophores / rapid color change: https://ocean.si.edu/ocean-life/invertebrates/how-octopuses-and-squids-change-color
24. NASA Aug. 12, 2026 eclipse path: https://science.nasa.gov/eclipses/future-eclipses/total-solar-eclipse-on-august-12-2026/
25. NASA Aug. 12 eclipse jet/balloon science: https://science.nasa.gov/science-research/heliophysics/nasa-science-soars-during-august-total-solar-eclipse/
26. NOAA lightning temperature: https://www.nesdis.noaa.gov/about/k-12-education/severe-weather/what-causes-lightning-and-thunder
27. American crow threatening-face experiment: https://www.sciencedirect.com/science/article/pii/S0003347209005806
28. UC Davis sunflower heliotropism/east orientation: https://www.ucdavis.edu/news/sunflowers-move-clock
29. Smithsonian shark lineage: https://ocean.si.edu/ocean-life/sharks-rays/sharks
30. ESA tardigrade Foton-M3 experiment: https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Research/Tiny_animals_survive_exposure_to_space
31. ESA TARDIS archive record: https://esdcdoi.esac.esa.int/doi/html/data/hre/hreda/ea4ded24-c367-4245-96dd-e1eedb98cf81.html
32. Purdue Eiffel thermal expansion: https://engineering.purdue.edu/MSE/about-us/gotmaterials/Buildings/patel.html
33. Official Eiffel Tower thermal/solar movement: https://www.toureiffel.paris/en/news/history-and-culture/why-does-eiffel-tower-change-size
34. Kew Cavendish banana / botanical berry classification: https://www.kew.org/plants/cavendish-banana
35. Proceedings B / PMC bottlenose dolphin social memory: https://pmc.ncbi.nlm.nih.gov/articles/PMC3757989/

### Editorial result

No new factual STOP was found.

High-risk wording remains hardened:

- Venus distinguishes ~243-day sidereal rotation, ~117-day solar day and ~225-day year;
- the Aug. 12 eclipse post includes northern Russia and the small Portugal segment alongside Greenland, Iceland and Spain, and the scheduled Aug. 11 wording correctly refers to the eclipse as occurring on Wednesday;
- crow wording stays tied to the actual threatening-mask experiment and at least 2.7 years of recognition;
- Eiffel wording does not conflate official vertical seasonal millimeters with larger thermal/solar movement effects;
- banana uses explicit Kew botanical classification;
- dolphin wording remains bounded to the original long-term social-memory study.

Editorial conclusion remains `14/14 publishable candidates`, but they are still draft/write-disabled until exact candidate review and release authorization.

## Provider-inert regression additions in this continuation

This audit branch adds focused regressions without changing production runtime:

- generic review accepts the exact Svodka profile + binding + reviewed digest;
- generic review rejects current Svodka profile drift;
- generic review rejects current Svodka target-binding drift;
- generic review rejects an unbound Svodka candidate;
- generic review rejects double authorization;
- manual canary + one verified scheduled post consume the two-per-day verified limit;
- a catch-up run cannot bypass an existing `dispatching/may_exist` intent;
- a GitHub scheduled rerun attempt is rejected while a distinct catch-up run remains a normal attempt-1 run.

These regressions deliberately use Svodka fixtures instead of importing Lordchrist research candidate tests into `Svodka quality`, preserving channel-level CI isolation.

## Remaining non-blocking P2 items

1. `telegram_multichannel_state.initialize_ledger(release)` is a low-level helper that still does not itself duplicate the authorization check. Production CLI/workflows enforce authorization before durable remote state and the helper cannot contact Telegram. This remains defense-in-depth, not the operational authorization boundary.
2. `authorize_svodka_release()` remains as an internal/test compatibility helper even though the operational Svodka CLI now uses the shared generic review helper. It may be retired later after tests are migrated, but it is not a provider path.
3. GitHub cron has no year field. The Aug. 9–15 schedule would be evaluated again in future years, but the immutable 2026 release publication-window activation gate makes those runs provider-inactive. Retire the pilot scheduler after the 2026 pilot for repository hygiene.

## Activation status after this audit

Production activation remains intentionally closed. Required sequence remains:

1. exact current-main successful `Svodka quality`;
2. fresh read-only Telegram preflight for exact bot/channel;
3. exact digest review of the 14-item target-bound candidate;
4. authorization with `--expected-candidate-sha256` and current profile/binding;
5. commit approved immutable release;
6. flip only the profile write gate;
7. obtain a new exact-current-main successful `Svodka quality` for the activation SHA;
8. initialize ledger once;
9. state-only skip any already-expired structural window if needed;
10. one strict-next manual canary inside the 120-minute freshness window;
11. durable `published / verified` receipt;
12. only then may primary/catch-up schedule events become provider-eligible.

No step in this continuation performs that activation.