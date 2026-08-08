from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTABLE_LOCK = ROOT / "requirements/telegram-publisher.txt"
PRODUCTION_LOCK = ROOT / "requirements/telegram-publisher-ubuntu24-py311.txt"
WORKFLOWS = ROOT / ".github/workflows"

EXPECTED_PACKAGES = {
    "annotated-types==0.7.0",
    "anyio==4.13.0",
    "certifi==2026.5.20",
    "h11==0.16.0",
    "httpcore==1.0.9",
    "httpx==0.28.1",
    "idna==3.17",
    "pydantic==2.13.4",
    "pydantic-core==2.46.4",
    "typing-extensions==4.15.0",
    "typing-inspection==0.4.2",
}
PRODUCTION_PYDANTIC_CORE_HASH = "--hash=sha256:f9fa868638bf362d3d138ea55829cefb3d5f4b0d7f142234382a15e2485dbec4"


def _stanzas(text: str) -> list[str]:
    stanzas: list[str] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line == "--require-hashes":
            continue
        if not raw_line[:1].isspace():
            if current:
                stanzas.append(" ".join(current))
            current = [line.rstrip("\\").strip()]
        else:
            current.append(line.rstrip("\\").strip())
    if current:
        stanzas.append(" ".join(current))
    return stanzas


def test_production_telegram_runtime_is_fully_pinned_and_hash_checked() -> None:
    production = PRODUCTION_LOCK.read_text(encoding="utf-8")
    portable = PORTABLE_LOCK.read_text(encoding="utf-8")
    assert "--require-hashes" in {line.strip() for line in production.splitlines()}

    production_stanzas = _stanzas(production)
    portable_specs = {line.strip() for line in portable.splitlines() if line.strip()}
    production_specs = {stanza.split()[0] for stanza in production_stanzas}
    assert portable_specs == EXPECTED_PACKAGES
    assert production_specs == EXPECTED_PACKAGES
    assert len(production_stanzas) == len(EXPECTED_PACKAGES)
    for stanza in production_stanzas:
        assert "--hash=sha256:" in stanza, stanza.split()[0]
        assert " @ " not in stanza
        assert ">=" not in stanza
        assert "~=" not in stanza

    pydantic_core = next(stanza for stanza in production_stanzas if stanza.startswith("pydantic-core=="))
    assert PRODUCTION_PYDANTIC_CORE_HASH in pydantic_core


def test_every_workflow_uses_only_the_hashed_production_telegram_runtime() -> None:
    consumers: list[Path] = []
    for workflow in WORKFLOWS.glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        if "telegram-publisher" not in text:
            continue
        if "requirements/telegram-publisher-ubuntu24-py311.txt" in text:
            consumers.append(workflow)
            assert "--only-binary=:all:" in text, workflow.name
        assert "-r requirements/telegram-publisher.txt" not in text, workflow.name

    assert consumers, "no workflow consumes the hashed production Telegram runtime"
