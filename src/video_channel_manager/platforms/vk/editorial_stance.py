from __future__ import annotations

from typing import Any

THE_LEGENDARY_POET_EDITORIAL_PROFILE_ID = "the-legendary-poet-historical-evangelical-v1"

_REQUIRED_PROFILE_VALUES = {
    "authority_repository": "FedorMilovanov/TheLegendaryPoet",
    "theological_position": "historical_evangelical_christianity",
    "judgment_mode": "asymmetric_evidence_based",
    "last_hour_rule": "acknowledge_once_not_equal_to_documented_life",
    "tone": "sorrow_without_sentimental_acquittal_or_gloating",
    "gospel_call": "repent_and_believe_in_christ",
}


def validate_the_legendary_poet_editorial_stance(
    decisions: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Validate the owner-defined theological and editorial authority profile.

    The profile deliberately rejects two opposite errors: claiming omniscience
    about an undocumented last instant, and using that abstract possibility to
    neutralize strong documentary evidence of unbelief and absent repentance.
    """

    profile = decisions.get("editorial_profile")
    if not isinstance(profile, dict):
        raise ValueError("Correction decisions have no editorial_profile")
    if str(profile.get("profile_id") or "") != THE_LEGENDARY_POET_EDITORIAL_PROFILE_ID:
        raise ValueError("Correction decisions use an unsupported editorial profile")
    for field, expected in _REQUIRED_PROFILE_VALUES.items():
        if str(profile.get(field) or "") != expected:
            raise ValueError(f"Editorial profile field {field} must be {expected}")

    principles = profile.get("principles")
    if not isinstance(principles, list) or not principles:
        raise ValueError("Editorial profile must contain explicit principles")
    required_principles = {
        "judge_public_confession_and_stable_fruits_by_scripture",
        "do_not_invent_last_hour_conversion",
        "do_not_balance_documented_unbelief_with_bare_possibility",
        "state_eternal_danger_plainly_when_evidence_is_strong",
        "speak_with_grief_not_superiority",
    }
    actual_principles = {str(value) for value in principles}
    missing = sorted(required_principles - actual_principles)
    if missing:
        raise ValueError(f"Editorial profile is missing required principles: {missing}")

    stance_source_ids = [str(value) for value in decisions.get("stance_source_ids") or []]
    if not stance_source_ids:
        raise ValueError("Correction decisions have no stance_source_ids")
    unknown = sorted(source_id for source_id in stance_source_ids if source_id not in sources)
    if unknown:
        raise ValueError(f"Editorial stance references unknown sources: {unknown}")
    authorities = {str(sources[source_id].get("authority") or "") for source_id in stance_source_ids}
    if not any("The Legendary Poet" in authority for authority in authorities):
        raise ValueError("Editorial stance must cite The Legendary Poet standards")
    if not any("Research" in authority for authority in authorities):
        raise ValueError("Editorial stance must cite the Research knowledge base")

    return profile


__all__ = [
    "THE_LEGENDARY_POET_EDITORIAL_PROFILE_ID",
    "validate_the_legendary_poet_editorial_stance",
]
