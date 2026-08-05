from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
SECURITY = ROOT / "docs" / "security.md"
CURRENT_STATE = ROOT / "docs" / "operations" / "current-state.md"
AUDIT = ROOT / "docs" / "operations" / "repository-integrity-audit-2026-08-05.md"

_FENCED_CODE = re.compile(r"(^|\n)(?:```|~~~).*?(?:\n```|\n~~~)(?=\n|$)", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
_EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "tel:", "data:")
_PLACEHOLDERS = {"URL", "EXACT_URL", "EXAMPLE_URL", "PATH", "EXACT_PATH"}


def _markdown_without_code(text: str) -> str:
    return _INLINE_CODE.sub("", _FENCED_CODE.sub("\n", text))


def test_all_repository_json_is_valid() -> None:
    json_files = sorted(ROOT.rglob("*.json"))
    assert json_files

    failures: list[str] = []
    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")

    assert failures == []


def test_local_markdown_links_resolve() -> None:
    markdown_files = sorted(ROOT.rglob("*.md"))
    assert markdown_files

    broken: list[str] = []
    root = ROOT.resolve()
    for document in markdown_files:
        text = _markdown_without_code(document.read_text(encoding="utf-8-sig"))
        for raw_target in _MARKDOWN_LINK.findall(text):
            target = unquote(raw_target.strip().strip("<>"))
            if not target or target.startswith("#") or target.startswith(_EXTERNAL_SCHEMES):
                continue
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target or target in _PLACEHOLDERS:
                continue

            resolved = (ROOT / target.lstrip("/")) if target.startswith("/") else (document.parent / target)
            resolved = resolved.resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            if not resolved.exists():
                broken.append(f"{document.relative_to(ROOT)} -> {raw_target}")

    assert broken == []


def test_public_entrypoints_state_the_current_authorization_boundary() -> None:
    readme = README.read_text(encoding="utf-8")
    security = SECURITY.read_text(encoding="utf-8")

    for statement in (
        "Provider writes, replay, deletion и mutation plans сейчас **не авторизованы**",
        "docs/operations/current-state.md",
        "сами по себе не разрешают запуск",
        "Completed-state CI `30994245235`",
        "Активного roadmap или backlog нет",
    ):
        assert statement in readme

    for stale in (
        "editorial CI run #669",
        "197 тестов",
        "## Следом",
        "safe playlist operations",
    ):
        assert stale not in readme

    for statement in (
        "Provider writes, replay, deletion, and mutation plans are currently unauthorized",
        "Mandatory controls for any future explicitly authorized mutation",
        "A timeout or lost response after dispatch is an unknown outcome, not a retry signal",
    ):
        assert statement in security


def test_roadmap_is_closed_and_not_initial_project_boilerplate() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")

    for statement in (
        "WAVES_0_13_COMPLETED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES",
        "There is no active provider-mutation roadmap",
        "Future work is not a continuation of the closed roadmap",
        "Provider writes, replay, deletion, and unattended execution remain unauthorized",
    ):
        assert statement in roadmap

    for stale in (
        "completed in this PR",
        "Milestone 1 —",
        "Milestone 2 —",
        "Milestone 3 —",
        "Milestone 4 —",
        "Milestone 5 —",
        "Milestone 6 —",
    ):
        assert stale not in roadmap


def test_current_state_retains_completed_state_merge_proof() -> None:
    text = CURRENT_STATE.read_text(encoding="utf-8")

    for fact in (
        "PR #129",
        "44a1590fac0e8fe8b563d35cfd68f2bed4727743",
        "07388521e8d3a2c5d501382227c35bdce6e6470e",
        "30994245235",
        "796 passed, 1 xfailed",
        "449 files already formatted",
        "provider queries/writes/write plans: `0/0/0`",
    ):
        assert fact in text

    assert AUDIT.is_file()
