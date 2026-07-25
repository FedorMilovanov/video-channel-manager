# Unified Editorial Standard

## Purpose

YouTube and VK use one editorial record and one evidence boundary. Platform differences belong in renderers and guarded executors, not in duplicated authoring schemas.

The canonical schema is `video-manager.editorial-content` version 1. Existing `video-manager.youtube-comment-content` version 2 records remain supported and are parsed as canonical records without reauthoring.

## Canonical record

A record contains:

- `profile`: `long_form_poetry`, `short_form`, `essay`, `historical`, `music_cover`, or a supported legacy equivalent;
- `variation_key`: a stable, work-specific editorial angle;
- `fact.heading`, `fact.text`, `fact.fact_type`, and evidence `fact.source_ids`;
- a concrete `question` about the presented text, performance, structure, or documented context;
- compact semantic `links` (`site`, `playlist`, `vk`, `vk_album`, `primary_text`, `full_version`, and related kinds);
- a complete `sources` ledger;
- `rendering_metadata`, `platform_suitability`, and optional `platform_targets`.

The record stores meaning and evidence. It does not store a separate VK copy and YouTube copy unless a human explicitly decides that two different facts are required.

## Evidence and anti-hallucination rules

Every factual paragraph must map to one or more source IDs. Every source ID must exist in the ledger. Public URLs must be source-backed or belong to the approved project-link map.

Do not generate or approve:

- invented biographical details;
- unsupported dates, publication claims, quotations, motives, or anecdotes;
- mystical or prophetic framing presented as fact;
- phrases such as “поэт предсказал”, “поэты-пророки”, “шедевр на все времена”, or equivalent generic hype;
- automatic literary interpretation disguised as documentary fact.

Interpretation may appear only when clearly framed as an editorial reading and when the wording does not convert interpretation into biography or history.

## Editorial quality

A record must provide a substantial, work-specific fact rather than a replaceable compliment. The question must be answerable from the material and must not be a generic engagement prompt. Links must be relevant to the work and must not become a fixed spam footer.

Variation is controlled by `variation_key`. A batch is invalid when it repeats a variation key, content ID, or final rendered text.

## Markers and tone

Allowed contextual markers include `📌`, `🎧`, `📚`, `📖`, `📝`, `🕯️`, `⚔️`, `❄️`, `🌊`, and `🎼`. Colored circles such as `🔵`, `🔴`, `🟢`, `🟡`, `🟣`, `⚪`, and `⚫` are forbidden.

Use compact literary prose, precise nouns and dates, restrained emphasis, and readable mobile paragraphs. Avoid slogans, inflated claims, aggressive calls to action, and copy-paste headings.

## Compatibility and migration

Legacy YouTube comment schema v2 already contains the canonical semantic fields. The migration path is therefore additive:

1. keep the existing file and validate it through the canonical parser;
2. preview it for YouTube and VK;
3. add `content_id`, `platform_suitability`, `rendering_metadata`, or `platform_targets` only when needed;
4. rename the schema to `video-manager.editorial-content` version 1 when the record becomes cross-platform-owned.

No mass rewrite of approved YouTube records is required.
