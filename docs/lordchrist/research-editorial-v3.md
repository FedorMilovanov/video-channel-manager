# Lordchrist research editorial v3

Status: provider-inert editorial successor  
Owner: issue #263  
Predecessor approved release: `sha256:b836f9dc6733cdc922e5aaed97c250d1d46484fe75a216c1f12e586214a2626f`

This revision exists because the first live research-v2 post proved two separate facts:

1. the historical/source work is useful and should be preserved;
2. heading-only Telegram formatting is not an acceptable reader presentation for long research posts.

The already-attempted v2 queue, release, ledger and dispatch evidence are immutable operational history. V3 therefore does **not** rewrite those files. It creates new publication identities only for predecessor posts 2–5.

## Reader-copy standard

Research copy must be restrained Russian prose rather than a ranking, motivational performance, bureaucratic memo or AI-sounding sequence of symmetrical slogans.

Required principles:

- distinguish historical evidence from pastoral reflection;
- keep numerical claims in the exact scope accepted by the research evidence;
- do not turn archive size, fame, productivity or historical influence into a measurement of greatness in the Kingdom of God;
- it is appropriate to thank God for unusually broad historical influence as a providentially given stewardship;
- remember the many named and unnamed people through whom ministry is recorded, edited, preserved, taught and transmitted;
- teachers may be respected, learned from and gratefully admired without being made infallible;
- where the post discusses authority, Christ and Scripture remain the final norm;
- do not imply that a little-known servant is less faithful because less material survived or fewer people know the name;
- avoid hype such as genius/record/hero language unless it is itself the historical subject and is explicitly qualified;
- avoid canned transitions and bureaucratic language such as `следует отметить`, `данный показатель`, `на деле всё интереснее`, or staged rhetorical crescendo for its own sake.

## Telegram presentation standard

Each post has two separately hashed artifacts:

- `.txt` — canonical visible reader text;
- `.html` — Telegram presentation using only the repository-supported `bold` and `italic` entity surface.

The validator fails closed unless parsing the HTML yields **exactly the canonical `.txt` text**. Formatting therefore cannot silently rewrite, omit or add a word.

Presentation rules:

- bold the exact title;
- use bold section headings where the material has real internal structure;
- bold only a small number of dates, counts or conclusions that aid scanning;
- use italic for a concluding reflection or a work title where appropriate;
- keep emoji restrained and functional, normally one title marker plus section markers;
- preserve real blank-line paragraph separation in the Telegram plain text;
- do not introduce source links into reader copy merely to decorate the post;
- do not depend on Markdown syntax: provider payloads use Telegram HTML and exact expected entities.

## Current successor contents

The provider-inert v3 package contains exactly four successor posts:

1. `lordchrist-research-v3-sermons-survive-century`
2. `lordchrist-research-v3-learning-across-generations`
3. `lordchrist-research-v3-three-expository-patterns`
4. `lordchrist-research-v3-hidden-discipline`

Each maps to exactly one predecessor v2 post and carries the complete predecessor claim-id set. This keeps the accepted evidence map visible while allowing new reader copy and presentation hashes.

## Activation boundary

V3 must remain provider-inert until the first v2 live post is reconciled from `unknown / may_exist` to a truthful durable state. A visible Telegram message is not by itself permission to forge a receipt or blind-retry the old mutation.

After reconciliation, a separate reviewed rollout may build a fresh four-item generic release starting from the next intended publication date. That rollout must bind the exact channel/bot, exact v3 candidate digest, current-main CI and a new publication ledger. This document does not authorize Telegram writes.
