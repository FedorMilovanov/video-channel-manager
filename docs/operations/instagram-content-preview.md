# Instagram content preview

Status: provider-inert  
Owner issue: #492

This runbook covers only the Instagram editorial/rendering system for `legendary-poet` and `lord-god-strength`. It performs no Instagram/Meta publication or profile mutation.

## Canonical editorial records

Instagram is a first-class target of the existing canonical editorial preview pipeline. A record must explicitly allow the requested surface in `platform_suitability`.

```powershell
video-manager content preview `
  --input .\content\editorial\examples\record.json `
  --platform instagram `
  --surface reel `
  --json-output .\data\reports\instagram-record-preview.json
```

Supported surfaces are `reel`, `feed`, and `carousel`. Legacy YouTube records are not silently opted into Instagram.

If a canonical `platform_targets` entry is present for Instagram, its value must be an exact numeric Instagram provider account ID. Public handles and usernames are display/discovery metadata only and fail target validation.

## Repository launch packs

The two launch corpora are strict `video-manager.instagram-launch-pack` v1 documents. Unknown fields fail closed; candidate/source IDs and variation keys are unique; every candidate references known source-led evidence and keeps unresolved blockers explicit.

Render an exact pack with:

```powershell
video-manager instagram launch-preview `
  .\content\instagram\legendary-poet-launch-candidates.json `
  --output .\data\reports\legendary-poet-instagram-launch-preview.json
```

or:

```powershell
video-manager instagram launch-preview `
  .\content\instagram\lord-god-strength-launch-candidates.json `
  --output .\data\reports\lord-god-strength-instagram-launch-preview.json
```

The command hashes the exact input bytes and writes `source_pack_sha256` into `video-manager.instagram-launch-preview` v1. The preview artifact is fixed to:

- `evidence_scope=exact_launch_pack_bytes`;
- `provider_effect=impossible`;
- `provider_writes_authorized=false`.

The launch-pack builder and canonical editorial renderer share the same `render_instagram_caption` engine. There is no separate launch-only rendering behavior.

Use `--strict` when warnings must also produce a non-zero exit. Blocking renderer errors always produce exit code 2 after the preview artifact is written.

## Caption diagnostics

The deterministic renderer checks repository rules, not guessed Instagram ranking formulas:

- concrete source-led topic/body required;
- 3–6 tightly relevant hashtags as a house readability rule;
- malformed/duplicate hashtags rejected;
- raw HTTP(S) URLs rejected from caption copy;
- colored circles and known clickbait phrases rejected;
- Lord God engagement-as-faith bait rejected;
- required generative-audio provenance disclosure enforced;
- internal mobile-readability warning above 1,800 characters, explicitly not a provider limit;
- requested surface must be explicitly allow-listed.

## Analytics exchange contract

`video-manager schema export` exports `instagram-analytics-snapshot-v1.schema.json` alongside the launch-pack and preview schemas.

Metric state is explicit:

- `observed` requires a numeric value, including a legitimate observed zero;
- `unavailable` requires `value=null`;
- `not_observed` requires `value=null`.

Therefore unknown/unavailable is never silently converted to zero.

Each analytics snapshot is tied to exact project/candidate identity, exact numeric Instagram Professional account ID, exact media ID, creative SHA-256, publication/observation timestamps, and source-evidence SHA-256. The contract remains read-only and sets `provider_writes_authorized=false`.

## Safety boundary

Issue #492 ends at deterministic editorial preparation, identity-safe preview, media/factory routing and analytics contracts. It does not authorize a Meta publishing executor. A future provider-write scope must separately prove exact account binding, exact reviewed output bytes, write authorization, provider preflight, remote postconditions and guarded recovery.
