# СВОДКА — full-restart production audit — 2026-08-08

Scope: restart audit of the current `main` for `@deep_info_life` / `СВОДКА`, including the auditor's own prior changes, current generic Telegram runtime, all Svodka workflows, the 14-item pilot queue for 2026-08-09..15, and a fresh primary-source revalidation.

Code/docs baseline immediately before this record: `main@e7c4e41c91d250ded6d22c70980211c7f743cda0`.

This pass deliberately did not trust conclusions from earlier audit waves. Every high-risk boundary was re-read from current repository state.

## Safety state re-proved

- `content/telegram/channels/svodka.json` remains `provider_writes_authorized=false`.
- Exact channel remains `@deep_info_life`, chat id `-1003527567039`.
- Shared posting bot remains `@preaching_mp3_bot`, bot id `8716602202`.
- The same underlying Telegram bot intentionally serves multiple channels; shared token reuse is not a target selector or a defect by itself.
- `content/telegram/svodka/approved-release-2026-08.json` is absent.
- `state/svodka-telegram` exists, but the publication ledger is absent before authorization.
- No Telegram provider mutation was performed during this restart audit.
- Current ordinary push-run `Svodka quality` green status is still not externally observable through the available connector/status surfaces; this document does not claim green CI from source inspection alone.

## New findings found only after restarting the audit

| # | Finding | Severity | Resolution |
|---:|---|---|---|
| 1 | The installed scheduled publisher exposed `workflow_dispatch`; after future activation a manual Run workflow could have executed the same scheduled mutation job if it happened inside an eligible window. | P1 accidental-write surface | Publishing job now requires `github.event_name == 'schedule' && github.ref == 'refs/heads/main'`. Manual scheduler dispatch is a provider-free skipped job. |
| 2 | `Svodka quality` originally used path filtering. GitHub documents a bounded diff evaluation for path filters; large audit waves could theoretically omit a relevant Svodka path from evaluation. | P1 CI coverage | Removed `paths` entirely. Quality runs on every push to `main`; concurrency cancels stale quality runs. |
| 3 | Shared production dependencies `telegram_models.py`, `telegram_transport.py` and `requirements/telegram-publisher.txt` could change without being part of the focused Svodka quality surface. | P1 CI coverage | Quality now tests those shared modules and installs the exact production Telegram lock after the development project before `pip check`. |
| 4 | New scheduled/reconciliation workflows and reconciliation tests were not all part of the focused quality surface. | P1 CI coverage | All current Svodka writer/recovery workflows and their regression tests are covered. |
| 5 | Provider-capable workflows did not prove that their exact current code SHA had passed the full Svodka quality workflow. A bad `main` commit could theoretically reach cron while its quality run was still running or red. | P1 release/runtime gate | Added exact-SHA GitHub Actions quality proof. Canary and scheduler require a completed successful `Svodka quality` for their own `GITHUB_SHA` before Telegram preflight or state/provider mutation. |
| 6 | First implementation of exact-SHA proof assumed workflow-run `path` lacked a ref suffix. Real GitHub REST responses may use `.github/workflows/svodka-quality.yml@main`. | blocking self-found regression | Helper accepts the real `@main` form and plain fallback; fixture now models the real REST response. |
| 7 | Skipped-send reconciliation had the same workflow-path assumption and did not explicitly require the source run to be completed or its event to match the writer. | P1 recovery provenance | Reconciliation normalizes `@ref`, requires `status=completed`, canary event `workflow_dispatch`, scheduler event `schedule`, exact attempt/head SHA, persisted intent success and provider-send `skipped`. |
| 8 | Draft validation did not actually reject two posts sharing one configured time slot, despite earlier audit text claiming slot uniqueness. Equal timestamps were also allowed by ordering logic. | P1 schedule contract | Draft timestamps must be strictly increasing, use exact minute boundaries, and each `(local date, HH:MM)` slot may appear only once. |
| 9 | Quiz/poll options could be duplicates after superficial whitespace/case changes. | editorial/runtime contract | Interactive options must be unique after `strip().casefold()`. |
| 10 | Generic immutable release ordering also allowed equal `scheduled_at` values. | P2 defense in depth | Release schedule is now strictly increasing even if a caller bypasses Svodka draft construction. |
| 11 | Generic structural publication window lasted until the next item; a delayed 10:30 GitHub cron could theoretically backfill near the 19:30 slot. | P1 editorial timing | Added Svodka-specific 120-minute maximum provider lateness. Canary and scheduler check freshness before Telegram preflight. |
| 12 | Initial canary freshness checked only the requested item time, not that it was the strict-next ledger item before provider read. | P1 unnecessary provider-read surface | Canary now proves strict-next identity and 120-minute freshness locally before Telegram preflight. |

## Exact-SHA quality proof contract

