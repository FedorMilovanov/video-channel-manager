# Instagram Reel factory and whole-channel coverage

Status: provider-inert  
Owner issue: #495  
Project: `legendary-poet`

This runbook starts after `docs/operations/instagram-video-intake-routing.md`. It turns exact source authority into a deterministic Reel production queue without allowing current uploads outside the reviewed factory to disappear silently.

## 1. Machine registry, not a handwritten-only backlog

Canonical machine registry:

```text
content/instagram/legendary-poet-reels-factory.json
```

Human editorial companion:

```text
content/instagram/legendary-poet-reels-factory-plan.md
```

The registry currently freezes **59 distinct Reel jobs** across fourteen editorial families. CI requires its Reel IDs to equal the reviewed Markdown plan headings exactly.

The registry is source-bound:

- exact YouTube sources use channel id `UC-78ys2S3cQ3lpqgXfo-SvQ` + exact video id + reviewed editorial record;
- site audio sources freeze repository, exact site commit, catalog blob, record id, asset path, duration and asset SHA-256;
- site editorial sources freeze repository, exact site commit, exact source-file blob and exported symbol.

Current site commit pin:

```text
a3918bfd5364e4642fe41a613e89986526b4db37
```

Do not replace the commit pin with the repository tree SHA. A commit object and its tree are separate Git identities.

## 2. Job gates are explicit

Each job states independently whether it requires:

- `requires_clean_master`;
- `requires_exact_text_span`;
- `requires_exact_timing`.

`requires_exact_timing=true` is invalid unless the same job also requires a clean master. The factory never stores invented `00:xx` cut points, "best 20 seconds", "chorus" guesses or similar placeholders.

Production modes:

- `source_led` — factual/editorial Reel can be built from reviewed source authority without reusing the historical social-video bytes;
- `hybrid` — source-led argument plus one or more gated text/media ingredients;
- `master_timed` — exact clean master and exact reviewed timing are mandatory.

## 3. Deterministic production queue

Without a media-route artifact:

```powershell
video-manager instagram reel-queue `
  .\content\instagram\legendary-poet-reels-factory.json `
  --output .\data\reports\legendary-poet-instagram-reel-queue.json
```

With exact local media evidence + rights/provenance routing:

```powershell
video-manager instagram reel-queue `
  .\content\instagram\legendary-poet-reels-factory.json `
  --media-route .\data\reports\legendary-poet-instagram-media-route.json `
  --output .\data\reports\legendary-poet-instagram-reel-queue.json
```

The queue hashes the exact registry bytes and, when supplied, the exact media-route bytes.

Queue states:

| State | Meaning |
| --- | --- |
| `source_led_ready` | reviewed source authority is sufficient for editorial production; no clean-master/text-span/timing gate remains |
| `exact_text_binding_required` | direct literary text still requires exact edition/span binding |
| `source_binding_required` | a clean source master is required but is not exactly bound |
| `materialization_required` | a site-owned audio master is precisely pinned but its bytes still need exact local materialization/verification |
| `timing_selection_required` | clean source path is ready enough to proceed, but exact cut timing has not been reviewed |
| `media_edit_ready` | clean master is bound and no text/timing gate remains; editing can begin |
| `editorial_rebuild_required` | social bytes are not the reusable master, but a separately authorized source-led rebuild lane exists |
| `hold` | rights/provenance/media route blocks production |

The baseline queue intentionally does **not** call a pinned site audio asset “media ready” merely because its repository path and SHA are known. Repository identity and local materialization are different states.

## 4. Current 59-job baseline before media materialization

The regression suite freezes the no-media-route baseline as:

```text
59 total
40 source_led_ready
 8 exact_text_binding_required
 8 source_binding_required
 3 materialization_required
 0 timing_selection_required
 0 media_edit_ready
 0 editorial_rebuild_required
 0 hold
```

This is not a publishing schedule. It is an evidence/readiness partition.

## 5. Whole-channel coverage — the 59 jobs are not the channel boundary

A 59-job factory is useful only if every current YouTube upload remains visible outside it.

`InstagramFactoryCoverageArtifact` joins the exact current `InstagramVideoIntakeArtifact` to the exact Reel registry and assigns every current video exactly one state:

- `covered_by_factory` — at least one exact Reel job already references this YouTube video;
- `reviewed_unexpanded` — a reviewed YouTube editorial record exists, but the current factory has no Reel job for it yet;
- `editorial_review_required` — no reviewed editorial authority exists yet.

The three states must sum to `total_current_videos`. There is no fourth implicit “ignore/archive” state.

The artifact also records exact factory YouTube sources missing from the current snapshot. A factory source is never silently dropped because the current provider inventory changed.

## 6. What the next fresh owner scan unlocks

Run the canonical owner read-only scan first:

```powershell
video-manager youtube scan `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --output .\data\exports\legendary-poet-youtube-current.json
```

Then build the typed intake. The current implementation retains owner-only `fileDetails`, so the intake can separate:

- confirmed Shorts where exact owner evidence proves the conservative post-cutoff square/vertical <=3-minute case;
- confirmed long-form where landscape geometry or >3-minute duration proves it;
- unresolved Short candidates;
- genuinely unknown cases.

Once that exact current intake exists, whole-channel factory coverage produces the real current numbers instead of reusing the July historical `111` mapping or `128`-video prose audit as if either were current state.

## 7. Non-goals

This factory/coverage lane does not:

- download YouTube delivery copies as convenience masters;
- convert a historical mapping into current provider state;
- auto-write captions from unreviewed video descriptions;
- invent direct literary quotations;
- invent Reel cut points;
- treat a previous YouTube/VK publication as Instagram rights clearance;
- infer an Instagram account from a public handle;
- publish anything to Instagram/Meta.

All artifacts remain `provider_effect=impossible` and `provider_writes_authorized=false`.
