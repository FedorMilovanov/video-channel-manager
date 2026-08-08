from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements/telegram-publisher.txt"
WORKFLOWS = ROOT / ".github/workflows"
LOCK_REFERENCE = "requirements/telegram-publisher.txt"

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


def test_minimal_telegram_runtime_is_fully_pinned_and_hash_checked() -> None:
    text = LOCK.read_text(encoding="utf-8")
    assert "--require-hashes" in {line.strip() for line in text.splitlines()}

    stanzas = _stanzas(text)
    package_specs = {stanza.split()[0] for stanza in stanzas}
    assert package_specs == EXPECTED_PACKAGES
    assert len(stanzas) == len(EXPECTED_PACKAGES)
    for stanza in stanzas:
        assert "--hash=sha256:" in stanza, stanza.split()[0]
        assert " @ " not in stanza
        assert ">=" not in stanza
        assert "~=" not in stanza

    pydantic_core = next(stanza for stanza in stanzas if stanza.startswith("pydantic-core=="))
    assert PRODUCTION_PYDANTIC_CORE_HASH in pydantic_core


def test_every_workflow_using_the_minimal_runtime_keeps_binary_only_install() -> None:
    consumers: list[Path] = []
    for workflow in WORKFLOWS.glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        if LOCK_REFERENCE in text:
            consumers.append(workflow)
            assert "--only-binary=:all:" in text, workflow.name

    assert consumers, "no workflow consumes the guarded Telegram publisher runtime"


def test_hash_locked_runtime_file_is_terminal_in_every_workflow_pip_transaction() -> None:
    consumers: list[Path] = []
    for workflow in WORKFLOWS.glob("*.yml"):
        lines = workflow.read_text(encoding="utf-8").splitlines()
        matching = [(index, line) for index, line in enumerate(lines) if LOCK_REFERENCE in line]
        if not matching:
            continue
        consumers.append(workflow)
        for index, line in matching:
            before, separator, after = line.partition(LOCK_REFERENCE)
            assert separator == LOCK_REFERENCE
            assert after.strip() == "", f"{workflow.name}:{index + 1} appends another requirement after the hash lock"
            assert not line.rstrip().endswith("\\"), (
                f"{workflow.name}:{index + 1} continues the pip transaction after the hash lock"
            )
            command_window = "\n".join(lines[max(0, index - 4) : index + 1])
            assert "pip install" in command_window, f"{workflow.name}:{index + 1} lock reference is not a pip install"
            assert "--only-binary=:all:" in command_window, (
                f"{workflow.name}:{index + 1} hash-locked install lost binary-only enforcement"
            )
            assert before.strip(), f"{workflow.name}:{index + 1} malformed hash-lock requirements line"

    assert consumers, "no workflow consumes the guarded Telegram publisher runtime"
