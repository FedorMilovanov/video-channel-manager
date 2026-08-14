<!-- PR body source for the provider-inert Milovi onboarding change. -->

Refs #353

## Scope

Provider-inert Milovi Cake Telegram growth/onboarding only. No live Telegram/Dzen/VK mutation is authorized or performed by this change.

## Included

- write-disabled `@MiloviCake` identity profile;
- Milovi-only manual read-only target-discovery workflow;
- 30-post source-mapped launch corpus, including 10 discovery/forwardable concepts;
- corrected verified customer-review quotations from the current Milovi review source;
- explicit ban on unsourced first-person Victoria voice;
- 40+ source research ledger;
- invite/QR attribution, VK/site bridge, Dzen stop/go and local placement playbook;
- text-only first-canary preparation plan;
- regression tests and PR review/scope-lock checklists.

## Important audit finding fixed before PR

The first draft contained five plausible but unsupported customer names/quotes. They were removed and replaced with exact currently published Milovi reviews, and regression tests now block those rejected placeholders from returning.

## Target safety

No numeric `chat_id` is guessed. The provisional profile remains `provider_writes_authorized=false`. After merge, target discovery must run read-only from current `main`, prove the shared bot and exact numeric channel, and produce a binding candidate for separate human review/commit.

## Explicitly not included

- no live post;
- no target binding;
- no release/scheduler queue;
- no invite-link creation;
- no admin-right change;
- no Dzen sync mutation;
- no VK mutation;
- no ad purchase.

## Review gates

- required CI/checks green;
- source/provenance review clean;
- workflow remains Milovi-only and provider-read-only;
- `provider_writes_authorized=false` unchanged;
- no cross-project target leakage;
- no provider mutation during PR review.
