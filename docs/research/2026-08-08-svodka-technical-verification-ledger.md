# СВОДКА — technical + factual verification ledger — 2026-08-08

Цель этого прохода — не собрать ссылки ради количества, а зафиксировать решения, которые влияют на production-пайплайн `@deep_info_life`: безопасность GitHub Actions, exact-target Telegram transport, отсутствие слепых retry, воспроизводимый review/release и границы фактологических утверждений.

Статусы:

- `adopted` — правило уже внедрено;
- `guard` — обязательная защита/ограничение;
- `next` — полезное усиление после pilot;
- `verified` — факт/формулировка проверены по первичному или официальному источнику.

## A. GitHub Actions / deployment / supply chain

| # | Источник | Проверка / решение | Статус |
|---:|---|---|---|
| 1 | https://docs.github.com/en/actions/concepts/security/github_token | `GITHUB_TOKEN` — job-scoped credential; self-push не должен быть основой каскада workflow. Убрали self-mutating repair workflow. | adopted |
| 2 | https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax | Явные `permissions` и маленькие обязанности workflow предпочтительнее «всё в одном». | adopted |
| 3 | https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets | Секрет передаётся через env, не печатается и не кладётся в state/artifacts. | adopted |
| 4 | https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments | Environment может ограничить доступ к production secret до approval. | next |
| 5 | https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments | Required reviewer подходит для будущего production gate после canary. | next |
| 6 | https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments | Deployment workflow должен иметь отдельный gate, а не смешиваться с редактурой. | adopted |
| 7 | https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run | `workflow_dispatch` используется до разрешения schedule. | adopted |
| 8 | https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/control-workflow-concurrency | State-changing Telegram jobs используют один concurrency group. | adopted |
| 9 | https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts | Review candidate — artifact, а не скрытая временная версия контента. | adopted |
| 10 | https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations | Attestation полезна для будущего long-lived release artifact, но для pilot не обязательна. | next |
| 11 | https://docs.github.com/en/actions/reference/security/secure-use | Third-party actions закреплены full-length commit SHA. | adopted |
| 12 | https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-security-updates | Dependabot security updates полезен для зависимостей и Actions. | next |
| 13 | https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-security-updates | Автоматические security PR можно включить отдельно от runtime публикации. | next |
| 14 | https://docs.github.com/en/code-security/concepts/secret-security/about-alerts | Репозиторий публичный: secret scanning — обязательный внешний слой контроля. | guard |
| 15 | https://docs.github.com/en/code-security/how-tos/secure-your-secrets/detect-secret-leaks/enable-secret-scanning | Не хранить BotFather token ни в JSON, ни в dispatch evidence. | adopted |
| 16 | https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments | Long-lived cloud credentials при появлении облачного deploy лучше заменять OIDC. | next |
| 17 | https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-google-cloud-platform | OIDC подтверждает общий принцип short-lived credentials; к Telegram token напрямую не относится. | next |
| 18 | https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-history | Production evidence должен позволять восстановить run id / attempt / SHA. | adopted |
| 19 | https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs | Для scheduled mutation повтор run attempt запрещён: повтор может создать второй side effect. | guard |
| 20 | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets | После pilot можно защитить `main`/state policy правилами repository ruleset. | next |

## B. Telegram Bot API / exact mutation verification

| # | Источник | Проверка / решение | Статус |
|---:|---|---|---|
| 21 | https://core.telegram.org/bots/api | Актуальный Bot API — источник контракта provider payload/response. | adopted |
| 22 | https://core.telegram.org/bots/api-changelog | Bot API 9.6 (2026): `correct_option_ids`, multiple-correct quizzes, poll `description`. | adopted |
| 23 | https://core.telegram.org/bots/api#sendpoll | `sendPoll` поддерживает `is_anonymous`, `allows_multiple_answers`, quiz fields и description. | adopted |
| 24 | https://core.telegram.org/bots/api#poll | После отправки проверяем returned Poll, а не считаем HTTP 200 достаточным. | adopted |
| 25 | https://core.telegram.org/bots/api#inputpolloption | Каждая option — отдельный `InputPollOption`; лимиты текста валидируются до отправки. | adopted |
| 26 | https://core.telegram.org/bots/api#getme | Preflight доказывает точный bot id + username. | adopted |
| 27 | https://core.telegram.org/bots/api#getchat | Числовой `chat_id` перепроверяется как channel identity. | adopted |
| 28 | https://core.telegram.org/bots/api#getchatadministrators | Bot должен реально находиться среди администраторов target channel. | adopted |
| 29 | https://core.telegram.org/bots/api#chatmemberadministrator | Для channel проверяется `can_post_messages`. | adopted |
| 30 | https://core.telegram.org/bots/api#message | После mutation проверяется message id и фактический returned chat. | adopted |
| 31 | https://core.telegram.org/bots/api#polloption | Returned options сверяются с immutable payload. | adopted |
| 32 | https://core.telegram.org/bots/api#pollanswer | Структура голосов не используется как подтверждение факта публикации; receipt берётся из returned Message. | guard |

