"""Fail CI when measured coverage drops below the recorded floor.

The repository measured 75% coverage and enforced none of it: `pytest --cov` printed a table that
nobody compared against anything, so any module could lose its tests and the build stayed green.
A single `--cov-fail-under` would only protect the total, and the total hides erosion: a new
untested module is offset by a well-tested one, and a 3,000-statement module can drop 20 points
while the total barely moves.

This checker therefore keeps two floors in `docs/operations/coverage-ratchet.json`:

* `total_floor` for the whole package;
* one floor per module, recorded at the precision of the measurement.

`--update` only ever raises a floor. It cannot lower one, and a module that is not registered yet
must arrive at or above `NEW_MODULE_FLOOR`; anything thinner has to be written into the register by
hand, so an exception is visible in review instead of being absorbed by a regeneration.

Usage:

    python scripts/coverage_ratchet.py                       # check coverage.json
    python scripts/coverage_ratchet.py --update              # record the current floors

The register is generated from one interpreter on purpose: statement counts and branch margins are
stable within a Python version but not guaranteed identical across them, and CI enforces the gate
on the version recorded in the register (`measured_python`).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_NAME = "video-channel-manager.coverage-ratchet"
SCHEMA_VERSION = 1
REGISTER_PATH = Path("docs/operations/coverage-ratchet.json")
REPORT_PATH = Path("coverage.json")
NEW_MODULE_FLOOR = 60.0


class RatchetError(Exception):
    """A register or report that cannot be interpreted is a failure, not a skipped check."""


@dataclass(frozen=True)
class ModuleCoverage:
    statements: int
    percent: float


@dataclass(frozen=True)
class CoverageReport:
    modules: dict[str, ModuleCoverage]
    total_percent: float


def _percent(value: Any, *, where: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise RatchetError(f"{where}: coverage must be numeric, got {value!r}")
    percent = float(value)
    if not 0.0 <= percent <= 100.0:
        raise RatchetError(f"{where}: coverage {percent} is outside 0..100")
    return percent


def floor_of(percent: float) -> float:
    """Truncate to two decimals: a floor must never round up past what was measured."""

    return math.floor(round(percent * 100, 9)) / 100


def read_report(path: Path = REPORT_PATH) -> CoverageReport:
    """Parse a `coverage json` report into per-module summaries and the total."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RatchetError(
            f"cannot read the coverage report {path}: {exc}. Run "
            "`python -m pytest --cov=video_channel_manager --cov-report=json:coverage.json` first."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RatchetError(f"coverage report {path} is not valid JSON: {exc}") from exc

    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise RatchetError(f"coverage report {path} has no per-file data")
    modules: dict[str, ModuleCoverage] = {}
    for name, data in files.items():
        summary = data.get("summary") if isinstance(data, dict) else None
        if not isinstance(summary, dict):
            raise RatchetError(f"coverage report {path} has no summary for {name}")
        modules[Path(name).as_posix()] = ModuleCoverage(
            statements=int(summary.get("num_statements", 0)),
            percent=_percent(summary.get("percent_covered"), where=f"{path}:{name}"),
        )

    totals = payload.get("totals")
    if not isinstance(totals, dict):
        raise RatchetError(f"coverage report {path} has no totals section")
    return CoverageReport(
        modules=modules,
        total_percent=_percent(totals.get("percent_covered"), where=f"{path}:totals"),
    )


