from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BLOCKED = "VK_WAVE6_RETIRED_IMPORT_BLOCKED: use the reviewed wave operator."
RETIRED_ENTRYPOINTS = {
    "apply_all_vk_description_cleanup.py": ("main",),
    "apply_vk_catalog_plan.py": ("main",),
    "apply_vk_editorial_cleanup_plan.py": ("main",),
    "apply_vk_wall_post_plan.py": ("main",),
    "apply_youtube_copy_plan_v3.py": ("main",),
    "repair_vk_descriptions_from_sync_journal.py": ("main",),
    "run_vk_p1_final_megawave.py": ("run", "main"),
    "run_vk_wall_wave.py": ("run", "main"),
    "sync_youtube_thumbnails_to_vk.py": ("main",),
    "complete_vk_longform_tail.py": ("main",),
}


@pytest.mark.parametrize(("filename", "entrypoints"), sorted(RETIRED_ENTRYPOINTS.items()))
def test_retired_wave6_imported_dispatchers_refuse_before_provider_code(
    filename: str, entrypoints: tuple[str, ...]
) -> None:
    source = ROOT / "scripts" / filename
    contents = source.read_text(encoding="utf-8")
    module = ast.parse(contents, filename=str(source))
    assert "_WAVE6_RETIRED_EXECUTOR = True" in contents

    for name in entrypoints:
        functions = [fn for fn in module.body if isinstance(fn, ast.FunctionDef) and fn.name == name]
        assert len(functions) == 1, f"Missing unique dispatcher {filename}:{name}"
        fn = functions[0]

        # Require an *unconditional first statement*: the legacy dispatcher
        # must not resolve a token, open a file or touch a provider before refusal.
        first = fn.body[0]
        assert isinstance(first, ast.Raise)
        assert isinstance(first.exc, ast.Call)
        assert isinstance(first.exc.func, ast.Name) and first.exc.func.id == "RuntimeError"
        assert len(first.exc.args) == 1
        assert isinstance(first.exc.args[0], ast.Constant) and first.exc.args[0].value == BLOCKED

        # Execute precisely the real function body in an isolated namespace
        # without importing a provider or the historical script module.
        isolated = ast.Module(
            body=[
                ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                fn,
            ],
            type_ignores=[],
        )
        ast.fix_missing_locations(isolated)
        namespace: dict[str, object] = {}
        exec(compile(isolated, filename=str(source), mode="exec"), namespace, namespace)
        arguments: tuple[object, ...] = (object(),) if name == "run" else ()
        with pytest.raises(RuntimeError, match="VK_WAVE6_RETIRED_IMPORT_BLOCKED"):
            dispatcher = namespace[name]
            assert callable(dispatcher)
            dispatcher(*arguments)


def test_retired_import_guards_preserve_exact_wave6_inventory_and_other_modules() -> None:
    registry = json.loads((ROOT / "scripts" / "wave-executors.json").read_text(encoding="utf-8"))
    rows = {item["path"]: item for item in registry["executors"]}
    assert len(RETIRED_ENTRYPOINTS) == 10

    for filename in RETIRED_ENTRYPOINTS:
        relative = f"scripts/{filename}"
        row = rows[relative]
        assert row["status"] == "retired"
        assert row["provider_write_capable"] is True
        raw = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        assert row["sha256"] == hashlib.sha256(raw).hexdigest()