## C. Python validation / tests / transport reliability

| # | Источник | Проверка / решение | Статус |
|---:|---|---|---|
| 33 | https://pip.pypa.io/en/latest/cli/pip_check/ | `pip check` остаётся blocking dependency-consistency gate. | adopted |
| 34 | https://pip.pypa.io/en/latest/topics/dependency-resolution/ | Dependency resolution может backtrack; runtime requirements держим минимальными и ограниченными. | guard |
| 35 | https://packaging.python.org/en/latest/specifications/dependency-specifiers/ | Версионные ограничения — часть воспроизводимого runtime contract. | adopted |
| 36 | https://packaging.python.org/en/latest/discussions/install-requires-vs-requirements/ | Отдельный concrete Telegram requirements file уместен для минимального publisher runtime. | adopted |
| 37 | https://docs.pytest.org/en/stable/how-to/parametrize.html | Contract matrices лучше покрывать parametrized tests, а не копиями тестов. | next |
| 38 | https://docs.pytest.org/en/stable/explanation/goodpractices.html | Editable install + отдельная test suite соответствуют рекомендуемому layout. | adopted |
| 39 | https://docs.pytest.org/en/stable/how-to/usage.html | Focused Svodka tests и full repository CI дополняют друг друга. | adopted |
| 40 | https://mypy.readthedocs.io/en/stable/existing_code.html | `mypy --strict` — целевой уровень для generic Telegram core. | adopted |
| 41 | https://docs.pydantic.dev/latest/concepts/validators/ | Cross-field invariants (quiz fields, schedule, exact source visibility) должны жить в model validators. | adopted |
| 42 | https://www.python-httpx.org/advanced/timeouts/ | Connect/read/write/pool timeout задаются явно. | adopted |
| 43 | https://www.python-httpx.org/advanced/transports/ | Provider mutation transport retries остаются `0`; read-only может иметь ограниченный retry. | adopted |
| 44 | https://docs.astral.sh/ruff/linter/ | `ruff check` — blocking correctness gate для нового runtime. | adopted |
| 45 | https://docs.astral.sh/ruff/formatter/ | `ruff format --check` проверяет canonical formatting, ничего не переписывая в CI. | adopted |

## D. Side effects / retry / CI security model

| # | Источник | Проверка / решение | Статус |
|---:|---|---|---|
| 46 | https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ | Timeout после side-effecting call не доказывает отсутствие эффекта; blind retry запрещён. | adopted |
| 47 | https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/ | Если provider не даёт idempotency key для send, клиент должен сохранять durable intent до запроса. | adopted |
| 48 | https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2 | Неидемпотентный request нельзя автоматически повторять без доказательства, что первый не применён. | adopted |
| 49 | https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html | Least privilege, secret hygiene, integrity и manual approval — базовые CI/CD controls. | adopted |
| 50 | https://slsa.dev/spec/v1.2/build-track-basics | Provenance полезна как следующий слой для immutable release artifacts. | next |

## E. Повторная фактологическая проверка pilot 9–15 августа

