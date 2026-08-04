from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = (ROOT / "src", ROOT / "scripts")


def _qualified_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def test_wave3_inventory_probe() -> None:
    findings: list[str] = []
    for search_root in SEARCH_ROOTS:
        for path in sorted(search_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _qualified_name(node.func)
                if name in {"httpx.Client", "Client"}:
                    findings.append(f"{path.relative_to(ROOT)}:{node.lineno}:{name}")
    raise AssertionError("WAVE3_HTTP_CLIENT_INVENTORY\n" + "\n".join(findings))