def read_register(path: Path = REGISTER_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RatchetError(f"cannot read the coverage ratchet register {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RatchetError(f"coverage ratchet register {path} is not valid JSON: {exc}") from exc

    if payload.get("schema_name") != SCHEMA_NAME:
        raise RatchetError(f"{path}: expected schema_name {SCHEMA_NAME!r}, got {payload.get('schema_name')!r}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise RatchetError(f"{path}: expected schema_version {SCHEMA_VERSION}, got {payload.get('schema_version')!r}")
    modules = payload.get("modules")
    if not isinstance(modules, dict):
        raise RatchetError(f"{path}: the register has no `modules` mapping")
    for name, floor in modules.items():
        _percent(floor, where=f"{path}:{name}")
    payload["total_floor"] = _percent(payload.get("total_floor"), where=f"{path}:total_floor")
    return payload


def evaluate(
    modules: dict[str, ModuleCoverage],
    register: dict[str, Any],
    *,
    total_percent: float,
    tolerance: float = 0.0,
) -> list[str]:
    """Return every violation of the recorded floors, in a stable order."""

    floors: dict[str, float] = {name: float(floor) for name, floor in register["modules"].items()}
    violations: list[str] = []

    total_floor = float(register["total_floor"])
    if total_percent + tolerance < total_floor:
        violations.append(f"total coverage {total_percent:.2f}% is below the recorded floor {total_floor:.2f}%")

    for name in sorted(set(floors) - set(modules)):
        violations.append(f"{name} is registered but missing from the coverage report (stale floor)")
    for name in sorted(set(modules) - set(floors)):
        measured = modules[name].percent
        violations.append(
            f"{name} has no recorded floor (measured {measured:.2f}%, {modules[name].statements} statements); "
            "run `python scripts/coverage_ratchet.py --update` once the module has tests"
        )
    for name in sorted(set(floors) & set(modules)):
        measured = modules[name].percent
        floor = floors[name]
        if measured + tolerance < floor:
            violations.append(
                f"{name} fell to {measured:.2f}% from the recorded floor {floor:.2f}% "
                f"({modules[name].statements} statements)"
            )
    return violations


def build_register(
    modules: dict[str, ModuleCoverage],
    register: dict[str, Any],
    *,
    total_percent: float,
    python_version: str,
    adopt: bool = False,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Raise floors to the measurement; never lower one.

    Returns the new register, the raised entries and the floor violations that block an update.
    """

    floors: dict[str, float] = {name: float(floor) for name, floor in register["modules"].items()}
    raised: list[str] = []
    blocked: list[str] = []

    for name, coverage in modules.items():
        measured = floor_of(coverage.percent)
        if name not in floors:
            if coverage.percent < NEW_MODULE_FLOOR and not adopt:
                blocked.append(
                    f"{name} is new and measures {coverage.percent:.2f}% "
                    f"({coverage.statements} statements), below the {NEW_MODULE_FLOOR:.0f}% new-module floor"
                )
                continue
            floors[name] = measured
            raised.append(f"{name}: new floor {measured:.2f}%")
            continue
        if measured > floors[name]:
            raised.append(f"{name}: {floors[name]:.2f}% -> {measured:.2f}%")
            floors[name] = measured

    for name in sorted(set(floors) - set(modules)):
        blocked.append(f"{name} is registered but no longer exists in the coverage report")

    total_floor = max(float(register["total_floor"]), floor_of(total_percent))
    if total_floor > float(register["total_floor"]):
        raised.append(f"total: {float(register['total_floor']):.2f}% -> {total_floor:.2f}%")

    stamp = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    updated = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "updated_at_utc": stamp,
        "measured_python": python_version,
        "command": "python -m pytest --cov=video_channel_manager --cov-report=json:coverage.json",
        "total_floor": total_floor,
        "new_module_floor": NEW_MODULE_FLOOR,
        "modules": {name: floors[name] for name in sorted(floors)},
    }
    return updated, raised, blocked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--register", type=Path, default=REGISTER_PATH)
    parser.add_argument("--update", action="store_true", help="raise floors to the current measurement")
    parser.add_argument(
        "--adopt",
        action="store_true",
        help="with --update on an empty register: record the current tree, including thin modules, once",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        help="percentage points of slack when checking (0 keeps the ratchet exact)",
    )
    args = parser.parse_args(argv)

    try:
        report = read_report(args.report)
        register = read_register(args.register)
    except RatchetError as exc:
        print(f"coverage ratchet: {exc}", file=sys.stderr)
        return 2
    modules = report.modules
    total_percent = report.total_percent

    if not args.update:
        violations = evaluate(modules, register, total_percent=total_percent, tolerance=args.tolerance)
        for violation in violations:
            print(f"coverage ratchet: {violation}", file=sys.stderr)
        if violations:
            return 1
        print(
            f"coverage ratchet: {len(modules)} modules at or above their recorded floors (total {total_percent:.2f}%)"
        )
        return 0

    if args.adopt and register["modules"]:
        print(
            "coverage ratchet: --adopt is only legal while the register is empty; "
            "use --update to raise existing floors",
            file=sys.stderr,
        )
        return 2

    updated, raised, blocked = build_register(
        modules,
        register,
        total_percent=total_percent,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        adopt=args.adopt,
    )
    for message in raised:
        print(f"coverage ratchet: raised {message}")
    if blocked:
        for message in blocked:
            print(f"coverage ratchet: {message}", file=sys.stderr)
        print("coverage ratchet: register not written", file=sys.stderr)
        return 1
    args.register.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"coverage ratchet: wrote {len(updated['modules'])} floors to {args.register} (total {updated['total_floor']:.2f}%)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
