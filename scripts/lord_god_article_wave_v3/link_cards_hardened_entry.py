from __future__ import annotations

from typing import Any, Callable

import httpx

from . import link_cards_hardened as core
from .common import canonical_sha

_original_audit_sources = core.audit_sources


def audit_sources(
    policy: dict[str, Any],
    contract: dict[str, Any],
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reject an OG image that changes between the two read-only audit passes."""
    rows, manifest = _original_audit_sources(
        policy,
        contract,
        client_factory=client_factory,
    )
    for row in rows:
        first_sha = str(row.get("image_sha256") or "")
        dimension_sha = str(row.get("dimension_check_sha256") or "")
        if not first_sha or not dimension_sha or first_sha == dimension_sha:
            continue
        conflicts = row.setdefault("conflicts", [])
        if isinstance(conflicts, list):
            conflicts.append(
                {
                    "code": "og_image_changed_between_audit_passes",
                    "detail": f"first={first_sha}; dimensions={dimension_sha}",
                }
            )
        checks = row.get("checks")
        if isinstance(checks, dict):
            checks["og_image_dimensions_verified"] = False
        row["status"] = "conflict"

    global_conflicts = manifest.get("global_conflicts")
    if not isinstance(global_conflicts, list):
        global_conflicts = []
    conflict_count = sum(
        len(row.get("conflicts", []))
        for row in rows
        if isinstance(row.get("conflicts"), list)
    ) + len(global_conflicts)
    manifest.update(
        {
            "status": "verified" if conflict_count == 0 else "blocked",
            "og_image_dimensions_verified": sum(
                bool(row.get("checks", {}).get("og_image_dimensions_verified"))
                for row in rows
                if isinstance(row.get("checks"), dict)
            ),
            "conflicts": conflict_count,
            "conflicting_operations": sum(
                row.get("status") == "conflict" for row in rows
            ),
            "global_conflicts": global_conflicts,
            "items": rows,
        }
    )
    manifest["manifest_sha256"] = canonical_sha(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    return rows, manifest


core.audit_sources = audit_sources

main = core.main
guarded_main = core.guarded_main
