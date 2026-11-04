"""Find modules no production path reaches, so the set can only shrink by decision.

The package ships code that nothing calls: not an import from `src` or `scripts`, not a console
script, not a `python -m` invocation, not a name or path used by a workflow, script or document.
`coverage-ratchet.json` is deliberately not evidence here — it lists every module by path, so it
would make the whole package look used.

The measured set lives in `docs/operations/module-disposition.json` and is checked by
`tests/test_module_disposition.py`, which requires the two sets to be equal in both directions. A
new unreachable module therefore fails CI until it is given a disposition, and a module that starts
being used has to leave the register. Nothing here deletes anything: a module with no owner decision
is recorded as `pending_owner_decision` with a note, so the debt is visible and countable instead of
silently growing.
"""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs/operations/module-disposition.json"

# The registers below name every module by path. They are not evidence that anything calls them.
NOT_EVIDENCE = {
    "docs/operations/coverage-ratchet.json",
    "docs/operations/module-disposition.json",
}

TEXT_SOURCES = (
    ".github/workflows/*.yml",
    "scripts/*",
    "docs/**/*.md",
    "docs/**/*.json",
    "*.md",
    "content/**/*.json",
)


@dataclass(frozen=True)
class Module:
    name: str
    path: Path


def package_modules(root: Path = ROOT) -> dict[str, Module]:
    modules: dict[str, Module] = {}
    for path in (root / "src/video_channel_manager").rglob("*.py"):
        name = ".".join(path.relative_to(root / "src").with_suffix("").parts)
        if name.endswith(".__init__"):
            name = name[: -len(".__init__")]
        modules[name] = Module(name=name, path=path)
    return modules


def text_corpus(root: Path = ROOT) -> dict[str, str]:
    """Every workflow, script and document that can invoke a module, read once."""

    corpus: dict[str, str] = {}
    for pattern in TEXT_SOURCES:
        for path in root.glob(pattern):
            relative = path.relative_to(root).as_posix()
            if path.is_file() and relative not in NOT_EVIDENCE:
                corpus[relative] = path.read_text(encoding="utf-8", errors="ignore")
    return corpus


def _imported_names(tree: ast.Module, own: tuple[str, ...] | None) -> set[str]:
    """Every dotted name this module imports, resolving relative imports against `own`."""

    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level and own:
                base = list(own)
                module = ".".join(base[: len(base) - node.level] + ([module] if module else []))
            targets.update(f"{module}.{alias.name}" if module else alias.name for alias in node.names)
    return targets


def _module_of(target: str, modules: dict[str, Module]) -> str | None:
    """Resolve an imported name to the longest package module it names."""

    candidate = target
    while candidate:
        if candidate in modules:
            return candidate
        if "." not in candidate:
            return None
        candidate = candidate.rsplit(".", 1)[0]
    return None


def reachable_modules(root: Path = ROOT) -> dict[str, str]:
    """Map every reachable module to the one piece of evidence that reaches it."""

    modules = package_modules(root)
    reachable: dict[str, str] = {}

    for group in ("src", "scripts"):
        for path in (root / group).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            own = tuple(path.relative_to(root / "src").with_suffix("").parts) if group == "src" else None
            for imported in _imported_names(tree, own):
                name = _module_of(imported, modules)
                if name is not None and modules[name].path != path:
                    reachable.setdefault(name, f"imported by {path.relative_to(root).as_posix()}")

    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    for script, target in project["project"]["scripts"].items():
        reachable.setdefault(target.split(":")[0], f"console script {script}")

    corpus = text_corpus(root)
    for name, module in modules.items():
        if name in reachable:
            continue
        path_hint = f"{module.path.stem}.py"
        for relative, text in corpus.items():
            if f"-m {name}" in text or name in text or path_hint in text:
                reachable[name] = f"named by {relative}"
                break
    return reachable


def unreachable_modules(root: Path = ROOT) -> dict[str, Module]:
    modules = package_modules(root)
    reachable = reachable_modules(root)
    return {name: module for name, module in modules.items() if name not in reachable}


def evidence_names_module(module: str, evidence: str, root: Path = ROOT) -> bool:
    """True when `evidence` is a repo file that actually names `module`."""

    path = root / evidence
    if not path.is_file():
        return False
    return module in path.read_text(encoding="utf-8", errors="ignore")


def invocation_exists(module: str, root: Path = ROOT) -> bool:
    """True when a workflow, script or document invokes the module by name or by path."""

    module_path = f"src/{module.replace('.', '/')}.py"
    for text in text_corpus(root).values():
        if f"-m {module}" in text or module_path in text:
            return True
    return False
