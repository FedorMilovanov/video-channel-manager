from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from video_channel_manager.editorial._project_profiles import PROJECT_KEYS, PROJECT_VK_COMMUNITY_IDS
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.clips_owner_reconciliation import (
    VK_OWNER_CLIPS_WALL_RECONCILIATION_SCHEMA,
)

VK_OWNER_ONLY_TRIAGE_SCHEMA = "vk-owner-only-clips-risk-triage-v1"
_OWNER_PROBE_SCHEMA = "vk-owner-clips-experimental-probe-v2"

RiskDisposition = Literal[
    "IP_HOLD_HIDE",
    "IP_GUIDELINE_REVIEW",
    "VISUAL_REVIEW",
    "AMBIGUOUS_REVIEW",
]

_IP_HOLD_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("shrek", ("shrek", "шрек")),
    ("ladybug", ("ladybug", "lady bug", "леди баг")),
    ("cat_noir", ("cat noir", "chat noir", "супер кот", "суперкот")),
    ("squid_game", ("squid game", "игра в кальмара")),
    ("om_nom", ("om nom", "omnom", "ам ням")),
)
_IP_GUIDELINE_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("minecraft", ("minecraft", "майнкрафт")),
)
_VISUAL_REVIEW_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fox", ("fox", "лиса", "лисич")),
    ("bear", ("bear", "медвед")),
    ("bunny", ("bunny", "rabbit", "заяц", "кролик")),
    ("basketball", ("basketball", "баскетбол")),
    ("book", ("book", "книга")),
)
_TRADEMARK_NAMING_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("snickers", ("snickers", "сникерс")),
    ("ferrero", ("ferrero", "ферреро")),
)
_CROSS_PROJECT_SIGNAL_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("legendary_poet_brand", ("the legendary poet", "легендарный поэт")),
    ("mayakovsky", ("маяковск", "mayakovsky")),
    ("yesenin", ("есенин", "yesenin")),
    ("pushkin", ("пушкин", "pushkin")),
    ("lermontov", ("лермонтов", "lermontov")),
    ("pasternak", ("пастернак", "pasternak")),
    ("tyutchev", ("тютчев", "tyutchev")),
    ("fet", ("афанасий фет", "feta poet")),
    ("blok", ("александр блок", "alexander blok")),
)


def _normalize_text(value: str) -> str:
    lowered = value.casefold().replace("ё", "е")
    return " ".join(part for part in re.split(r"[^0-9a-zа-я]+", lowered) if part)


