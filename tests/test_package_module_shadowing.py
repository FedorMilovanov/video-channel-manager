from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "video_channel_manager"


def test_no_module_is_shadowed_by_a_same_named_package() -> None:
    """A module and a package with one name silently resolve to a single winner.

    ``video_channel_manager/platforms/vk.py`` used to sit next to
    ``video_channel_manager/platforms/vk/``. Every import resolved to the
    package, so the module was unreachable code that still appeared in coverage
    and type-checking reports. Such a pair is always a defect.
    """

    shadowed: list[str] = []

    for module in PACKAGE_ROOT.rglob("*.py"):
        if module.name == "__init__.py":
            continue
        candidate = module.with_suffix("")
        if candidate.is_dir() and (candidate / "__init__.py").is_file():
            shadowed.append(str(module.relative_to(ROOT)))

    assert shadowed == []
