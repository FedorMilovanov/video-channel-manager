"""Local VK alias quarantine guard; no provider calls and no token reads.

The owner retired the third-party user credential (issue #662); these aliases
must never be used for VK API reads/writes or for an in-place login refresh.
This is an alias gate only: a renamed alias sharing the same secret is also
prohibited by policy and requires separate token-identity review.
"""

from __future__ import annotations

QUARANTINED_LEGACY_VK_ALIASES = frozenset({"legendary-poet", "default"})


def reject_quarantined_legacy_alias(alias: str) -> None:
    """Fail before settings, a credential store, or any VK client is created."""
    if not isinstance(alias, str) or not alias.strip():
        raise ValueError("VK account alias must be a nonempty string")
    if alias.strip() in QUARANTINED_LEGACY_VK_ALIASES:
        raise ValueError("VK account alias is quarantined (issue #662); use a separately reviewed credential")
