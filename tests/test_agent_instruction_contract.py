from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_root_agent_contract_stays_concise_and_nonvolatile() -> None:
    text = _text("AGENTS.md")

    assert len(text.splitlines()) <= 180
    assert "docs/operations/current-state.md" in text
    assert "docs/operations/project-identity-registry.md" in text
    assert "docs/operations/operational-artifact-standard.md" in text
    assert ".github/copilot-instructions.md" in text
    assert "completed Resi/DASH `<TITLE> - FULL.mp4` master goes to `C:\\Users\\Fedor\\Downloads`" in text

    for stale_pattern in (
        "Current production code baseline:",
        "Historical Wave",
        "No operational continuation is pending",
        "main@",
    ):
        assert stale_pattern not in text

    for invariant in (
        "Durable same-object keys must not include timestamps",
        "Release/content approval and provider execution authority are separate gates",
        "zero blind mutation retries",
        "A final artifact must consume the exact accepted upstream artifacts it claims",
        "one write owner at a time",
        "`main` is the only supported repository code/runtime execution baseline",
        "`state/lordchrist-telegram` and `state/svodka-telegram` are durable state-only refs",
        "align it to exact current `main`",
        "repository implementation complete",
        "artifact complete",
        "provider rollout complete",
    ):
        assert invariant in text


def test_current_state_is_a_live_index_not_a_commit_ledger() -> None:
    text = _text("docs/operations/current-state.md")

    assert len(text.splitlines()) <= 180
    assert "main@" not in text
    assert "Issue #154 is closed as **completed**" in text
    assert "Issue #154 remains **artifact-level open**" not in text
    assert "not required rework" in text
    assert "Do not regenerate or reupload the album solely" in text
    assert "A completed artifact/provider outcome is not retroactively reopened" in text
    assert "Issue #168 is closed as repository implementation complete" in text
    assert "Issue #170 is closed as repository pipeline implementation complete" in text
    assert "provider_writes_authorized=false" in text
    assert "`provider_writes_authorized=true` only for the reviewed rollout gates" in text
    assert "release `svodka-pilot-2026-08`" in text
    assert "the durable ledger now exists on `state/svodka-telegram`" in text
    assert "no approved live August release is present" not in text
    assert "no live Svodka publication ledger is present" not in text
    assert not (ROOT / "docs/operations/svodka-rollout-status.json").exists()
    assert "current `main` includes the guarded YouTube release executor" in text
    assert "implementation completion does not itself authorize execution" in text
    assert "historical research-v2 canary ambiguity is no longer a legacy blocker" in text
    assert "Issue #286 / PR #287" in text
    assert "`retired_no_replay`" in text
    assert "every other `dispatching` or `may_exist` effect remains fail-closed" in text
    assert "the retired August research release itself cannot resume, retry, or authorize a successor" in text
    assert "Only `main` is a supported repository code/runtime execution baseline" in text
    assert "`state/lordchrist-telegram` and `state/svodka-telegram` are durable state-only refs" in text
    assert "`protected=false`" in text
    assert "repository ruleset count `0`" in text
    assert "Dependency Graph itself is policy-enabled for this public repository" in text
    assert "SBOM REST export is verified unavailable through both documented generation surfaces" in text
    assert "blanket `UNVERIFIED` item" in text
    assert "retained `<TITLE> - FULL.mp4` master goes to canonical Windows Downloads" in text
    assert (
        "generated handoff/watcher control files and exact-trim outputs remain under repository `operator-output`"
        in text
    )


def test_dependabot_maintenance_is_atomic_and_bounded() -> None:
    text = _text(".github/dependabot.yml")

    for policy in (
        "routine-minor-patch:",
        "workflow-actions:",
        "applies-to: version-updates",
        'dependency-name: "*"',
        "version-update:semver-major",
        "dependency-name: pydantic-core",
        "dependency-name: httpx",
    ):
        assert policy in text

    assert text.count("groups:") == 2
    assert "routine-minor-patch:" in text and "- minor" in text and "- patch" in text
    assert "workflow-actions:" in text and "- major" in text
    assert "dependency-name: mypy" not in text


def test_telegram_runtime_lock_has_explicit_roots_and_atomic_contract() -> None:
    roots = _text("requirements/telegram-publisher.in")
    lock = _text("requirements/telegram-publisher.txt")

    assert "httpx==0.28.1" in roots
    assert "pydantic==2.13.4" in roots
    assert "transitive line in the hash lock independently" in roots
    assert "Root constraints live in requirements/telegram-publisher.in" in lock
    assert "never update a transitive" in lock
    assert "--require-hashes" in lock


def test_windows_copilot_file_only_adds_handoff_rules() -> None:
    text = _text(".github/copilot-instructions.md")

    assert len(text.splitlines()) <= 130
    assert "`AGENTS.md` is the repository operating contract" in text
    assert "C:\\Users\\Fedor\\Projects\\video-channel-manager\\operator-output" in text
    assert "C:\\Users\\Fedor\\Downloads" in text
    assert "Resi/DASH has one explicit split-destination exception" in text
    assert "LastWriteTime" in text
    assert "Historical Wave" not in text
    assert "Current production code baseline" not in text


def test_agent_contract_references_exist() -> None:
    for relative in (
        "docs/operations/current-state.md",
        "docs/operations/project-identity-registry.md",
        "docs/operations/operational-artifact-standard.md",
        "docs/operations/operational-package-acceptance.md",
        "docs/operations/retirement-registry-v1.json",
        "docs/operations/operator-output-handoff-rule.md",
        ".github/copilot-instructions.md",
    ):
        assert (ROOT / relative).is_file(), relative
