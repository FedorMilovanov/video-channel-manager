# Lordchrist — post-proof аудит репозитория — 2026-08-08

Статус: **технический аудит после первого подтверждённого автономного scheduled-поста**.

Базовый SHA аудита: `57080b097809af4227fc80db02f152918a07d50d`.

Первый scheduled-proof уже сохранён отдельно в `docs/lordchrist/proofs/2026-08-08-first-scheduled-proof.md`: Telegram подтвердил `lordchrist-bunyan-fire-grace` как `published / verified`, `message_id=1472`, run `31245659459/1`.

## Краткий вывод

Репозиторий за последние часы существенно вырос и теперь содержит два поколения Telegram-инфраструктуры:

1. проверенный в production специализированный Lordchrist quote publisher;
2. более новый generic multichannel runtime, разработанный на Svodka и уже содержащий более сильные release/state/provider-инварианты.

Поэтому правильное дальнейшее направление — **не писать третий publisher для research-post v2**, а оставить evidence/fact-check слой research-v2 отдельным и передавать одобренные материалы в generic multichannel release/state/transport слой.

Живой quote publisher не следует переписывать одновременно с этой миграцией: он уже доказал работу в production и должен получать только небольшие, отдельно проверяемые hardening-изменения.

## Что уже хорошо защищено

- Telegram mutation transport retries зафиксированы как `0`; read-only preflight может повторять безопасные запросы.
- provider intent сохраняется до `sendMessage`; неоднозначный provider outcome не допускает blind retry.
- текущая quote-очередь и presentation policy привязаны digest-ами.
- GitHub Actions в критических workflow уже используют full-length SHA для `actions/checkout` и `actions/setup-python`.
- CI проверяет Python 3.11/3.12/3.13, Ruff, Ruff format, mypy, pytest, dependency audit, compileall и отдельный minimal Telegram runtime smoke.
- Dependabot уже следит за `pip` и `github-actions` еженедельно.
- generic multichannel runtime умеет фиксировать точный provider payload, HTML entities/source links, target binding, reviewed release provenance и deterministic publication windows.
- Svodka-контур уже показывает полезный шаблон exact-SHA quality re-proof, stale-window recovery только без provider effect и verified-manual-canary gate.

## Найденные / оставшиеся риски

### P1 — старый research PR нельзя мерджить как есть

PR #169 был создан до большого массива изменений `main` и сильно разошёлся с текущей базой. Его содержимое нужно перенести на свежую ветку от current main. Сам PR использовать как provenance/editorial archive, но не как merge vehicle.

### P1 — Lordchrist research-v2 не должен дублировать durable state machine

Первоначальный research-v2 валидатор полезен как evidence contract (`claim -> source -> certainty -> measurement_scope`), но provider-доставка должна использовать generic multichannel runtime. Иначе появятся две реализации intent/send/outcome/reconciliation с разными дефектами.

### P1 — legacy Lordchrist concurrency всё ещё `queue: single`

GitHub теперь документирует `queue: max`: до 100 pending runs могут ожидать в одном concurrency group. При `single` новый pending заменяет предыдущий. Для production publisher после успешного proof предпочтительно перейти на `queue: max`, сохранив `cancel-in-progress: false` и ledger quota как главный semantic guard.

Изменение должно быть отдельным маленьким PR и regression-tested, а не смешиваться с research migration.

### P1 — branch/ruleset enforcement не подтверждён

В доступном GitHub connector нет чтения rulesets/branch protection, поэтому нельзя утверждать, что `main` и `state/lordchrist-telegram` сейчас защищены от force-push/delete.

Нужны разные политики:

- `main`: block force push/delete; PR + required green checks для критических изменений;
- `state/lordchrist-telegram`: block force push/delete, но сохранить normal fast-forward writes publisher-а.

### P2 — нет CODEOWNERS

Добавляется в этом hardening PR как ownership map. На персональном репозитории это прежде всего документация и automatic review routing; реальная обязательность зависит от ruleset/branch protection и не должна считаться включённой без проверки GitHub Settings.

### P2 — dependency review отсутствует

Текущий `pip-audit` хорошо ловит известные уязвимости установленного графа, но отдельный Dependency Review полезен именно на PR-diff: он блокирует внесение новой уязвимой зависимости до merge. В этом PR добавляется официальный `actions/dependency-review-action` v5 по full SHA, с `contents: read` и `fail-on-severity: moderate`.

### P2 — runtime exact-pinned, но не hash-verified

`requirements/telegram-publisher.txt` использует `==` и production install уже запрещает source distributions через `--only-binary=:all:`, но локальных wheel hashes пока нет.

Следующий supply-chain шаг: отдельный generated hash lock + `--require-hashes`. Не следует добавлять неполный/ручной набор hashes: pip hash-checking mode является all-or-nothing и требует hashes для всех транзитивных зависимостей.

### P2 — `ubuntu-latest` остаётся в ряде production/CI workflow

Первый Lordchrist scheduled proof фактически прошёл на Ubuntu 24.04, но явный `ubuntu-24.04` уменьшит будущий runtime drift. Менять это нужно отдельным небольшим PR после CI-проверки, не вместе с research content.

### P2 — job-level `contents: write` шире фактического окна записи

Legacy publisher получает write-capable `GITHUB_TOKEN` на весь job, хотя запись нужна только state-операциям. GitHub рекомендует minimum permissions. Сужение требует аккуратного разделения job/credentials так, чтобы не разрушить durable intent-before-send; это полезно, но не должно делаться косметически.

