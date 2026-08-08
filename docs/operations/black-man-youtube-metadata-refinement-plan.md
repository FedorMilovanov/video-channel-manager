# «Чёрный человек» — YouTube metadata refinement plan

This note reserves a repository-tracked refinement pass for the already-uploaded private video `x-puy27S2qs` on The Legendary Poet. It does not authorize any provider mutation.

Goals:
- rewrite the description against the canonical YouTube authoring/rendering standards;
- preserve the already-final title unless an explicit title change is separately reviewed;
- preserve the exact uploaded video and existing private visibility;
- preserve exact chapter timestamps;
- validate description formatting before any remote write;
- perform metadata change through a digest-bound plan, exact target ID, before-state preflight, and post-write reread;
- treat thumbnail, playlist membership, pinned comment, and visibility as separate operations.

The refinement pass must read and obey:
- `docs/youtube-editorial-standard.md`;
- `docs/youtube-description-rendering-standard.md`;
- `docs/youtube-copy-authoring-standard.md`;
- `docs/operations/project-identity-registry.md`.

Current exact target:
- channel: `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- video: `x-puy27S2qs`;
- first-upload visibility: `private`;
- final media SHA-256: `e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0`.

Provider writes from this document: 0.
