# Milovi Telegram marathon wave

Updated: 2026-08-20  
Owning issue: #353  
Provider target: `@MiloviCake`

This document makes the already-merged Cake + School follow-on work operationally discoverable without reviving any retired follow-on executor. It is provider-inert and is not execution authority.

## Canonical wave

The canonical sequence is `content/telegram/milovi-cake/marathon-wave-2026-08.json`.

It reuses, rather than rewrites:

- `follow-on-wave-candidates-2026-08.json` — the exact frozen 12-item copy set from merged PR #409;
- `follow-on-photo-source-manifest-2026-08.json` — exact source/transport proof for all nine Cake photos;
- `school-interest-reading-candidates-2026-08.json` — the reviewed Milovi School interest-reading pool from merged PR #406.

The sequence remains exactly 12 items: nine Cake and three School items, with School at positions 3, 7 and 11. The final item is Cake. School items remain separate editorial reading, never evidence of Cake recipes, production or French origin.

## Freshness reconciliation performed on 2026-08-20

The frozen Cake source snapshot is `FedorMilovanov/Milovi_Cake@551866f1c34611406fc0a696bec8fc8fb4fd36d8`. Current Cake `main` was read back at `80f071fa6e9ef3024006436cb78d4134c61787cc`; it is the direct child of the reviewed snapshot and its only changed path is `scripts/production_smoke.py`. The gallery/order/bento/review sources used by the frozen wave therefore did not change in that repository step.

The reviewed School snapshot is `FedorMilovanov/Milovi_School@aa82176012b93a50ccfcfb90293d496618e50b61`. Current School `main` read back at the same exact SHA. The selected Ladurée, Paris-Brest and Carême source bindings therefore remain on the exact reviewed repository snapshot.

This is dated freshness evidence, not a promise that external sources can never change. A future provider-visible publication must still resolve current source truth when its mutable claims require it.

## Why there are no frozen dates here

The old follow-on compiler and readiness workflows were intentionally retired by the permanent single-writer consolidation. Reintroducing a dated 12-item scheduler would create a second runtime path and would immediately accumulate stale catch-up debt.

The marathon therefore freezes **sequence and provenance**, not future release IDs or timestamps. When an exact item is deliberately promoted, assign one fresh strict-next `milovi-feed-YYYYMMDD-NNN` identity for a current daylight slot and use the permanent feed control plane only.

If the slot is missed, do not retime the same publication identity and do not catch it up. Generate a new future identity only through a fresh reviewed promotion cycle.

## Content readiness

All nine Cake photo items already have exact reviewed WebP source identity plus deterministic JPEG transport bytes in the existing photo manifest.

All three School items already have frozen copy in the existing 12-item follow-on candidate file and reviewed source identity in the School pool. They require no Cake product CTA and must remain clearly labelled as Milovi School reading.

The remaining nine School pool candidates stay reserve material. The accepted native-video lane remains a separate 16/16 artifact reservoir on `agent/milovi-video-accepted-73c578eff825`; this wave does not create new `sendVideo` authority. Life/kitchen/BTS content remains excluded until a reviewed real source corpus exists.

## Permanent execution boundary

Only `.github/workflows/milovi-telegram-feed-publisher.yml` may perform a Milovi Telegram mutation.

For every future item:

1. preserve the marathon sequence unless a separately reviewed editorial decision changes it;
2. resolve fresh current `main` and applicable source freshness;
3. materialize one immutable permanent-feed bundle for one strict-next daylight slot;
4. pass current feed quality;
5. separately authorize the exact release/content identity;
6. initialize durable state provider-free;
7. separately record fresh exact human execution authority;
8. use one provider attempt with zero blind retries and exact outcome reconciliation.

Historical #409/#410/#412/#413 artifacts and their retired workflows never become execution authority. Nothing in this file authorizes Telegram access or mutation.
