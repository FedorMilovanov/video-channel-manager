# Milovi Issue #323 reviewed PromotionSpec

This artifact is intentionally provider-inert. It does not generate public copy, call VK, or authorize a provider mutation.

A reviewed spec covers exactly the 12 Issue #323 sources and both managed public-copy fields for each source. Every field freezes the exact reviewed current text and its SHA-256. Policy is explicit:

- `managed_exact`: only exact reviewed BEFORE may plan an edit to exact reviewed AFTER. Exact AFTER is treated as already applied.
- `adopt_reviewed_exact`: the exact manually reviewed current value is adopted as the intended value; no edit target exists.
- `preserve_external`: the exact reviewed current value is preserved and the Issue #323 finalizer has zero edit target authority for that field.

A processing/truncation projection is read evidence only and never grants edit eligibility. Any unreviewed drift produces `STOP`.

Batch planning is all-or-nothing: if any of the 24 fields is unresolved, the batch returns zero planned mutations. Even an executable plan reports `provider_mutation_authorized=false`; later execution must require a separate confirmation bound to the exact plan digest.

Do not create the real 12/12 reviewed spec from the legacy title-based promotion builder. First capture current Clip descriptions and current wall-incarnation texts read-only, review those exact values, then explicitly choose policy and (for `managed_exact`) exact target text for each field.