Provider writers now use the GitHub Actions REST API as a runtime gate. A qualifying quality run must match all of the following:

- workflow file `svodka-quality.yml`;
- exact writer `GITHUB_SHA`;
- `head_branch=main`;
- `status=completed`;
- `conclusion=success`;
- event `push` or explicit full `workflow_dispatch` quality run;
- workflow path `.github/workflows/svodka-quality.yml` or the REST form `.github/workflows/svodka-quality.yml@main`.

Failure to obtain this proof is availability loss only: the provider workflow fails closed before Telegram preflight or durable dispatch intent.

## Publication freshness contract

Svodka provider access is intentionally stricter than the generic state window.

- Freshness begins at exact immutable `scheduled_at`.
- Maximum automatic/manual lag is 120 minutes.
- Effective deadline is the earlier of `scheduled_at + 120 minutes` or the generic structural next-slot boundary.
- Manual canary must be the strict-next item and fresh before any Telegram read.
- Scheduled publisher evaluates strict-next freshness before any Telegram read.
- An over-late morning item remains provider-ineligible even if its broader structural state window has not reached the evening slot yet.
- At the structural boundary, state-only skip recovery may mark the stale item `skipped/impossible`; it is never automatically backfilled.

GitHub explicitly documents that scheduled workflows can be delayed and, under high load, sometimes dropped. The two-hour policy therefore tolerates scheduling delay without sacrificing the editorial meaning of the fixed 10:30 / 19:30 slots.

## Library-level P2 remaining

`telegram_multichannel_state.initialize_ledger(release)` is a low-level pure-Python helper that still does not itself repeat the `release_authorized` check. The production CLI and every committed remote-state workflow require authorization before durable state creation, and the helper cannot contact Telegram. This is retained as a small P2 defense-in-depth item rather than performing a large untested full-file replacement of the critical state module in this audit environment.

No production activation should treat this P2 as authorization. The authorization boundary remains the validated immutable release + guarded CLI/workflows.

## Fresh current API / platform verification

The following primary/official technical references were rechecked in this restart pass:

1. https://docs.github.com/en/rest/actions/workflow-runs
2. https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
3. https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
4. https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/control-workflow-concurrency
5. https://docs.github.com/en/actions/concepts/security/github_token
6. https://docs.github.com/en/actions/reference/security/secure-use
7. https://core.telegram.org/bots/api
8. https://core.telegram.org/bots/api-changelog
9. https://core.telegram.org/bots/api#getchatadministrators
10. https://core.telegram.org/bots/api#chatmemberadministrator
11. https://core.telegram.org/bots/api#sendpoll
12. https://core.telegram.org/bots/api#poll
13. https://core.telegram.org/bots/api#message

Current conclusions retained:

- `getChatAdministrators(return_bots=true)` is valid current Bot API behavior; it was added in Bot API 10.0 and is not an obsolete/custom field.
- Current poll fields include the Svodka-pinned `allows_revoting`, `members_only`, `correct_option_ids`, `description`, `is_anonymous` and `allows_multiple_answers` semantics.
- GitHub workflow-run APIs support filtering by exact `head_sha` and status, enabling the exact-SHA quality gate.
- Scheduled workflows are not guaranteed to begin exactly on time, which justifies an explicit editorial freshness boundary rather than assuming cron punctuality.

## Fresh primary/official source revalidation of all 14 posts

The queue was re-read against current primary/official sources rather than copied from the previous audit ledger:

