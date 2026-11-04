"""The coverage ratchet is only worth having if it fails when coverage actually drops.

`docs/operations/coverage-ratchet.json` records a floor per module and one for the package total.
CI compares a fresh `coverage json` report against it through `scripts/coverage_ratchet.py`. These
tests exercise the checker on synthetic reports, so every failure mode is proven to produce a
non-zero exit and a message that names the module and both numbers, and they pin the two rules that
make the register a ratchet rather than a snapshot: a floor is never lowered, and a brand-new module
cannot be adopted below the new-module floor.

The structural test at the bottom keeps the register in step with the package: a renamed, added or
deleted module must touch the register in the same commit, and no floor may point at a file that no
longer exists.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts import coverage_ratchet as ratchet

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs/operations/coverage-ratchet.json"
PACKAGE = ROOT / "src/video_channel_manager"


def _report(modules: dict[str, float], total: float) -> dict[str, Any]:
    return {
        "files": {
            name: {"summary": {"num_statements": 100, "percent_covered": percent}} for name, percent in modules.items()
        },
        "totals": {"percent_covered": total},
    }


def _register(modules: dict[str, float], total: float) -> dict[str, Any]:
    return {
        "schema_name": ratchet.SCHEMA_NAME,
        "schema_version": ratchet.SCHEMA_VERSION,
        "updated_at_utc": "2026-10-22T00:00:00Z",
        "measured_python": "3.11",
        "command": "python -m pytest --cov=video_channel_manager --cov-report=json:coverage.json",
        "total_floor": total,
        "new_module_floor": ratchet.NEW_MODULE_FLOOR,
        "modules": modules,
    }


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(tmp_path: Path, report: dict[str, Any], register: dict[str, Any], *argv: str) -> int:
    return ratchet.main(
        [
            "--report",
            str(_write(tmp_path / "coverage.json", report)),
            "--register",
            str(_write(tmp_path / "register.json", register)),
            *argv,
        ]
    )


def test_a_report_at_the_recorded_floors_passes(tmp_path: Path) -> None:
    assert _run(tmp_path, _report({"a.py": 90.0}, 90.0), _register({"a.py": 90.0}, 90.0)) == 0


def test_a_module_below_its_floor_fails_and_names_both_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run(tmp_path, _report({"a.py": 72.5}, 72.5), _register({"a.py": 90.0}, 72.5))

    assert code == 1
    error = capsys.readouterr().err
    assert "a.py fell to 72.50% from the recorded floor 90.00%" in error


def test_the_total_floor_fails_independently_of_the_module_floors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run(tmp_path, _report({"a.py": 90.0}, 70.0), _register({"a.py": 90.0}, 75.0))

    assert code == 1
    assert "total coverage 70.00% is below the recorded floor 75.00%" in capsys.readouterr().err


def test_an_unregistered_module_is_a_failure_not_an_omission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run(tmp_path, _report({"a.py": 90.0, "new.py": 12.0}, 80.0), _register({"a.py": 90.0}, 80.0))

    assert code == 1
    error = capsys.readouterr().err
    assert "new.py has no recorded floor (measured 12.00%, 100 statements)" in error
    assert "--update" in error


def test_a_floor_for_a_vanished_module_is_stale(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = _run(tmp_path, _report({"a.py": 90.0}, 90.0), _register({"a.py": 90.0, "gone.py": 40.0}, 90.0))

    assert code == 1
    assert "gone.py is registered but missing from the coverage report" in capsys.readouterr().err


def test_tolerance_only_widens_the_check_never_the_register(tmp_path: Path) -> None:
    report = _report({"a.py": 89.5}, 89.5)
    register = _register({"a.py": 90.0}, 90.0)

    assert _run(tmp_path, report, register) == 1
    assert _run(tmp_path, report, register, "--tolerance", "0.5") == 0


def test_a_missing_report_is_a_check_error_not_a_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = ratchet.main(
        ["--report", str(tmp_path / "absent.json"), "--register", str(_write(tmp_path / "r.json", _register({}, 0.0)))]
    )

    assert code == 2
    assert "cannot read the coverage report" in capsys.readouterr().err


def test_update_raises_a_floor_that_improved(tmp_path: Path) -> None:
    register_path = _write(tmp_path / "register.json", _register({"a.py": 80.0}, 80.0))
    report_path = _write(tmp_path / "coverage.json", _report({"a.py": 91.4}, 91.4))

    code = ratchet.main(["--report", str(report_path), "--register", str(register_path), "--update"])

    assert code == 0
    updated = json.loads(register_path.read_text(encoding="utf-8"))
    assert updated["modules"] == {"a.py": 91.4}
    assert updated["total_floor"] == 91.4


def test_update_never_lowers_a_floor(tmp_path: Path) -> None:
    register_path = _write(tmp_path / "register.json", _register({"a.py": 95.0}, 95.0))
    report_path = _write(tmp_path / "coverage.json", _report({"a.py": 50.0}, 50.0))

    code = ratchet.main(["--report", str(report_path), "--register", str(register_path), "--update"])

    assert code == 0
    updated = json.loads(register_path.read_text(encoding="utf-8"))
    assert updated["modules"] == {"a.py": 95.0}
    assert updated["total_floor"] == 95.0


def test_update_refuses_to_adopt_a_new_module_below_the_new_module_floor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    register_path = _write(tmp_path / "register.json", _register({"a.py": 90.0}, 90.0))
    report_path = _write(tmp_path / "coverage.json", _report({"a.py": 90.0, "thin.py": 5.0}, 47.5))

    code = ratchet.main(["--report", str(report_path), "--register", str(register_path), "--update"])

    assert code == 1
    error = capsys.readouterr().err
    assert "thin.py is new and measures 5.00%" in error
    assert "register not written" in error
    assert json.loads(register_path.read_text(encoding="utf-8"))["modules"] == {"a.py": 90.0}


def test_update_refuses_to_keep_a_floor_for_a_deleted_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    register_path = _write(tmp_path / "register.json", _register({"a.py": 90.0, "gone.py": 20.0}, 90.0))
    report_path = _write(tmp_path / "coverage.json", _report({"a.py": 90.0}, 90.0))

    code = ratchet.main(["--report", str(report_path), "--register", str(register_path), "--update"])

    assert code == 1
    assert "gone.py is registered but no longer exists" in capsys.readouterr().err


def test_adopt_is_only_legal_on_an_empty_register(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    register_path = _write(tmp_path / "register.json", _register({"a.py": 90.0}, 90.0))
    report_path = _write(tmp_path / "coverage.json", _report({"a.py": 90.0}, 90.0))

    code = ratchet.main(["--report", str(report_path), "--register", str(register_path), "--update", "--adopt"])

    assert code == 2
    assert "--adopt is only legal while the register is empty" in capsys.readouterr().err


def test_adopt_seeds_an_empty_register_with_every_measurement(tmp_path: Path) -> None:
    register_path = _write(tmp_path / "register.json", _register({}, 0.0))
    report_path = _write(tmp_path / "coverage.json", _report({"a.py": 90.0, "thin.py": 12.0}, 60.0))

    code = ratchet.main(["--report", str(report_path), "--register", str(register_path), "--update", "--adopt"])

    assert code == 0
    updated = json.loads(register_path.read_text(encoding="utf-8"))
    assert updated["modules"] == {"a.py": 90.0, "thin.py": 12.0}
    assert updated["total_floor"] == 60.0


def test_floor_of_never_rounds_up() -> None:
    assert ratchet.floor_of(89.999) == 89.99
    assert ratchet.floor_of(100.0) == 100.0
    assert ratchet.floor_of(0.0) == 0.0


def test_build_register_stamps_the_measurement_and_sorts_modules() -> None:
    updated, raised, blocked = ratchet.build_register(
        {
            "b.py": ratchet.ModuleCoverage(statements=10, percent=70.0),
            "a.py": ratchet.ModuleCoverage(statements=10, percent=80.0),
        },
        _register({}, 0.0),
        total_percent=75.0,
        python_version="3.11",
        adopt=True,
        now=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
    )

    assert blocked == []
    assert list(updated["modules"]) == ["a.py", "b.py"]
    assert updated["updated_at_utc"] == "2026-10-22T12:00:00Z"
    assert updated["measured_python"] == "3.11"
    assert len(raised) == 3


def test_the_register_covers_exactly_the_package() -> None:
    register = ratchet.read_register(REGISTER)
    on_disk = {path.relative_to(ROOT).as_posix() for path in PACKAGE.rglob("*.py")}

    assert set(register["modules"]) == on_disk


def test_the_register_is_internally_consistent() -> None:
    register = ratchet.read_register(REGISTER)

    assert register["new_module_floor"] == ratchet.NEW_MODULE_FLOOR
    assert 0.0 <= register["total_floor"] <= 100.0
    for name, floor in register["modules"].items():
        assert isinstance(floor, float), name
        assert 0.0 <= floor <= 100.0, name
        assert floor == ratchet.floor_of(floor), f"{name} floor {floor} carries more than two decimals"
