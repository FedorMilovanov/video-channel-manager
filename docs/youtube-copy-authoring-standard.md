# YouTube copy authoring and handoff standard — The Legendary Poet

Status: required authoring supplement for repository-owned YouTube copy. It does not authorize provider mutation.

This standard sits below the narrower sources of truth:

1. `docs/operations/project-identity-registry.md` — exact project/provider identities;
2. `docs/youtube-editorial-standard.md` — editorial and fact-check boundary;
3. `docs/youtube-description-rendering-standard.md` — exact YouTube formatting/rendering rules;
4. `docs/youtube-comment-editorial-standard.md` — top-level/pinned comment rules;
5. this document — research, authoring and operator handoff workflow.

If rules differ, the more specific canonical document above wins.

## 1. Research before copy

Any description or comment that states dates, publication history, biography, quotation, dedication, historical circumstances or an alleged authorial intention must be researched before it is called final.

Preferred evidence order:

1. academic complete works and critical editions;
2. author manuscripts, letters, diaries and notebooks;
3. first/authorised editions and periodicals;
4. state archives, museums and national libraries;
5. academic commentary and peer-reviewed scholarship;
6. reputable reference works.

For Russian literature prefer sources such as РВБ/ФЭБ, НЭБ/РГБ, Пушкинский Дом and museum/archive collections over anonymous blogs, quote aggregators, SEO pages or school essays.

A factual claim should be traceable to an editorial source ledger. A disputed or interpretive claim is labelled as interpretation rather than converted into certainty. Do not write `автор хотел сказать...` or equivalent unless the evidence actually supports it.

## 2. Literary quality

A finished description is prose for a reader, not an SEO form.

Use concrete images, conflicts, formal decisions, historical facts and musical/visual choices. Avoid universal filler such as:

- «это не просто...»;
- «уникальная атмосфера»;
- «глубокий смысл»;
- «вечные вопросы»;
- «ожившая классика»;
- «никого не оставит равнодушным»;
- «нейросети оживили поэзию».

Strong evaluative words require a concrete reason. AI-assisted music/visual work is described as interpretation or experiment, never as an improvement of the literary original.

## 3. First paragraph

The first paragraph is the share-preview boundary and follows `docs/youtube-description-rendering-standard.md`:

- normally 2–4 sentences;
- no `*` / `_` wrappers;
- no link list;
- no heavy section heading;
- immediate concrete entry into the work rather than an advertisement;
- no mechanical repetition of the video title.

## 4. YouTube formatting

Repository copy may use the formatting supported by the rendering standard:

- `*text*` for bold;
- `_text_` for italic;
- open `https://...` URLs;
- chapter timestamps such as `00:00`;
- restrained bullets/emoji when editorially useful.

Do not use HTML, Markdown link syntax, Markdown tables or backslash escaping intended only to survive chat rendering. Local project/admin URLs must never leak into public copy.

Punctuation around emphasis follows the exact semantic-boundary rules in `docs/youtube-description-rendering-standard.md`.

## 5. Media-dependent claims

Durations, chapter timestamps, file-derived properties and statements about the exact rendered album are not ordinary prose facts. They must be tied to the exact accepted media/timing evidence.

For the Black Man album specifically, `content/youtube/legendary-poet/black-man-album-description-body.txt` intentionally contains a STOP placeholder for chapters. A final description must replace it from the exact verified timing/render package for the same media bytes. Never carry chapter timestamps forward merely because an older description called them final.

No tracked body/template containing an unresolved marker such as `[[...]]` is publishable copy.

## 6. Project identity before provider access

A repository-owned YouTube planner/executor must prove the canonical triple before credentials or provider API access:

```text
project_key + OAuth account alias + exact channel_id
```

For The Legendary Poet the current canonical identity is defined by `docs/operations/project-identity-registry.md` and the machine registry in `video_channel_manager.editorial`.

A caller-supplied OAuth alias is a credential selector, not project identity. Channel readback alone is not a substitute for the canonical project gate.

## 7. Description plan boundary

A guarded description plan must freeze at least:

- schema/version;
- project key;
- OAuth alias;
- exact channel ID;
- exact video ID;
- source copy path + SHA-256;
- exact before description + digest;
- provider read revision/evidence;
- exact after description + digest;
- explicit changed surface (`snippet.description` only);
- preserved surfaces;
- full canonical plan SHA-256.

Old plan schemas are not silently upgraded at execution time. Rebuild them from current code.

Current operational state keeps YouTube provider mutations unauthorized. A review-only plan therefore records `provider_write_authorized=false` and execution refuses it. Changing that field by hand invalidates the plan digest; a future provider mutation requires a separately reviewed authorization path after explicit user authorization.

## 8. No-blind-replay execution contract

If provider execution is separately authorised in the future:

1. revalidate canonical project identity before credentials;
2. require the exact digest-bound confirmation;
3. acquire the exact target write lock;
4. re-prove canonical identity under the lock;
5. re-read the exact video;
6. `after` → already applied / no write;
7. `before` → eligible exact update;
8. any third description state → conflict / STOP;
9. update only description while preserving current title/tags/category fields required by YouTube;
10. re-read and verify the exact description;
11. persist an immutable result.

An HTTP success, exit code or UI appearance is not the postcondition.

## 9. Operator handoff

For an operator-facing copy result, use one obvious file under the canonical `operator-output/` rules in `docs/operations/operator-output-handoff-rule.md`. Print the exact path. Do not make the operator search timestamp trees or select a file by newest modification time.

When text is handed directly in chat for manual insertion, preserve literal YouTube `*...*` and `_..._` markers in a copy-safe text block. Do not teach the operator to repair escaping artifacts manually.

## 10. Black Man canonical inputs

The repository tracks one literary body rather than competing `v2-final` / `v3-final` files:

- `content/youtube/legendary-poet/black-man-album-description-body.txt`;
- `docs/operations/black-man-youtube-description-sources.md`;
- `docs/operations/black-man-youtube-metadata-refinement-plan.md`.

The body is not a final provider payload until its chapter placeholder is replaced and the resulting complete copy passes the current linter and immutable planning workflow.
