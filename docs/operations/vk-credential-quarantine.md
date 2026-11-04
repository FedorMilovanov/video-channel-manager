# VK legacy credential quarantine (issue #662)

Status: **active, provider-inert**. This document records a policy decision about one specific
credential. It is not an inference from an API error code, and it does not relax anything in
[`wall-safety-contract.md`](wall-safety-contract.md).

## What is quarantined

The shared VK credential stored under the local alias `legendary-poet` (the same underlying token as
`default`) is **quarantined**: it must not be used for any provider call, read or write, until the
resume condition below is met.

Recorded evidence, from the issue-#662 investigation (2026-09-12 … 2026-09-17):

| Fact | Value |
| --- | --- |
| Credential alias | `legendary-poet` (same token as `default`) |
| Community in scope | `60805374` |
| First exact-method code-9 observation | `2026-09-12T22:35:13Z` |
| Probe after extended quiet | `2026-09-13T14:41:22Z` → code 9 |
| Probe after ~6h43m more quiet | `2026-09-13T21:24:33Z` → code 9 |
| Probe after >64h without a newer observation | failed → time-based retry retired |
| Later legacy observation | `2026-09-17T07:41:39Z` |
| Token provenance | browser OAuth redirect issued 2026-04-20 for VK user `631487`, via third-party `client_id=2685278` |
| Owner's own app (not yet consented) | `54555649` |
| Quarantine state | `blocked_on_oauth_consent_legacy_quarantined` |

Provider writes during the entire investigation: **0**. Recovery state stayed `apply_started=false`,
`apply_completed=false`, journal empty.

## Why this is a policy, not a code-9 rule

`wall-safety-contract.md` says code `9` is per credential + method and **must not** be read as a
credential-wide quarantine. That rule is unchanged and still correct: nothing here treats one flood
response as authority to block a credential.

The quarantine is an operator decision about *this token's provenance*: it is a third-party-client
OAuth redirect that has repeatedly produced flood rejection, and it was deliberately retired in favour
of the owner's own app. The reason for the quarantine is the decision, not the error code.

## Forbidden while quarantined

- any `vk` provider call using the quarantined credential, including "one-shot" probes;
- retrying on a fixed quiet-period cadence (6 hours, 24 hours, "long enough") — there is no VK TTL;
- `vk login --force` as a recovery attempt: the validation flow performs provider reads before it
  replaces the stored token;
- alias rotation, token rotation, IP change or an alternate writer to evade flood control;
- restoring or re-running any local launcher that resumes this credential.

Local provider-inert blockers (`.cmd` / `.ps1` launchers and a turnkey script) were created on the
operator's Windows desktop and their digests were recorded in issue #662. They are **not** tracked in
this repository, so nothing here can prove they still exist: treat any local launcher as untrusted
until it is re-verified against that issue record.

## Only supported resume condition

The supported credential is the **community access key of community 60805374**
(created in the community's `Работа с API → Ключи доступа` settings with the
`wall` permission). On 2026-10-24 it was verified read-only
(`groups.getTokenPermissions` shows `wall`; `groups.getById` binds community
`60805374`) with zero provider writes. Resume sequence:

1. Import the community key **separately** from the legacy token; never
   overwrite the quarantined credential in place, so the quarantine boundary
   stays provable.
2. Validate it with the single read gate below (exactly
   `groups.getTokenPermissions` + `groups.getById`).
3. Only then restore the guarded provider path and rebuild the Lord God
   postponed-content wave from a fresh wall audit under policy
   `vk-lord-god-postponed-wall-v4`: the adapter binds alias
   `vk-lord-god-community-key` and rejects the quarantined aliases
   (`legendary-poet`, `default`) before any provider call, so a legacy plan
   can never be replayed under the new credential. The exact end-to-end
   sequence lives in
   [`lord-god-vk-daily-postponed-runbook.md`](lord-god-vk-daily-postponed-runbook.md).

```
vk community-key-login --account vk-lord-god-community-key --community 60805374
vk community-key-capabilities --account vk-lord-god-community-key --community 60805374
```

`tests/test_operator_runbook_commands.py` parses documented `vk` invocations against the
real CLI, so a renamed option fails in CI rather than during an incident.

## Related

- [`current-state.md`](current-state.md) — the VK sections that depend on this quarantine.
- [`wall-safety-contract.md`](wall-safety-contract.md) — code-9 circuit semantics.
- Issue #662 — original investigation and closure evidence.