14. Venus rotation/orbit: https://science.nasa.gov/venus/venus-facts/
15. Venus solar day distinction: https://science.nasa.gov/earth/climate-change/nasa-climate-modeling-suggests-venus-may-have-been-habitable/
16. Goldfish day-to-day relearning / long-term memory measure: https://pubmed.ncbi.nlm.nih.gov/935220/
17. Goldfish prolonged discrimination learning: https://onlinelibrary.wiley.com/doi/10.1901/jeab.1979.31-259
18. Wombat cubic feces mechanics: https://pubs.rsc.org/en/content/articlelanding/2021/sm/d0sm01230k
19. Lunar laser ranging and 3.8 cm/year: https://www.nasa.gov/missions/laser-beams-reflected-between-earth-and-moon-boost-science/
20. NASA tidal explanation of lunar recession: https://science.nasa.gov/solar-system/moon/10-things-what-we-learn-about-earth-by-studying-the-moon/
21. NASA/ILRS tidal dissipation and expanding lunar orbit: https://ilrs.gsfc.nasa.gov/about/reports/tides.html
22. Cephalopod hearts and hemocyanin: https://ocean.si.edu/ocean-life/invertebrates/octopuses-squids-and-relatives
23. Cephalopod chromatophores: https://ocean.si.edu/ocean-life/invertebrates/how-octopuses-and-squids-change-color
24. Aug. 12, 2026 eclipse path: https://science.nasa.gov/eclipses/future-eclipses/total-solar-eclipse-on-august-12-2026/
25. NASA Aug. 12 eclipse jet/balloon science: https://science.nasa.gov/science-research/heliophysics/nasa-science-soars-during-august-total-solar-eclipse/
26. NOAA lightning temperature: https://www.nesdis.noaa.gov/about/k-12-education/severe-weather/what-causes-lightning-and-thunder
27. American crow threatening-face experiment: https://www.sciencedirect.com/science/article/pii/S0003347209005806
28. Sunflower circadian heliotropism / mature east orientation: https://www.ucdavis.edu/news/sunflowers-move-clock
29. Shark lineage / 420 Ma scales: https://ocean.si.edu/ocean-life/sharks-rays/sharks
30. ESA tardigrade Foton-M3 experiment: https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Research/Tiny_animals_survive_exposure_to_space
31. ESA 2026 TARDIS dataset: https://esdcdoi.esac.esa.int/doi/html/data/hre/hreda/ea4ded24-c367-4245-96dd-e1eedb98cf81.html
32. Purdue Materials Engineering Eiffel thermal expansion: https://engineering.purdue.edu/MSE/about-us/gotmaterials/Buildings/patel.html
33. Official Eiffel Tower thermal/solar movement: https://www.toureiffel.paris/en/news/history-and-culture/why-does-eiffel-tower-change-size
34. Kew Cavendish banana botanical classification: https://www.kew.org/plants/cavendish-banana
35. Proceedings B bottlenose dolphin social memory: https://pmc.ncbi.nlm.nih.gov/articles/PMC3757989/

### Editorial findings from the fresh pass

- **Venus:** current wording correctly distinguishes ~243-day sidereal rotation from ~117-day solar day and ~225-day year. No regression.
- **Goldfish:** the 1976 paper explicitly uses day-2 savings in relearning as a long-term-memory measure; paired with prolonged discrimination learning, the three-second-memory myth wording remains defensible.
- **Wombat:** last ~17% of intestine and nonuniform wall mechanics remain correctly summarized.
- **Moon:** 3.8 cm/year and the tidal mechanism are both supported; the fresh pass added a second NASA mechanism check rather than relying only on the ranging page.
- **Octopus:** three hearts, copper-based hemocyanin and rapid chromatophore color change remain supported.
- **Eclipse:** NASA's current 2026 page explicitly includes northern Russia and a small corner of Portugal in totality; current post is complete. The NASA science page confirms the high-altitude jet and balloon program.
- **Lightning:** NOAA still gives roughly 30,000 °C / five times the Sun's surface comparison used by the quiz.
- **Crows:** current post stays narrowly tied to the threatening-mask field experiment and ≥2.7-year recognition rather than claiming universal permanent human-face memory.
- **Sunflower:** young tracking, circadian control, mature east orientation and pollinator benefit remain supported.
- **Sharks:** Smithsonian still states >400 Ma lineage and ~420 Ma confirmed scales; current modern-species caveat remains important.
- **Tardigrades:** ESA explicitly states ~3000 animals and 12-day Foton-M3 exposure; the 2026 archive record is current.
- **Eiffel:** the official Tower page says vertical seasonal height change is only a few millimeters and daily solar asymmetry can move the top in an ~15 cm curve; Purdue separately gives ~15 cm hot-to-cold thermal dimensional change. The current post deliberately distinguishes these effects and does not repeat the rejected claim that the tower simply becomes exactly 15 cm taller in summer.
- **Banana:** Kew's botanical berry classification remains the correct quiz answer.
- **Dolphins:** the original study reports separation up to 20.5 years and frames social recognition as lasting at least 20 years; current wording remains supportable.

**Editorial result: 14/14 remain publishable candidates; no new factual STOP was found in the restart pass.** They remain draft/write-disabled until exact candidate review and release authorization.

## Current readiness verdict

Architecture is now stronger than at the start of this restart pass, but production activation is still intentionally closed.

Blocking activation evidence still required:

1. Actual completed successful `Svodka quality` on the exact activation `main` SHA.
2. Fresh read-only Telegram preflight for the exact shared bot + `@deep_info_life` target.
3. Exact review of the canonical 14-item `svodka-review-candidate` and retained digest.
4. Authorized immutable release committed from that exact candidate/current binding.
5. Profile write gate enabled, followed by a new exact-SHA successful quality proof.
6. One initialized ledger for that release digest.
7. One strict-next manual canary inside its 120-minute freshness window.
8. Durable exact `published / verified` receipt.

Only after those proofs may the already-installed cron perform a scheduled mutation. A manual Run workflow on the scheduler cannot substitute for cron, and a stale slot cannot be used as an automatic backfill.
