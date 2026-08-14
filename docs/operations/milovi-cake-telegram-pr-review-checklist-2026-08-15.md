# Milovi Cake Telegram onboarding — PR review checklist

Date: 2026-08-15
Owning issue: #353

This checklist is provider-inert. It does not authorize any live Telegram operation.

## Scope review

- [ ] Diff contains only Milovi onboarding/editorial/research/test artifacts.
- [ ] `content/telegram/channels/milovi-cake.json` remains `provider_writes_authorized=false`.
- [ ] No numeric Milovi `chat_id` is guessed or hard-coded before provider proof.
- [ ] No target-binding file is committed before read-only discovery proof.
- [ ] No release/scheduler queue consumes the editorial launch pack.
- [ ] No unrelated Lordchrist/Svodka workflow choice is introduced.

## Content provenance review

- [ ] All review quotes match current `Milovi_Cake/otzyvy/index.html` exactly.
- [ ] Victoria first-person voice is absent unless separately approved/sourced.
- [ ] Price/address/delivery drafts carry pre-publish recheck gates.
- [ ] Gallery posts point to verified Milovi media items.
- [ ] School-derived claims retain contested-attribution caveats where applicable.

## Target-discovery review

- [ ] Workflow is Milovi-only and manually dispatched.
- [ ] Workflow repository permission is `contents: read`.
- [ ] Discovery calls only the read-only Telegram path.
- [ ] Expected bot identity is pinned to id `8716602202` / `preaching_mp3_bot`.
- [ ] Proof must round-trip username → numeric id → same username/type.
- [ ] Bot must be channel admin with `can_post_messages`.
- [ ] Binding candidate is uploaded only as a review artifact; it is not auto-committed.

## Canary review

- [ ] First canary remains one text-only message.
- [ ] No media, pin, poll, edit, schedule, Dzen sync, invite creation or admin mutation is bundled with it.
- [ ] Exact rendered provider payload digest must be recorded before authorization.
- [ ] #353 must explicitly authorize that one payload.
- [ ] Ambiguous provider outcome blocks retry.

## Merge gate

- [ ] Required CI/checks are green.
- [ ] Review comments are resolved.
- [ ] No provider mutation has occurred while reviewing this PR.