### P2 — нет independently verified generic target binding для Lordchrist

`content/telegram/channels/lordchrist.json` уже существует, но `content/telegram/channels/lordchrist-target-binding.json` отсутствует. Перед generic research canary нужно получить свежий read-only `getMe + getChat + getChatAdministrators` proof и зафиксировать exact binding без provider write.

### P3 — CodeQL / artifact attestations не являются текущим blocking item

Для публичного репозитория GitHub предоставляет code scanning и artifact provenance возможности. Они полезны как дальнейшее repo-wide усиление, но не решают специфические Telegram exactly-once / state / evidence риски. Их не следует ставить впереди research migration, target binding, release provenance, dependency hashes и branch rules.

## Архитектура research-post v2 после аудита

Рекомендуемые слои:

`research source registry`
→ `claim/evidence/certainty validator`
→ `canonical Russian post body`
→ `content/source hashes`
→ `generic Telegram message payload`
→ `reviewed immutable release candidate`
→ `exact target binding`
→ `generic durable ledger`
→ `manual canary inside immutable publication window`
→ `verified Telegram receipt`
→ `scheduled strict-next dispatch`
→ `durable outcome / may_exist stop`.

Research evidence semantics остаются отдельными от quote semantics. Provider transport/state semantics, наоборот, должны быть общими.

## Пять research-постов

Сохраняется уже проверенная серия:

1. `T+0` — 📖 «Не рекорд, а мера труда»;
2. `T+2` — 🖋️ «Перо, стенографист и магнитная лента»;
3. `T+4` — 🕯️ «Учиться у тех, кто жил до нас»;
4. `T+6` — 📚 «Один текст — три манеры проповедовать»;
5. `T+8` — ⏳ «Невидимая дисциплина».

До canary это relative editorial schedule. Generic release получает абсолютные timezone-aware `scheduled_at` только после выбора реального окна запуска. Первый элемент публикуется ровно один раз как canary; остальные четыре после verified receipt могут обслуживаться scheduler-ом.

## Что делаем сейчас

1. Переносим research-v2 с PR #169 на свежую ветку от audited `main`.
2. Не переносим research-specific provider mutation code — используем generic multichannel runtime.
3. Создаём provider-free Lordchrist generic preflight/binding path.
4. Создаём immutable research release candidate и preview.
5. Только после review — отдельный exact canary.
6. После verified canary — scheduled strict-next для оставшихся четырёх.
7. Отдельно минимально harden-им legacy quote workflow (`queue:max`, explicit runner и далее credential scope), не смешивая это с research migration.
8. Включаем dependency review и фиксируем CODEOWNERS.
9. Генерируем hash-verified Telegram runtime отдельной supply-chain волной.
10. Проверяем GitHub Settings вручную/API когда доступно: rulesets, required checks, SHA-pinning policy, secret scanning/push protection.

## Технический verification pass — 30+ primary/official pages

Ниже — первичные технические страницы, использованные для решений этого аудита. Они не заменяют тесты репозитория; их задача — проверить семантику внешних платформ и не строить защиту на устаревших предположениях.

### GitHub Actions / deployment / concurrency

1. https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
2. https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency
3. https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run
4. https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
5. https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments
6. https://docs.github.com/en/actions/reference/security/secure-use
7. https://docs.github.com/en/actions/concepts/security/github_token
8. https://docs.github.com/en/rest/actions/permissions
9. https://docs.github.com/en/rest/actions/concurrency-groups
10. https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository

### GitHub repository protection / supply chain

11. https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
12. https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
13. https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
14. https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
15. https://docs.github.com/en/code-security/getting-started/github-security-features
16. https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository
17. https://docs.github.com/en/code-security/concepts/secret-security/about-alerts
18. https://docs.github.com/en/code-security/concepts/secret-security/push-protection
19. https://docs.github.com/en/code-security/how-tos/secure-your-secrets/work-with-leak-prevention/push-protection-on-the-command-line
20. https://docs.github.com/en/code-security/how-tos/secure-your-secrets/work-with-leak-prevention/push-protection-in-the-github-ui
21. https://docs.github.com/en/code-security/reference/secret-security/secret-scanning-scope
22. https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-on-actions
23. https://github.com/actions/dependency-review-action
24. https://github.com/actions/dependency-review-action/releases
25. https://github.com/actions/dependency-review-action/blob/main/docs/examples.md
26. https://github.com/marketplace/actions/dependency-review

### pip / Python supply chain

27. https://pip.pypa.io/en/stable/topics/secure-installs/
28. https://pip.pypa.io/en/stable/topics/repeatable-installs/
29. https://pip.pypa.io/en/stable/reference/requirements-file-format/
30. https://pip.pypa.io/en/stable/cli/pip_hash/

### Telegram provider contract

31. https://core.telegram.org/bots/api
32. https://core.telegram.org/bots/api-changelog
33. https://core.telegram.org/bots/faq

## Не делать

- не считать `sendMessage` exactly-once API: provider idempotency key отсутствует;
- не retry-ить mutating transport при read/write ambiguity;
- не смешивать 3 563 опубликованных проповеди Сперджена и historical estimate Кальвина в одинаковый metric;
- не разрешать research renderer/publisher обходить evidence validator;
- не сливать stale PR #169 поверх current main;
- не включать generic Lordchrist writes до exact target binding + reviewed release + independent canary;
- не добавлять неполные hashes только ради галочки;
- не считать CODEOWNERS/rulesets реально enforced, пока GitHub Settings это не подтверждают.
