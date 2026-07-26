# Content Authoring Guide

## 1. Choose a factual angle

Use one documented angle that belongs to the specific work: composition history, first publication, manuscript history, textual structure, archival provenance, documented context, adaptation history, or performance history.

A strong fact contains names, dates, editions, manuscript states, documented circumstances, or a precise formal observation supported by a source. A weak fact can be pasted under any poem.

## 2. Map claims to sources

List every evidence source in `sources`, then place the supporting IDs in both top-level `source_ids` and `fact.source_ids`. Repository paths must be relative and may not escape the repository. URLs must be absolute HTTP(S) URLs.

Do not cite a source merely because it mentions the author. It must support the actual claim in the paragraph. A playlist may support a navigation link, but it is not evidence for a historical claim unless it actually documents that claim.

## 3. Assign stable identity

`content_id` identifies the editorial record across platforms and plans. It must remain stable when only rendering changes. Do not use a temporary filename, array position, or generated plan operation ID as the canonical content identity.

`variation_key` identifies the exact factual angle, not merely the author. Good keys include the work, angle, and revision, for example `tyutchev-night-sea-two-editions-nice-v3`.

## 4. Write the heading

Use one contextual marker and a concrete noun phrase. Prefer “Две редакции одного морского текста” to “Великий шедевр Тютчева”. YouTube may add restrained emphasis; VK will remove supported markup cleanly.

Do not place HTML in canonical text. If VK fallback cannot deterministically remove residual markup, preview and plan building must stop for review.

## 5. Write the question

Ask about something visible or audible in the material: a structural transition, a contrast, an image, a performance choice, or the relation between the documented context and the presented version.

Avoid “Понравилось ли вам?” and “Что вы думаете?”.

## 6. Select and order links

The project site and VK community are stable project routes. Add only links relevant to the work: the correct author playlist, a VK album, the primary text, the original work, or a full version. Do not add every available channel link to every record.

Keep labels compact. The URL must remain on the same line as its label in every rendered surface.

Use `rendering_metadata.preferred_link_order` when link order genuinely differs by platform. It may be a shared list or a mapping such as:

```json
{
  "preferred_link_order": {
    "youtube.comment": ["site", "playlist", "vk", "primary_text"],
    "vk.video_description": ["vk", "site", "primary_text", "playlist"]
  }
}
```

Ordering metadata never bypasses platform suitability or required-link rules.

## 7. Assign platform suitability and targets

Use `platform_suitability` to prevent a record from being rendered onto an inappropriate surface. Use `platform_targets` only for stable reviewed IDs; live target state still comes from a fresh snapshot.

Do not infer suitability from the presence of a link. A record intended only for a YouTube comment should not silently become a VK post merely because it contains the VK community URL.

## 8. Review before approval

An approved record requires a timezone-aware ISO-8601 `reviewed_at`, for example `2026-07-25T20:22:00+00:00`.

Before approval:

1. preview every allowed platform surface;
2. inspect mobile line shapes and `label + URL` layout;
3. validate URLs and source mapping;
4. resolve all renderer errors and deliberately review warnings;
5. compare the batch for duplicate content IDs, variation keys, and rendered text;
6. ensure the factual paragraph still says exactly what the sources support.

Approval belongs to the record. Remote execution still requires an immutable snapshot, signed plan, dry-run, exact confirmations, and a platform-specific guarded executor.
