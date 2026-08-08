# Lordchrist — post-proof аудит репозитория — 2026-08-08

Статус: **технический аудит после первого подтверждённого автономного scheduled-поста**.

Исходный SHA аудита: `57080b097809af4227fc80db02f152918a07d50d`. Во время проверки `main` продолжал активно двигаться, поэтому все изменения разделены на независимые PR и должны приниматься только по exact-head CI.

Первый scheduled-proof сохранён в `docs/lordchrist/proofs/2026-08-08-first-scheduled-proof.md`: `lordchrist-bunyan-fire-grace`, Telegram `message_id=1472`, run `31245659459/1`, итог `published / verified`.

## Главный архитектурный вывод

В репозитории теперь два поколения Telegram-инфраструктуры:

1. специализированный Lordchrist quote publisher, уже доказавший работу в production;
2. более новый generic multichannel runtime, созданный для Svodka и содержащий более сильные release/state/provider-инварианты.

Research-post v2 не должен создавать третью реализацию отправки. Его evidence/fact-check слой остаётся отдельным, а provider delivery, durable intent, outcome и reconciliation должны использовать generic multichannel runtime.

Живой quote publisher при этом не переписывается вместе с research-миграцией: его hardening делается маленькими самостоятельными изменениями.

## Что уже хорошо защищено

- mutation transport retries для Telegram равны `0`; read-only preflight может повторять безопасные запросы;
- provider intent сохраняется до `sendMessage`; неоднозначный provider outcome блокирует blind retry;
- quote-очередь и presentation policy привязаны digest-ами;
- критические Actions используют full commit SHA;
- основной CI проверяет Python 3.11/3.12/3.13, Ruff, Ruff format, mypy, pytest, dependency audit, compileall и minimal Telegram runtime;
- Dependabot уже следит за `pip` и `github-actions`;
- generic multichannel runtime фиксирует provider payload, target binding, reviewed release provenance, publication windows и Telegram receipt semantics;
- Svodka уже даёт рабочие шаблоны exact-SHA quality proof, verified manual canary и recovery только при доказанном отсутствии provider effect.

## Существенные находки

### P0/P1 — во время аудита текущий `main` оказался красным

Общий CI на merge-base показал `1032 passed, 1 xfailed, 3 failed`; Ruff correctness, mypy и pip-audit были чистыми, но Ruff format видел три файла.

Причина — не Lordchrist hardening, а несинхронизированные regression fixtures после параллельного развития generic Telegram/Svodka runtime:

- HTTP-client ownership inventory не учитывал новые generic discovery/transport clients;
- Svodka release test ожидал poll schema v3 при текущей v4;
- offline Telegram poll mock не возвращал новые поля, которые текущий transport уже строго проверяет;
- три файла имели format drift.

Исправление вынесено в отдельный минимальный repair PR. Это важный урок: новые safety-проверки нельзя оценивать поверх уже красной базы.

### P1 — stale research PR #169 нельзя мерджить как есть

Он был создан до большого массива изменений `main`. Его evidence/content переносится на свежую current-main ветку; старый PR остаётся provenance, но не merge vehicle.

### P1 — research-v2 не должен дублировать durable state machine

`claim -> source -> certainty -> measurement_scope` — полезный отдельный контракт. Но Telegram intent/send/outcome/reconciliation должен быть общим generic слоем, иначе две state machine неизбежно начнут расходиться.

### P1 — legacy Lordchrist concurrency всё ещё `queue: single`

GitHub документирует `queue: max`: в одной concurrency group может ожидать до 100 pending runs; при `single` новый pending заменяет предыдущий. После успешного production proof предпочтителен отдельный tiny PR `single -> max`, при сохранении `cancel-in-progress: false` и ledger quota как semantic guard.

### P1 — branch/ruleset enforcement не подтверждён

Доступный connector не читает repository rulesets/branch protection. Нельзя утверждать, что force-push/delete уже запрещены.

Нужны разные политики:

- `main`: block force-push/delete, reviewed green PR для критических путей;
- `state/lordchrist-telegram`: block force-push/delete, но разрешить обычные fast-forward writes publisher-а.

### P2 — CODEOWNERS отсутствовал

В этом hardening PR добавлена карта владения критическими workflow, Telegram runtime/content и audit paths. Сама по себе CODEOWNERS не доказывает обязательный review — enforcement зависит от ruleset/branch protection.

