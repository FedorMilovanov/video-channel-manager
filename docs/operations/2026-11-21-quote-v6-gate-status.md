# @lordchrist quote-v6 — состояние fail-closed preflight (закрытие #1044)

Дата: 21.11.2026. Основание: issue #1044, стандарт
`content/telegram/lordchrist/SEMANTIC_CLARITY_AND_CONTEXT_STANDARD.md`, документ
`docs/operations/lordchrist-quote-v6-semantic-gate.md`.

## 1. Что уже исполняется в `main`

| Требование #1044 | Где | Состояние |
| --- | --- | --- |
| Per-ID review-реестр (тезис, связка, риск прочтения, contiguous span, SHA, оригинал, права, ревьюер, вердикт) | `content/telegram/lordchrist/quote-v6-semantic-review-v1.json` | 30 записей, все `REVIEW_REQUIRED` |
| Отдельный activation-реестр подписей (PR + head SHA + review ID + логин) | `content/telegram/lordchrist/quote-v6-semantic-activation-v1.json` | `entries: []` — ни одной публикации не разрешено |
| Гейт до записи intent и повторно до `sendMessage` | `scripts/lordchrist_quote_v6_semantic_gate.py`, вызовы в `scripts/lordchrist_quote_v6_publisher.py` | живой, GET-only к GitHub API, при недоступности API — `SemanticApprovalHold` |
| Проверка против актуального `main` + pinned digest + protected `state/lordchrist-telegram` | тот же модуль | живой |
| Запрет старых `initialize` / `migrate` / `migrate-editorial` | workflow: `if [[ "$V6_ACTION" != "publish" ]]; then … exit 2`; CLI: `ValueError` до любых записей | недостижимы из workflow и CLI, закреплено тестами |
| Provider-free интеграционные тесты | `tests/test_lordchrist_quote_v6_semantic_gate.py`, `tests/test_lordchrist_quote_v6_live_publisher.py` | зелёные |
| Никаких новых `POST` в ходе работ | прогоны не выполнялись | подтверждается ledger: 12 published / 18 pending без изменений |

Дополнительно в этой волне добавлены два теста, которые раньше отсутствовали:

- `test_retired_mutations_are_guarded_before_their_own_branches` — проверяет, что
  fail-closed guard в workflow стоит **перед** ветками `initialize` / `migrate-restyle` /
  `migrate-editorial-v2`, то есть миграции эпохи 11/19 недостижимы, а не «не рекомендованы»;
- `test_cli_refuses_retired_mutations_without_touching_state` — CLI отказывает в
  `init` / `migrate` / `migrate-editorial` и не вызывает `save_ledger`.

## 2. Что это означает практически

- Пока в activation-реестре ноль записей, **ни одна** из 18 ожидающих карточек не может уйти:
  отправитель обязан завершиться `SemanticApprovalHold` до записи intent.
- Четыре pending с `HOLD_MEANING` (№16 Райл об освящении, №18 Райл о воине, №22 Уотсон о
  довольстве, №27 Баньян/Беула) ждут именно редакционного решения, а не кода.
- Опубликованные 12 карточек (включая Бакстер #1618 и Эдвардс #1629) не переписываются:
  история, ledger и message ID неприкосновенны.

## 3. Как одна карточка становится публикуемой (без изменений в коде)

1. Независимый редактор сверяет оригинал, русский текст, грамматику, права на перевод.
2. PR A заполняет в review-реестре для **точного** ID все поля и `semantic_verdict=PASS_MEANING`;
   SHA финального payload должен совпасть с очередью.
3. Реальный `APPROVED` review от другого аккаунта на точный `head.sha` PR A, merge в `main`.
4. PR B добавляет в activation-реестр `publication_id`, `review_pr_number`,
   `approved_pr_head_sha`, `reviewer_login`, `github_approval_review_id`.
5. Только после этого штатный sender сможет подготовить intent; публикация — в обычном
   московском окне, без «догоняющих» выпусков.

## 4. Что остаётся вне кода

- Независимая редакционная приёмка 18 ожидающих карточек — работа редактора, не агента.
- Разрешение на rollout (пункт 7 issue) — отдельное решение владельца; до него гейт
  остаётся включённым и блокирующим, что и является целевым поведением.

Вывод: кодовые требования #1044 выполнены и закреплены тестами; публикационный эффект
намеренно нулевой. Дальнейшие шаги — редакционные, они вынесены в
`docs/operations/2026-11-21-zero-open-tasks-plan.md`.
