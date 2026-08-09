from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_A = ROOT / "src" / "video_channel_manager" / "wave_engine" / "package_a.py"
MP3_CONTRACT = ROOT / "docs" / "operations" / "mp3-batch-processing-contract.md"


def test_ci_uses_exact_node24_action_releases() -> None:
    text = CI.read_text(encoding="utf-8")

    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1" in text
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1" in text
    for retired in (
        "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
        "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ):
        assert retired not in text


def test_unclosed_sqlite_connections_are_blocking_and_production_closes_them() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    package_a = PACKAGE_A.read_text(encoding="utf-8")

    assert '"error:unclosed database.*:ResourceWarning"' in pyproject
    assert "from contextlib import closing" in package_a
    assert "with closing(sqlite3.connect(uri, uri=True)) as connection:" in package_a
    assert "with sqlite3.connect(uri, uri=True) as connection:" not in package_a


def test_mp3_contract_records_fail_closed_identity_rules() -> None:
    text = MP3_CONTRACT.read_text(encoding="utf-8")

    for phrase in (
        "schema_version`: `1.1`",
        "source_id_sha256_conflict",
        "sha256_multiple_source_ids",
        "explicit exact metadata wins canonical selection",
        "1,000 ready tracks",
        "40 deterministic chunks of 25",
    ):
        assert phrase in text