| # | Тема | Источник | Итог | Статус |
|---:|---|---|---|---|
| 51 | Venus sidereal/solar day | https://science.nasa.gov/venus/venus-facts/ | 243 суток вращение, ~225 суток год, retrograde. | verified |
| 52 | Venus solar day | https://science.nasa.gov/earth/climate-change/nasa-climate-modeling-suggests-venus-may-have-been-habitable/ | ~117 земных суток solar day; формулировка отделена от sidereal rotation. | verified |
| 53 | Goldfish learning | https://pubmed.ncbi.nlm.nih.gov/935220/ | Day-to-day relearning supports memory beyond «3 seconds». | verified |
| 54 | Goldfish discrimination | https://onlinelibrary.wiley.com/doi/10.1901/jeab.1979.31-259 | Prolonged discrimination learning above chance; убрана лишняя конкретика из текста. | verified |
| 55 | Wombat cubes | https://pubs.rsc.org/en/content/articlelanding/2021/sm/d0sm01230k | Cubes linked to last ~17% of intestine and nonuniform mechanics. | verified |
| 56 | Moon recession | https://www.nasa.gov/missions/laser-beams-reflected-between-earth-and-moon-boost-science/ | ~3.8 cm/year from lunar laser ranging. | verified |
| 57 | Cephalopod hearts/blood | https://ocean.si.edu/ocean-life/invertebrates/octopuses-squids-and-relatives | Three hearts / copper hemocyanin boundary supported. | verified |
| 58 | Cephalopod color | https://ocean.si.edu/ocean-life/invertebrates/how-octopuses-and-squids-change-color | Chromatophores and rapid neural control supported. | verified |
| 59 | Eclipse path 2026-08-12 | https://science.nasa.gov/eclipses/future-eclipses/total-solar-eclipse-on-august-12-2026/ | Added northern Russia + small Portugal; old incomplete wording replaced. | verified |
| 60 | Eclipse science | https://science.nasa.gov/science-research/heliophysics/nasa-science-soars-during-august-total-solar-eclipse/ | Aircraft/balloon science supported separately from path claim. | verified |
| 61 | Lightning temperature | https://www.nesdis.noaa.gov/about/k-12-education/severe-weather/what-causes-lightning-and-thunder | ~30,000 °C / about 5× solar surface. | verified |
| 62 | Crow face memory | https://www.sciencedirect.com/science/article/pii/S0003347209005806 | Original study: threatening mask recognition for at least 2.7 years. | verified |
| 63 | Sunflower tracking | https://www.ucdavis.edu/news/sunflowers-move-clock | Growing plants track; mature flowers face east. | verified |
| 64 | Shark lineage | https://ocean.si.edu/ocean-life/sharks-rays/sharks | Shark lineage >400 Ma; wording keeps lineage/species distinction. | verified |
| 65 | Tardigrades / space | https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Research/Tiny_animals_survive_exposure_to_space | 12-day exposure and survival claim supported with caveat. | verified |
| 66 | TARDIS 2026 dataset | https://esdcdoi.esac.esa.int/doi/html/data/hre/hreda/ea4ded24-c367-4245-96dd-e1eedb98cf81.html | 2026 archive/dataset claim supported. | verified |
| 67 | Eiffel thermal expansion | https://engineering.purdue.edu/MSE/about-us/gotmaterials/Buildings/patel.html | ~15 cm hottest-to-coldest dimension change; old «15 cm is simply false» post removed. | verified |
| 68 | Eiffel asymmetric heating | https://www.toureiffel.paris/en/news/history-and-culture/why-does-eiffel-tower-change-size | Top movement and asymmetric solar heating kept as separate effect. | verified |
| 69 | Banana berry | https://www.kew.org/plants/cavendish-banana | Kew explicitly classifies banana fruit botanically as berry. | verified |
| 70 | Dolphin social memory | https://pmc.ncbi.nlm.nih.gov/articles/PMC3757989/ | Original Proceedings B paper supports recognition after at least 20 years. | verified |

## Решения этой волны

1. Canonical editorial JSON исправляется напрямую и проходит review/CI; workflow больше не редактирует контент сам.
2. `Svodka quality` имеет только `contents: read`, не получает Telegram secret и не делает provider mutations.
3. Все 14 payload рендерятся детерминированно до release.
4. `sendPoll` проверяет returned anonymity, multiple-answer semantics, description, correct answer ids и quiz explanation.
5. Ledger создаётся отдельным manual-only workflow только для точного authorized release digest.
6. Canary — отдельный manual-only workflow; он требует exact release + exact publication + exact confirmation, fresh preflight и durable intent на `state/svodka-telegram` до `send-once`.
7. Schedule не включается до verified manual canary. Это намеренная production граница, а не недоделка.