def _matched_labels(text: str, rules: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    normalized = f" {_normalize_text(text)} "
    labels: list[str] = []
    for label, phrases in rules:
        for phrase in phrases:
            normalized_phrase = _normalize_text(phrase)
            if normalized_phrase and f" {normalized_phrase} " in normalized:
                labels.append(label)
                break
            if normalized_phrase in {"лисич", "медвед", "маяковск"} and normalized_phrase in normalized:
                labels.append(label)
                break
    return labels


def _validate_identity(*, project_key: str, community_id: int, owner_id: int) -> str:
    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        raise ValueError(f"unknown project_key for VK owner-only triage: {project_key}")
    if isinstance(community_id, bool) or not isinstance(community_id, int) or community_id <= 0:
        raise ValueError("VK community_id must be a positive integer")
    if isinstance(owner_id, bool) or not isinstance(owner_id, int) or owner_id >= 0:
        raise ValueError("VK owner_id must be a negative integer")
    if community_id not in PROJECT_VK_COMMUNITY_IDS.get(normalized_project, frozenset()):
        raise ValueError(
            f"VK community differs from canonical project identity for {normalized_project}: {community_id}"
        )
    if owner_id != -community_id:
        raise ValueError(f"VK owner differs from canonical community identity for {normalized_project}: {owner_id}")
    return normalized_project


def _validate_reconciliation(
    payload: dict[str, Any],
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
    owner_probe: dict[str, Any],
) -> list[str]:
    if payload.get("schema") != VK_OWNER_CLIPS_WALL_RECONCILIATION_SCHEMA:
        raise ValueError("unsupported VK owner Clips wall reconciliation schema")
    if payload.get("read_only") is not True or payload.get("provider_writes") != 0:
        raise ValueError("VK owner Clips wall reconciliation is not provider-free")
    if payload.get("project_key") != project_key:
        raise ValueError("reconciliation project differs from triage target")
    if payload.get("community_id") != community_id or payload.get("owner_id") != owner_id:
        raise ValueError("reconciliation exact community/owner differs from triage target")

    expected_hash = payload.get("reconciliation_sha256")
    if not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
        raise ValueError("reconciliation has no canonical digest")
    unsigned = {key: value for key, value in payload.items() if key != "reconciliation_sha256"}
    if canonical_sha256(unsigned) != expected_hash:
        raise ValueError("reconciliation canonical digest mismatch")

    input_evidence = payload.get("input_evidence")
    reconciliation = payload.get("reconciliation")
    if not isinstance(input_evidence, dict) or not isinstance(reconciliation, dict):
        raise ValueError("reconciliation evidence is structurally incomplete")
    if input_evidence.get("owner_probe_sha256") != canonical_sha256(owner_probe):
        raise ValueError("owner probe bytes differ from reconciliation-bound evidence")
    if reconciliation.get("surface_complete_claim") is not False:
        raise ValueError("reconciliation must not claim complete owner surface")
    owner_only = reconciliation.get("owner_only_remote_ids")
    if not isinstance(owner_only, list) or any(not isinstance(item, str) for item in owner_only):
        raise ValueError("reconciliation owner_only_remote_ids are invalid")
    if reconciliation.get("owner_only_count") != len(owner_only):
        raise ValueError("reconciliation owner_only_count differs from exact IDs")
    if len(set(owner_only)) != len(owner_only):
        raise ValueError("reconciliation owner_only IDs must be unique")
    return owner_only


def _validate_owner_probe(
    payload: dict[str, Any],
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
) -> dict[str, dict[str, Any]]:
    if payload.get("schema") != _OWNER_PROBE_SCHEMA:
        raise ValueError("unsupported VK owner Clips probe schema")
    if payload.get("read_only") is not True or payload.get("provider_effect") != "safe_read_only":
        raise ValueError("owner Clips probe is not proven read-only")
    if payload.get("project_key") != project_key:
        raise ValueError("owner Clips probe project differs from triage target")
    community = payload.get("community")
    if not isinstance(community, dict):
        raise ValueError("owner Clips probe has no exact community evidence")
    if community.get("community_id") != community_id or community.get("owner_id") != owner_id:
        raise ValueError("owner Clips probe exact community/owner differs from triage target")
    if community.get("managed_by_token") is not True:
        raise ValueError("owner Clips probe did not prove exact managed community")

    clips = payload.get("clips")
    if not isinstance(clips, list):
        raise ValueError("owner Clips probe has no exact clip records")
    by_id: dict[str, dict[str, Any]] = {}
    for item in clips:
        if not isinstance(item, dict):
            raise ValueError("owner Clips probe contains a non-object clip record")
        remote_id = str(item.get("remote_id") or "")
        if not remote_id.startswith(f"{owner_id}_"):
            raise ValueError(f"owner Clips probe contains foreign or invalid remote ID: {remote_id}")
        if item.get("is_native_clip") is not True or item.get("type") != "short_video":
            raise ValueError(f"owner Clips probe lacks exact native Clip proof: {remote_id}")
        if remote_id in by_id:
            raise ValueError(f"owner Clips probe contains duplicate remote ID: {remote_id}")
        by_id[remote_id] = item
    return by_id


def classify_owner_only_clip(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "")
    description = str(item.get("description") or "")
    searchable = f"{title}\n{description}"

    hold_matches = _matched_labels(searchable, _IP_HOLD_TERMS)
    guideline_matches = _matched_labels(searchable, _IP_GUIDELINE_TERMS)
    visual_matches = _matched_labels(searchable, _VISUAL_REVIEW_TERMS)
    trademark_matches = _matched_labels(searchable, _TRADEMARK_NAMING_TERMS)
    cross_project_matches = _matched_labels(searchable, _CROSS_PROJECT_SIGNAL_TERMS)

    if hold_matches:
        disposition: RiskDisposition = "IP_HOLD_HIDE"
        rationale = "explicit named franchise/character signal; hold migration/amplification pending separate review"
    elif guideline_matches:
        disposition = "IP_GUIDELINE_REVIEW"
        rationale = "explicit Minecraft signal; conditional first-party usage guidance may apply and requires review"
    elif visual_matches:
        disposition = "VISUAL_REVIEW"
        rationale = "generic visual/title category; text alone is insufficient for an IP or project conclusion"
    else:
        disposition = "AMBIGUOUS_REVIEW"
        rationale = "no approved text-only risk rule resolves this owner-only candidate"

    return {
        "remote_id": str(item.get("remote_id") or ""),
        "title": title,
        "description": description,
        "risk_disposition": disposition,
        "risk_rationale": rationale,
        "ip_hold_signals": hold_matches,
        "guideline_review_signals": guideline_matches,
        "visual_review_signals": visual_matches,
        "trademark_naming_review": bool(trademark_matches),
        "trademark_naming_signals": trademark_matches,
        "cross_project_signal_review": bool(cross_project_matches),
        "cross_project_signals": cross_project_matches,
        "audio_policy": "operator_confirmed_non_blocking_absent_exact_provider_claim",
        "provider_mutation_authorized": False,
        "delete_authorized": False,
        "hide_authorized": False,
        "upload_authorized": False,
    }


def build_owner_only_risk_triage(
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
    reconciliation: dict[str, Any],
    owner_probe: dict[str, Any],
) -> dict[str, Any]:
    normalized_project = _validate_identity(
        project_key=project_key,
        community_id=community_id,
        owner_id=owner_id,
    )
    probe_by_id = _validate_owner_probe(
        owner_probe,
        project_key=normalized_project,
        community_id=community_id,
        owner_id=owner_id,
    )
    owner_only_ids = _validate_reconciliation(
        reconciliation,
        project_key=normalized_project,
        community_id=community_id,
        owner_id=owner_id,
        owner_probe=owner_probe,
    )

    missing = [remote_id for remote_id in owner_only_ids if remote_id not in probe_by_id]
    if missing:
        raise ValueError(f"reconciliation owner-only IDs are absent from exact owner-probe records: {missing}")

    candidates = [classify_owner_only_clip(probe_by_id[remote_id]) for remote_id in sorted(owner_only_ids)]
    dispositions = Counter(str(item["risk_disposition"]) for item in candidates)
    trademark_count = sum(1 for item in candidates if item["trademark_naming_review"] is True)
    cross_project_count = sum(1 for item in candidates if item["cross_project_signal_review"] is True)
    provider_probe = owner_probe.get("provider_probe")
    provider_status = provider_probe.get("status") if isinstance(provider_probe, dict) else None

    result: dict[str, Any] = {
        "schema": VK_OWNER_ONLY_TRIAGE_SCHEMA,
        "project_key": normalized_project,
        "community_id": community_id,
        "owner_id": owner_id,
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "source_scope": "reconciliation.owner_only_remote_ids",
        "input_evidence": {
            "reconciliation_sha256": canonical_sha256(reconciliation),
            "owner_probe_sha256": canonical_sha256(owner_probe),
            "owner_probe_status": provider_status,
            "owner_surface_complete_claim": False,
        },
        "summary": {
            "owner_only_candidate_count": len(candidates),
            "risk_disposition_counts": dict(sorted(dispositions.items())),
            "trademark_naming_review_count": trademark_count,
            "cross_project_signal_review_count": cross_project_count,
            "delete_authorized_count": 0,
            "hide_authorized_count": 0,
            "upload_authorized_count": 0,
        },
        "policy": {
            "IP_HOLD_HIDE": "hold migration/amplification; label alone does not authorize hiding or deleting provider content",
            "IP_GUIDELINE_REVIEW": "review first-party usage guidance; do not auto-delete or auto-migrate",
            "VISUAL_REVIEW": "inspect visual/source evidence; title text alone is insufficient",
            "AMBIGUOUS_REVIEW": "no provider mutation until exact source/target evidence resolves the item",
            "trademark_naming_review": "commercial naming review is separate from character/IP hold and is not auto-delete authority",
            "cross_project_signal_review": "text is only a signal; exact project provenance is required before cross-project classification",
        },
        "candidates": candidates,
    }
    result["triage_sha256"] = canonical_sha256({key: value for key, value in result.items() if key != "triage_sha256"})
    return result


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Triage Milovi VK owner-only Clips from saved provider-free evidence.")
    root.add_argument("--project", required=True)
    root.add_argument("--community", type=int, required=True)
    root.add_argument("--owner-id", type=int, required=True)
    root.add_argument("--reconciliation", type=Path, required=True)
    root.add_argument("--owner-probe", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    reconciliation = _load_json(args.reconciliation)
    owner_probe = _load_json(args.owner_probe)
    if not isinstance(reconciliation, dict) or not isinstance(owner_probe, dict):
        raise ValueError("triage inputs must be JSON objects")
    result = build_owner_only_risk_triage(
        project_key=args.project,
        community_id=args.community,
        owner_id=args.owner_id,
        reconciliation=reconciliation,
        owner_probe=owner_probe,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "owner_only_candidates": result["summary"]["owner_only_candidate_count"],
                "risk_dispositions": result["summary"]["risk_disposition_counts"],
                "trademark_naming_review": result["summary"]["trademark_naming_review_count"],
                "cross_project_signal_review": result["summary"]["cross_project_signal_review_count"],
                "provider_writes": 0,
                "provider_mutation_authorized": False,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "VK_OWNER_ONLY_TRIAGE_SCHEMA",
    "build_owner_only_risk_triage",
    "classify_owner_only_clip",
]
