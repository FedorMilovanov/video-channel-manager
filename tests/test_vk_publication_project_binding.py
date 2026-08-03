from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_RENDER_FUNCTIONS = frozenset(
    {
        "render_vk_publication",
        "render_vk_publication_description",
        "render_vk_publication_title",
    }
)


def _unbound_publication_calls() -> list[str]:
    offenders: list[str] = []
    for source_root in (ROOT / "src", ROOT / "scripts"):
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function_name: str | None = None
                if isinstance(node.func, ast.Name):
                    function_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    function_name = node.func.attr
                if function_name not in _RENDER_FUNCTIONS:
                    continue
                if any(keyword.arg == "project_key" for keyword in node.keywords):
                    continue
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}:{function_name}")
    return offenders


def test_every_vk_publication_render_call_binds_a_project() -> None:
    assert _unbound_publication_calls() == []
