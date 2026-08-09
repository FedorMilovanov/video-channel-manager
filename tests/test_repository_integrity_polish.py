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
WAVE14 = ROOT / "docs" / "operations" / "audit-register-v7-2026-08-05.json"

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


def test_completed_state_merge_proof_stays_in_immutable_register() -> None:
    register = json.loads(WAVE14.read_text(encoding="utf-8"))
    proof = register["wave_14_repository_polish"]

    assert proof["pull_request"] == 131  # type: ignore[index]
    assert proof["exact_head"] == "80f701b6926a5a9c788b99c69634b54d63ed1862"  # type: ignore[index]
    assert proof["merge"] == "626f83c6e5c068d7faa8b6d14163b42916faa769"  # type: ignore[index]
    assert proof["ci_run"] == 31000834701  # type: ignore[index]
    assert proof["pytest"] == "801 passed, 1 xfailed"  # type: ignore[index]
    assert proof["ruff_format"] == "451 files already formatted"  # type: ignore[index]
    assert register["provider_queries_during_wave_14"] == 0
    assert register["provider_writes_during_wave_14"] == 0
    assert register["write_plans_created_during_wave_14"] == 0

    current = CURRENT_STATE.read_text(encoding="utf-8")
    assert "main@626f83c6e5c068d7faa8b6d14163b42916faa769" not in current
    assert AUDIT.is_file()
