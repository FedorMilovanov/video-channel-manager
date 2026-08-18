# Milovi Cake one-off Telegram canary — 2026-08-18

Owning issue: #353

This is a new exact operation, not a replay or catch-up of the missed `milovi-bootstrap-003` slot.

- Project: `milovi-cake`
- Target: `@MiloviCake` / chat `-1002215328390`
- Bot: `8716602202` / `@preaching_mp3_bot`
- New publication: `milovi-canary-20260818-001`
- Authorized release digest: `sha256:04fd7792c9a2bb698259935ac81c5b04071f73883b3a9270eb324d3355b0ebfe`
- Provider payload digest: `sha256:60ba1bdd1e9a05d6bb7620951a5861140c253477c533be25d3aabe362c96cdef`
- Media: `p11.jpg`, `sha256:8bb0956e44084265d7a3a14ce01f96eb1e4a9c327c780448de34e068f6cf6f10`, 412206 bytes
- Fresh slot: `2026-08-18T16:10:00+03:00`
- Freshness deadline: `2026-08-18T18:10:00+03:00`
- Controller may dispatch only on `2026-08-18` between `16:10` and `17:05` Moscow and only after exact-current-main CI, one-off quality, and media proof are green.
- Provider workflow remains `workflow_dispatch` only and requires exact confirmation `PUBLISH:@MiloviCake:milovi-canary-20260818-001`.
- Durable one-off ledger lives on `state/milovi-cake-telegram` under `content/telegram/milovi-cake/oneoff-canary-2026-08-18/`.
- The old `milovi-bootstrap-003` is superseded only if it still has no prior intent/provider effect; it must be marked `skipped/provider_effect=impossible` before the one-off provider run.
- Exactly one provider attempt is authorized. Blind retries are zero. Any `may_exist`/unknown outcome blocks replay.

Expected postcondition: one verified Telegram photo message in `@MiloviCake` with exact target/payload/media identity and a durable provider receipt; otherwise the operation remains explicitly unresolved and non-replayable.
