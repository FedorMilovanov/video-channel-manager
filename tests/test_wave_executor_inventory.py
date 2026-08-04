from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "scripts" / "wave-executors.json"
STATUSES = {"supported_engine", "compatibility_adapter", "retired", "independent_tool"}
RETIRED_MARKER = "_WAVE6_RETIRED_EXECUTOR = True"
RISK_MARKERS = (
    "video.save",
    "wall.post",
    "wall.edit",
    "wall.delete",
    "--execute",
    "EnableProviderWrites",
    "YouTubeCommentWriter",
    "YouTubeDescriptionWriter",
    "VkEditorialWriter",
    "VkThumbnailWriter",
    "VkVideoWriter",
)


def _canonical_text_sha(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _registry() -> dict[str, object]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_every_python_script_is_uniquely_classified_and_digest_bound() -> None:
    payload = _registry()
    assert payload["schema_name"] == "video-manager.wave-executor-registry"
    assert payload["schema_version"] == 1
    assert set(payload["statuses"]) == STATUSES

    entries = payload["executors"]
    assert isinstance(entries, list)
    by_path = {entry["path"]: entry for entry in entries}
    assert len(by_path) == len(entries)

    observed = {path.relative_to(ROOT).as_posix() for path in (ROOT / "scripts").rglob("*.py")}
    assert set(by_path) == observed
    for relative, entry in by_path.items():
        path = ROOT / relative
        assert entry["status"] in STATUSES
        assert entry["sha256"] == _canonical_text_sha(path)
        assert isinstance(entry["direct_entrypoint"], bool)
        assert isinstance(entry["provider_write_capable"], bool)
        assert isinstance(entry["callers"], list)
        assert isinstance(entry["private_imports"], list)


def test_retired_direct_executors_stop_before_historical_write_authority() -> None:
    entries = _registry()["executors"]
    assert isinstance(entries, list)
    retired = [entry for entry in entries if entry["status"] == "retired"]
    assert len(retired) == 26

    for entry in retired:
        assert entry["direct_entrypoint"] is True
        assert entry["provider_write_capable"] is True
        path = ROOT / entry["path"]
        text = path.read_text(encoding="utf-8")
        marker_index = text.index(RETIRED_MARKER)
        guard_index = text.index('if __name__ == "__main__":', marker_index)
        assert guard_index > marker_index
        first_function = text.find("def ")
        if first_function >= 0:
            assert guard_index < first_function, f"retirement guard is not module-early: {entry['path']}"

        tree = ast.parse(text, filename=str(path))
        guard_node_index = next(
            index
            for index, node in enumerate(tree.body)
            if isinstance(node, ast.If)
            and "_WAVE6_RETIRED_EXECUTOR" not in ast.unparse(node.test)
            and "__name__" in ast.unparse(node.test)
            and "__main__" in ast.unparse(node.test)
        )
        prior = tree.body[:guard_node_index]
        assert all(
            isinstance(node, (ast.Import, ast.ImportFrom))
            or (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            or (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "_WAVE6_RETIRED_EXECUTOR" for target in node.targets
                )
            )
            for node in prior
        ), f"retirement guard follows executable module logic: {entry['path']}"


def test_supported_engine_never_imports_historical_scripts_or_private_script_functions() -> None:
    engine_root = ROOT / "src" / "video_channel_manager" / "wave_engine"
    modules = []
    for path in sorted(engine_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                modules.append(module)
                if module.startswith("scripts"):
                    assert all(not alias.name.startswith("_") for alias in node.names)

    assert all(not module.startswith("scripts") for module in modules)


def test_historical_private_imports_are_confined_to_compatibility_adapters() -> None:
    entries = _registry()["executors"]
    assert isinstance(entries, list)
    with_private_imports = [entry for entry in entries if entry["private_imports"]]
    assert with_private_imports
    assert all(entry["status"] == "compatibility_adapter" for entry in with_private_imports)
