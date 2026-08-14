# Milovi Cake Telegram onboarding — scope lock

Date: 2026-08-15
Owning issue: #353

This branch is now scope-locked for PR review. Do not add new growth features to this PR unless needed to fix CI, factual provenance, or a review finding.

Allowed fixes before merge:
- CI/test failures;
- incorrect Milovi facts/sources;
- Telegram target-discovery safety defects;
- cross-project leakage;
- documentation contradictions.

Out of scope for this PR:
- live publication;
- numeric target binding derived without provider proof;
- scheduler/release queue;
- invite-link creation;
- Dzen/VK provider mutations;
- paid promotion;
- site UI changes;
- new customer bot.
