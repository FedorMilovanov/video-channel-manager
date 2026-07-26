# VK publishing contour status

Дата: 2026-07-25  
Ветка: `integration/youtube-vk-unified-v2`  
PR: `#13`  
Live VK writes during development: **none**

## Added

- self-validating VK catalog plan for albums, memberships and exact video text changes;
- explicit `content/policies/vk-catalog-policy.json` with policy SHA-256;
- empty-album prevention and reviewed title overrides;
- fresh video-coverage digest and locked live re-preflight;
- durable per-operation result journal and full catalog postflight;
- self-validating one-video wall post plan;
- exact video-attachment duplicate scan before `wall.post`;
- exact visible-link validation between wall message and wall source JSON;
- deterministic `guid`, non-retrying wall mutation and `wall.getById` verification;
- source-led SEO article and wall-post drafts for Alexander Blok’s «На поле Куликовом»;
- article/source-ledger validator for claims, source IDs, primary sources, URLs and exact video identity;
- reviewed map for the eleven VK uploads confirmed by the transfer log;
- operator runbook, catalog-policy addendum and article editorial standard.

## Current editorial structure

- `Поющие поэты` — general collection, without claiming every item is full-length;
- author albums retain normal personal names;
- `AI-эксперименты` — separate experimental material;
- `Чёрный человек — Сергей Есенин` — separate cycle/series;
- collections without a mapped live VK video are skipped rather than created empty.

## Safety gate

No catalog or wall execution is authorized by this document. The operator must first:

1. stop all other writers for community `235216998`;
2. create fresh YouTube and VK `AuditPackage` files;
3. build a new catalog plan with both `--mapping-json` and `--policy-json`;
4. inspect the generated plan/report;
5. obtain `conflicts: 0` and, for wall publishing, `duplicate posts found: 0`;
6. validate the article/source bundle;
7. copy exact digests and counts from that dry-run into the explicit execute command.

The article remains `editorial-review`; factual claims are source-mapped and interpretive claims remain human-reviewed. No wall post has been published by this development work.