### P2 — Dependency Review полезен, но сейчас технически недоступен

Официальный `actions/dependency-review-action` был реально испытан в этом PR. Workflow завершился ошибкой: GitHub сообщил, что Dependency Review не поддерживается, пока в репозитории отключён Dependency Graph.

Поэтому красный workflow удалён вместо оставления фиктивного gate. Текущий `pip-audit` продолжает работать. Dependency Review следует включить только после включения Dependency Graph в GitHub Settings, затем вернуть официальный full-SHA pinned action отдельным PR.

### P2 — runtime exact-pinned, но ещё не hash-verified

`requirements/telegram-publisher.txt` использует `==`, а production install — `--only-binary=:all:`. Следующий supply-chain шаг — generated hash lock + `--require-hashes`. Неполный ручной набор hashes запрещён: pip hash-checking mode требует полного набора для всего разрешаемого dependency graph.

### P2 — `ubuntu-latest` остаётся в legacy Lordchrist workflow

Первый proof фактически работал на Ubuntu 24.04. Явный `ubuntu-24.04` уменьшит runtime drift, но это отдельный tiny PR после восстановления зелёного main.

### P2 — job-level `contents: write` шире окна реальной записи

Legacy publisher имеет write-capable token на весь job. Сужение желательно, но только после проектирования job boundary, которое не разрушит intent-before-send. Это не косметическая правка.

### P2 — generic Lordchrist target binding ещё не закреплён

Профиль `content/telegram/channels/lordchrist.json` существует, binding-файл отсутствует. Research migration добавляет read-only discovery → immutable binding candidate без provider write. Только после exact binding можно строить live generic research release.

### P3 — CodeQL / artifact attestations не blocking item

Они полезны репозиторию в целом, но сейчас не решают наиболее важные Telegram-риски: target identity, state monotonicity, provider ambiguity, release provenance и evidence integrity. Их не ставим впереди этих задач.

## Research-post v2 после аудита

Целевая цепочка:

`source registry`
→ `claim/evidence/certainty validator`
→ `canonical Russian text`
→ `content/source hashes`
→ `generic Telegram payload`
→ `reviewed immutable release`
→ `exact target binding`
→ `generic durable ledger`
→ `one manual canary`
→ `verified Telegram receipt`
→ `scheduled strict-next`
→ `durable outcome / may_exist stop`.

Пять материалов сохраняют editorial offsets:

1. `T+0` — 📖 «Не рекорд, а мера труда»;
2. `T+2` — 🖋️ «Перо, стенографист и магнитная лента»;
3. `T+4` — 🕯️ «Учиться у тех, кто жил до нас»;
4. `T+6` — 📚 «Один текст — три манеры проповедовать»;
5. `T+8` — ⏳ «Невидимая дисциплина».

Абсолютные `scheduled_at` появляются только при создании конкретного generic release.

## Порядок работ

1. Восстановить зелёный current `main` отдельным repair PR.
2. Перенести research-v2 с #169 на свежую базу и оставить evidence validator provider-inert.
3. Добавить adapter research → generic release, а не новый sender.
4. Получить provider-free Lordchrist target proof/binding.
5. Создать и review-нуть immutable research release candidate.
6. Сделать ровно один exact canary.
7. После `verified` запустить generic scheduler для оставшихся четырёх.
8. Отдельно harden legacy quote workflow (`queue:max`, explicit runner, затем credential scope).
9. После включения GitHub Dependency Graph вернуть Dependency Review.
10. Отдельно сгенерировать complete hash-verified Telegram runtime.
11. Проверить в GitHub Settings rulesets, required checks, SHA-pinning policy, secret scanning/push protection.

## Технический verification pass — 33 primary/official pages

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

- не считать Telegram mutation exactly-once API;
- не retry-ить provider mutation при сетевой неоднозначности;
- не смешивать разные исторические denominators в research-цифрах;
- не разрешать research release обходить evidence validator;
- не сливать stale #169;
- не включать generic Lordchrist writes до exact binding + reviewed release + canary;
- не добавлять неполные dependency hashes;
- не считать CODEOWNERS/rulesets enforced без проверки Settings;
- не оставлять permanently-red security workflow, если его platform prerequisite отключён.
