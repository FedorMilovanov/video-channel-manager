"""The completed Charnock QC operation stays owner-only and read-only."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-charnock-qc-reissue.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_manual_single_page_read_only_dispatch() -> None:
    text = _source()
    assert "workflow_dispatch:" in text
    for event in ("schedule:", "push:", "pull_request:", "repository_dispatch:"):
        assert event not in text
    for page in ("'01b'", "'02'", "'07'", "'13'"):
        assert page in text
    assert "default: dry-run" in text
    assert "          - reconcile" in text
    assert "          - structural-reconcile" in text
    assert "          - execute" not in text
    assert '"$MODE" == "execute"' not in text
    assert '"$MODE" == "reconcile"' in text
    assert '"$MODE" == "structural-reconcile"' in text
    assert "default: current-main" in text
    assert "historical-qc-20261121" in text
    assert 'media_revision="c1bafa972e91d536fc56d86e53b4ce6f3502f37d"' in text
    assert "run-name: charnock-qc-readonly-" in text


def test_owner_main_and_exact_head_gate_are_preserved() -> None:
    text = _source()
    assert "github.actor == 'FedorMilovanov'" in text
    assert "github.repository == 'FedorMilovanov/video-channel-manager'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert '"$GITHUB_RUN_ATTEMPT" == "1"' in text
    assert 'gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha' in text


def test_no_edit_secrets_provider_mutation_or_write_permissions() -> None:
    text = _source()
    for forbidden in (
        "LORDCHRIST_TELEGRAPH_ACCESS_TOKEN",
        "LORDCHRIST_TELEGRAM_BOT_TOKEN",
        "sendMessage",
        "createPage",
        "editPage",
        "--execute",
        "--confirm",
        "contents: write",
        "actions: write",
    ):
        assert forbidden not in text
    assert "cancel-in-progress: false" in text
    assert "persist-credentials: false" in text
    assert "contents: read" in text


def test_retirement_registry_prohibits_only_the_consumed_edit_mode() -> None:
    registry = json.loads((ROOT / "docs/operations/retirement-registry-v1.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in registry["retired_families"]}
    retired = entries["lordchrist-charnock-qc-page-edit-20261121"]
    assert retired["kind"] == "repository_provider_mutation_mode"
    assert retired["status"] == "retired_non_executable"
    assert retired["execution_prohibited"] is True
    assert retired["issues"] == [997]
    assert "read-only comparison only" in retired["replacement"]
    assert "old SHAs and external copies are not stopped" in retired["reason"]
    assert registry["provider_writes_authorized"] is False


def test_one_read_only_receipt_uploaded_even_when_comparison_fails() -> None:
    text = _source()
    assert "python -m scripts.charnock_telegraph_qc_reissue" in text
    assert "--reconcile" in text
    assert "--media-base-url" in text
    assert "--receipt-dir" in text
    assert "set -euo pipefail" in text
    assert 'if [[ "$MODE" == "reconcile" ]]' in text
    assert 'elif [[ "$MODE" == "structural-reconcile" ]]' in text
    assert "--require-normalized-tree" in text
    assert "if ! python -m scripts.charnock_telegraph_qc_reissue" in text
    assert "from scripts.charnock_telegraph_qc_reissue import annotation_summary" in text
    assert text.count("emit_comparison_summary") == 3  # declaration, mismatch, success
    assert "find" in text and "wc -l" in text and "-eq 1" in text
    assert "if: always() && (inputs.mode == 'reconcile' || inputs.mode == 'structural-reconcile')" in text
    assert "actions/upload-artifact" in text
    assert "charnock-qc-readonly-result-${REVIEWED_PAGE}" in text
    assert "charnock-qc-reissue-receipt-${{ inputs.page }}" in text


@pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None, reason="workflow runs on a Linux bash runner")
@pytest.mark.parametrize(
    ("script_status", "effect", "expected_status"),
    [(0, "NORMALIZED_NODE_TREE_MATCH", 0), (2, "NORMALIZED_NODE_TREE_MISMATCH", 3)],
)
def test_workflow_emits_a_compact_summary_on_match_and_mismatch(
    tmp_path: Path, script_status: int, effect: str, expected_status: int
) -> None:
    workflow = yaml.safe_load(_source())
    steps = workflow["jobs"]["compare"]["steps"]
    script = next(step["run"] for step in steps if step["name"] == "Compare the public page without provider writes")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    runner = tmp_path / "runner"
    runner.mkdir()
    python_stub = bin_dir / "python"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "-m" ]]; then\n'
        '  printf "%s\\n" "$@" > "$RUNNER_TEMP/invocation.txt"\n'
        '  printf "%s\\n" "$FAKE_OUTCOME"\n'
        '  : > "$RUNNER_TEMP/charnock-qc-reissue-receipts/receipt.json"\n'
        '  exit "$FAKE_STATUS"\n'
        "fi\n"
        'exec "$REAL_PYTHON" "$@"\n',
        encoding="utf-8",
    )
    python_stub.chmod(0o755)
    outcome = {
        "article": "10",
        "effect": effect,
        "provider_write_attempted": False,
        "live_first_text": "DO_NOT_COPY_PAGE_TEXT",
        "normalized_tree_sha256_before": "a" * 64,
        "normalized_tree_sha256_after": "b" * 64,
        "verification": {"normalized_node_tree_equal": script_status == 0, "normalized_node_tree_required": True},
    }
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "src"))),
        "REAL_PYTHON": sys.executable,
        "RUNNER_TEMP": str(runner),
        "FAKE_OUTCOME": json.dumps(outcome),
        "FAKE_STATUS": str(script_status),
        "GITHUB_REPOSITORY": "FedorMilovanov/video-channel-manager",
        "GITHUB_SHA": "a" * 40,
        "REVIEWED_PAGE": "10",
        "MEDIA_BASE": "historical-qc-20261121",
        "MODE": "structural-reconcile",
    }
    result = subprocess.run(["bash", "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == expected_status, result.stdout + result.stderr
    prefix = "::notice title=charnock-qc-readonly-result-10::"
    summary_line = next(line.removeprefix(prefix) for line in result.stdout.splitlines() if line.startswith(prefix))
    summary = json.loads(summary_line)
    assert summary["effect"] == effect
    assert summary["verification"]["normalized_node_tree_required"] is True
    assert "DO_NOT_COPY_PAGE_TEXT" not in summary_line
    invocation = (runner / "invocation.txt").read_text(encoding="utf-8").splitlines()
    assert "--require-normalized-tree" in invocation and "--reconcile" in invocation
    assert any("c1bafa972e91d536fc56d86e53b4ce6f3502f37d" in item for item in invocation)
    assert len(list((runner / "charnock-qc-reissue-receipts").glob("*.json"))) == 1
