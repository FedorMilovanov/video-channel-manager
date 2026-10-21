"""Shared invariants for third-party GitHub Actions pins.

Security invariant: every external action is pinned to a full 40-hex commit SHA
with a documented release version, so a moving tag or branch can never execute
unreviewed code in a provider-capable workflow.

Version *identity* is deliberately expressed as a reviewed minimum instead of an
exact SHA equality. Pinning the exact SHA in unrelated tests used to make every
routine patch bump (for example ``upload-artifact`` 7.0.1 -> 7.0.2) fail CI in
tests that had nothing to do with the upgrade, which quietly turned a security
maintenance task into a multi-file rewrite. The minimum-version form keeps the
same protection - no downgrade, no unpinned ref - without brittle coupling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

FULL_SHA = re.compile(r"[0-9a-f]{40}")

PIN_PATTERN = re.compile(
    r"uses:\s*(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"@(?P<ref>[^\s#]+)"
    r"(?:\s*#\s*(?P<version>v?[0-9]+(?:\.[0-9]+)*))?"
)

# Reviewed minimum release per action. A bump above the minimum passes without
# editing tests; a downgrade or an undocumented ref fails.
MINIMUM_RELEASES: dict[str, tuple[int, ...]] = {
    "actions/checkout": (7, 0, 1),
    "actions/setup-python": (7, 0, 0),
    "actions/upload-artifact": (7, 0, 1),
}

# Historical refs that must never come back. Each entry was retired for a
# concrete reason (unpinned node16/node20 runtimes or a superseded release).
RETIRED_REFS: frozenset[str] = frozenset(
    {
        "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    }
)


class ActionPinError(AssertionError):
    """Raised when a workflow action reference violates the pin contract."""


@dataclass(frozen=True)
class ActionPin:
    """One parsed ``uses:`` reference from a workflow file."""

    action: str
    ref: str
    version: str | None

    @property
    def release(self) -> tuple[int, ...]:
        raw = (self.version or "0").lstrip("v")
        return tuple(int(part) for part in raw.split("."))

    @property
    def reference(self) -> str:
        return f"{self.action}@{self.ref}"


def iter_action_pins(text: str) -> tuple[ActionPin, ...]:
    """Return every external action reference in a workflow body."""

    return tuple(
        ActionPin(
            action=match.group("action"),
            ref=match.group("ref"),
            version=match.group("version"),
        )
        for match in PIN_PATTERN.finditer(text)
    )


def assert_actions_pinned(text: str, *, source: str = "workflow") -> tuple[ActionPin, ...]:
    """Assert the pin contract for one workflow body and return the pins.

    Raises:
        ActionPinError: if an action is not pinned to a full commit SHA, has no
            documented release version, is below the reviewed minimum, or uses a
            retired reference.
    """

    pins = iter_action_pins(text)
    if not pins:
        raise ActionPinError(f"{source}: expected at least one pinned external action")

    for pin in pins:
        if not FULL_SHA.fullmatch(pin.ref):
            raise ActionPinError(f"{source}: {pin.action} must be pinned to a full 40-hex commit SHA, got {pin.ref!r}")
        if pin.version is None:
            raise ActionPinError(f"{source}: {pin.action}@{pin.ref} must document its release version, e.g. '# v7.0.2'")
        if pin.reference in RETIRED_REFS:
            raise ActionPinError(f"{source}: retired action reference is back: {pin.reference}")

        minimum = MINIMUM_RELEASES.get(pin.action)
        if minimum is not None and pin.release < minimum:
            printable_minimum = ".".join(str(part) for part in minimum)
            raise ActionPinError(
                f"{source}: {pin.action} {pin.version} is below the reviewed minimum v{printable_minimum}"
            )

    return pins


def assert_no_retired_refs(text: str, *, source: str = "workflow") -> None:
    """Assert that no explicitly retired action reference is present."""

    for retired in sorted(RETIRED_REFS):
        if retired in text:
            raise ActionPinError(f"{source}: retired action reference is present: {retired}")


def workflow_files() -> tuple[Path, ...]:
    """Return every tracked workflow file, sorted for deterministic failures."""

    return tuple(sorted(WORKFLOW_DIR.glob("*.yml")))


def workflow_pins() -> dict[str, tuple[ActionPin, ...]]:
    """Validate every workflow file and return its pins keyed by file name."""

    collected: dict[str, tuple[ActionPin, ...]] = {}
    for path in workflow_files():
        text = path.read_text(encoding="utf-8")
        collected[path.name] = assert_actions_pinned(text, source=path.name)
        assert_no_retired_refs(text, source=path.name)
    return collected
