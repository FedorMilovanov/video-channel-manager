# Telegram control audit — 2026-08-09

Audited runtime baseline before this documentation-only continuation: `main@0776418450070a707370970977192dd59698b25e`.

This record closes the internal code/runtime findings that remained after the 2026-08-08 Lordchrist/Svodka hardening marathon and the first full control-audit continuation. It does not authorize a provider operation and performs no Telegram read or write.

## Current provider/state separation

### Lordchrist legacy quote publisher

The legacy `@lordchrist` quote publisher is a real production surface with durable verified history on `state/lordchrist-telegram`:

- manual verified message `1470`;
- scheduled verified message `1472`;
- later strict queue entries remain pending at this control point;
- no unresolved `may_exist` dispatch was found in the reviewed ledger state.

The publisher and its provider-outcome recovery use the same `lordchrist-telegram-publisher` concurrency group, `cancel-in-progress: false`, `queue: max`, and `ubuntu-24.04`.

### Lordchrist generic research-v2

Research-v2 remains a separate content/release track on the shared generic Telegram runtime, not a third sender/state machine.

- current generic profile: `provider_writes_authorized=false`;
- current exact five-item target-bound candidate: `sha256:2eb3825390b8f4e70b847d9d1b328ea4e203bce0f1c88e036ea97ae667809cd0`;
- validation remains read-only/provider-inert;
- research activation/canary is not performed by this audit.

### Svodka

`@deep_info_life` remains intentionally unarmed:

- profile write gate: `false`;
- approved release: absent at this control point;
- publication ledger: absent at this control point;
- canonical 14-post queue remained unchanged through the later runtime hardening;
- no Svodka provider mutation is performed by this audit.

## Closed findings in this continuation

### Manual reconciliation publication time

Before `3f1a1744c22364571912a89c19ecd5f85a83a844`, manual `confirmed_published` reconciliation could use the operator resolution time as `published_at_utc`. A provider message published on one Moscow date but proven on the next could therefore consume the wrong daily publication quota.

The production CLI now requires an exact timezone-aware `--published-at-utc` for `confirmed_published`. The state transition keeps publication time distinct from `resolved_at_utc`, requires it to be no earlier than the durable dispatch attempt and no later than reconciliation, and regressions prove previous-day evidence does not consume the next Moscow-day quota.

PR #207 exact head `ef63fd0d7707605be070d5f720cc0729d390092a` passed full CI #3760 before squash merge `3f1a1744c22364571912a89c19ecd5f85a83a844`.

### Complete Lordchrist writer inventory

Before `aea3aa343d5bb42297c4ee25665ecf1058690a23`, the Lordchrist concurrency regression inspected only the main publisher workflow even though provider-outcome recovery was also a writer in the same concurrency group.

The regression now discovers every `.github/workflows/*.yml` containing `group: lordchrist-telegram-publisher`, requires the exact current writer set, and applies the lossless serialization/runner contract to every discovered writer.

PR #208 exact head `b74f01d6f8b711bf5630057c78d715e1195b5aaa` passed full CI #3763 before squash merge `aea3aa343d5bb42297c4ee25665ecf1058690a23`.

### Hash-lock workflow integration

The complete Telegram dependency hash lock introduced by `a3e978d13b9c9ebf46f2348bce5626515259cf43` was correct, but the specialized Lordchrist research-v2 workflow still placed `-r requirements/telegram-publisher.txt` and the test-only requirement `pytest>=8.3,<10` in one pip transaction.

Because the requirements file enables `--require-hashes`, pip correctly applies hash-checking to the whole transaction. The first specialized validation after the memory-sync branch therefore failed before tests instead of silently weakening the lock.

PR #210 fixes the integration without changing the production lock: the exact hash-checked Telegram runtime is installed in its own binary-only transaction, the provider-inert pytest harness is installed separately, and a generic regression now inspects every workflow `pip install` that consumes the lock and forbids adding another package after it.

PR #210 exact head `ec23fc88c44621e1d8fa22fb834b4d978d7a4234` passed full CI #3769 and specialized Lordchrist research-v2 validation #67 before squash merge `0776418450070a707370970977192dd59698b25e`.

### Previously closed but stale in the old defect register

The immutable 2026-08-08 defect register intentionally remains unchanged. Its successor records that:

- `LCT-CONCURRENCY-004` was fixed by `f98bc118229f54dec3d83e8160adc37c1695ee7c`;
- `RESEARCH-STATE-006` was resolved into the shared generic runtime by `a91e613afdc61211b35e5153fa89c009c8427280`;
- `SUPPLY-HASHES-008` was fixed by `a3e978d13b9c9ebf46f2348bce5626515259cf43`;
- Lordchrist exact outcome durability/recovery was hardened by `a213bb0a6bf3ada94d2b7e08c66ee18c95bfc12a`.

## Supply-chain state

`requirements/telegram-publisher.txt` uses pip `--require-hashes` for the exact supported minimal Telegram dependency closure. Production/minimal workflow installs keep that lock in a separate binary-only pip transaction. General CI builds an isolated Python 3.11 environment from this file, runs provider-free CLI smoke checks, `pip check`, vulnerability audit, Ruff, formatting, mypy and the full test suite.

This closes both the repository-level hash-lock finding and the discovered workflow-integration error. It does not prove external GitHub repository settings.

## External governance boundary

`.github/CODEOWNERS` exists for critical automation, Telegram runtime/content and audit paths. That file does **not** prove that review, branch protection or rulesets are enforced.

Effective GitHub ruleset/branch-protection state and current Dependency Graph setting are external host configuration. The connector available during this audit does not expose those effective settings, so they remain explicitly **UNVERIFIED**, not silently treated as green.

Before a new high-risk activation, independently verify at minimum:

- `main` force-push/deletion policy;
- state-branch force-push/deletion policy compatible with the intended fast-forward writer;
- whether CODEOWNERS review is actually required by a rule;
- Dependency Graph state before reintroducing Dependency Review as a required control.

## Control-audit result

No additional internal Telegram provider/state bypass was found after the timestamp, complete writer-surface and hash-lock integration fixes. Known repository-controlled Telegram P1/P2 findings from the handoff are closed or reduced to provider-inert documentation/state synchronization.

The remaining non-green Telegram items are external governance verification and intentionally unopened provider activations. Neither is converted into an inferred success by this audit.
