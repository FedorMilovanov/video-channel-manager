from __future__ import annotations

from collections.abc import Mapping

from video_channel_manager.application.identity.digest import evidence_digest
from video_channel_manager.application.identity.models import (
    ExactFieldReadback,
    FieldReadbackItem,
    TextPurpose,
)
from video_channel_manager.application.identity.text import canonicalize_text


def compare_exact_fields(
    expected: Mapping[str, str],
    observed: Mapping[str, str],
    purposes: Mapping[str, TextPurpose],
) -> ExactFieldReadback:
    missing_purposes = sorted(set(expected) - set(purposes))
    if missing_purposes:
        raise ValueError(f"missing field purposes: {', '.join(missing_purposes)}")

    items: list[FieldReadbackItem] = []
    missing_fields: list[str] = []
    for field in sorted(expected):
        expected_evidence = canonicalize_text(expected[field], purposes[field])
        observed_value = observed.get(field)
        if observed_value is None:
            missing_fields.append(field)
            items.append(
                FieldReadbackItem(
                    field=field,
                    purpose=purposes[field],
                    expected=expected_evidence,
                    observed=None,
                    exact=False,
                )
            )
            continue
        observed_evidence = canonicalize_text(observed_value, purposes[field])
        items.append(
            FieldReadbackItem(
                field=field,
                purpose=purposes[field],
                expected=expected_evidence,
                observed=observed_evidence,
                exact=expected_evidence.canonical == observed_evidence.canonical,
            )
        )

    unexpected_fields = sorted(set(observed) - set(expected))
    exact = not missing_fields and all(item.exact for item in items)
    payload = {
        "ruleset_version": "wave-8b-v1",
        "items": [
            {
                "field": item.field,
                "purpose": item.purpose.value,
                "expected_digest": item.expected.digest,
                "observed_digest": item.observed.digest if item.observed is not None else None,
                "exact": item.exact,
            }
            for item in items
        ],
        "missing_fields": missing_fields,
        "unexpected_fields": unexpected_fields,
        "exact": exact,
    }
    return ExactFieldReadback(
        items=items,
        missing_fields=missing_fields,
        unexpected_fields=unexpected_fields,
        exact=exact,
        digest=evidence_digest(payload),
    )
