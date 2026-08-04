# Recurring false patterns and required countermeasures

This file is the compact search target future agents should consult before changing upload, matching, checking, or operator code.

| False pattern | Why it failed | Required countermeasure |
|---|---|---|
| Hard-coded channel counts define success | Counts became stale and the classification itself was wrong | Counts are report outputs; bind exact IDs and manifest digests |
| Fresh snapshots guarantee correct matching | Fresh evidence can still be interpreted by a bad matcher | Exact reviewed mapping first; fuzzy fallback must expose ambiguity |
| A vertical upload is equivalent to a Clip | VK may return ordinary `video` | Verify final user-required surface/type; fail closed on mismatch |
| One CSS/text selector is an upload contract | Provider UI changes | Adapter boundary, resilient discovery, evidence, manual fallback |
| Every requested ID returns an object | Missing IDs produced empty responses/placeholders | Validate exact object identity and required fields before counting |
| Clip text is always in `title` | Native Clips returned `title=None` | Read normalized `title + description` |
| Unique duration is identity | Different media can share durations | Duration is supporting evidence only |
| Visual verification can proceed without local media | Only one of 48 files was available | Mark fingerprint verification unavailable, never implied |
| First 30 visible means a hard limit of 30 | Remaining uploads appeared after delay | Bounded polling and eventual-consistency state |
| “Missing now” means “safe to upload again” | Accepted or processing objects can appear later | Never retransmit accepted/processing/unknown; reconcile exact IDs |
| Expected duration can be typed into a checker | Manual values were wrong | Read with `ffprobe` from the exact source file |
| Matching gaps are remote ID gaps | Seven unmapped objects created fake gaps | Continuity over complete object set; mapping is a separate layer |
| More checks always mean more safety | Scope expanded into permanent audit overhead | Quick operation scope by default; full audit only on incident/request |
| Every fix deserves another standalone script | Tool sprawl increased operator error | One supported operator and reusable tested modules |

## Archive-to-test rule

Every new historical failure must produce at least one of:

- a regression test in supported code;
- a fail-closed validation rule;
- a provider-contract note;
- an operator simplification;
- an explicit decision that the behavior is not supported.

An archive entry without a countermeasure is incomplete.
