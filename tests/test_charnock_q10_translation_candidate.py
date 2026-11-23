"""Fail-closed proof that Charnock №11 q-10 remains an isolated research candidate."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-11.json"
BASE = ROOT / "content/research/charnock-source-credit-candidates-20261123/charnock-11.json"
PROPOSAL = ROOT / "content/research/charnock-q10-translation-review-20261123/charnock-11-q10-proposed.json"

APPROVED_SHA = "d42392bb593de4f89d36a12a3548f459efe41090"
BASE_SHA = "9f6bf6403d852723ec240e1839239652e44b4012"
PROPOSED_REVISION = "charnock-11-q10-translation-proposal-20261123"


def _working_tree_git_blob_sha(path: Path) -> str:
    """Hash checkout bytes through Git's normal clean filters.

    The Git object stays LF even if Windows core.autocrlf checks it out as
    CRLF. The filtered working-tree hash still catches content mutations,
    unlike looking only at the stored HEAD blob identity.
    """
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "hash-object", f"--path={relative}", "--", relative],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _q10(article: dict) -> dict:
    blocks = [item for item in article["blocks"] if item.get("block_id") == "q-10"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "blockquote"
    return blocks[0]


def test_baseline_and_approved_sources_remain_immutable() -> None:
    assert _working_tree_git_blob_sha(ARTICLE) == APPROVED_SHA
    assert _working_tree_git_blob_sha(BASE) == BASE_SHA


def test_proposed_translation_changes_only_plain_span_and_revision() -> None:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    proposed = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    old_q = _q10(base)
    new_q = _q10(proposed)
    before = old_q["blocks"][0]["text"]
    after = new_q["blocks"][0]["text"]
    assert isinstance(before, list) and len(before) == 3
    assert isinstance(after, list) and len(after) == 3
    assert "странное расстройство у некоторых имений" in before[0]
    assert "неожиданные неудачи в имущественных делах" in after[0]
    assert "словно действуют по разумному замыслу" in after[0]
    assert "замысел человеческого сохранения" not in after[0]
    assert before[1:] == after[1:]
    assert old_q["credit"] == new_q["credit"]

    expected = copy.deepcopy(base)
    expected["revision"] = PROPOSED_REVISION
    _q10(expected)["blocks"][0]["text"][0] = after[0]
    assert proposed == expected
    assert proposed["blocks"][-1] == base["blocks"][-1]
    assert proposed["document_id"] == "lordchrist-telegraph-charnock-11"


def test_proposed_q10_translation_retains_unique_top_level_block_ids() -> None:
    """Translation work may change one quotation span, never collide with the bibliography anchor."""
    base = json.loads(BASE.read_text(encoding="utf-8"))
    proposed = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    for document in (base, proposed):
        ids = [block["block_id"] for block in document["blocks"]]
        assert len(ids) == len(set(ids)), ids
    assert base["blocks"][-1]["block_id"] == proposed["blocks"][-1]["block_id"] == "p-27"
