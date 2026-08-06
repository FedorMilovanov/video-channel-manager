# VK postponed text edit result states

This state matrix is normative for `video-manager-vk-postponed-text` results. It prevents a confirmed no-effect provider response from being reported as an unknown effect.

| State or status | Provider effect | Meaning | Next allowed action |
|---|---|---|---|
| `already_after` | `verified` | Fresh preflight exactly matches the immutable after-state. | Skip the operation. |
| `verified_before_dispatch` | `verified` | A later pre-dispatch read found the exact after-state. | Skip the operation. |
| `verified` | `verified` | Postflight exactly matches the immutable after-state. | Continue. |
| `verified_after_delayed_reconciliation` | `verified` | Delayed readback proved success after a transient response. | Continue. |
| `confirmed_absent` | `confirmed_absent` | Postflight exactly matches the immutable before-state and no controlled retry remains. | Stop; reconcile before a later resume. |
| `captcha_required_confirmed_absent` | `confirmed_absent` | VK error 14 occurred and postflight still matches exact before-state. | Stop; do not solve or bypass CAPTCHA in the core executor. Wait, reconcile, then resume the same plan. |
| `transient_confirmed_absent_waiting_retry` | `confirmed_absent` | A transient response occurred and exact readback proved no effect. | One configured delayed retry is allowed. |
| `unknown_requires_reconciliation` | `may_exist` | The exact provider effect cannot be proved because readback failed or produced a third state. | Stop without retry; perform read-only reconciliation. |
| `blocked_conflict` | `not_dispatched` | Initial live state matches neither approved before nor approved after. | Review and build a new plan; no write is allowed. |
| `stopped_conflict` | `not_dispatched` | A pre-dispatch live read changed after the run began. | Stop and review. |
| `final_postcondition_failed` | mixed | Not every target is exact-after at final full-surface verification. | Preserve journals and investigate; no blind replay. |
| `non_target_postcondition_failed` | mixed | A published or non-target postponed object changed during the run. | Preserve evidence and investigate; no blind replay. |
| `succeeded` | `verified` | Every target is exact-after, queue count is unchanged, and every non-target wall object is unchanged. | Operation is complete. |

## Aggregation rule

`confirmed_absent` and `unknown_requires_reconciliation` are different states and must never share one `unknown` counter. A result summary may count verified, confirmed-absent, CAPTCHA-stopped, and unknown outcomes separately, but the per-operation journal remains authoritative.

## Resume rule

A later invocation of the same exact plan is permitted only after fresh reconciliation reports zero conflicts. It skips exact-after posts and dispatches only exact-before posts. A target in any third state blocks the entire resume before another provider mutation.
