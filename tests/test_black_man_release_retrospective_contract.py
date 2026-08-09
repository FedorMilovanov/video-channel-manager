from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_black_man_live_state_is_non_authorizing_and_blocks_forgetful_reupload() -> None:
    payload = json.loads(
        (ROOT / "docs/operations/black-man-youtube-live-state-2026-08-09.json").read_text(encoding="utf-8")
    )

    assert payload["project_key"] == "legendary-poet"
    assert payload["channel_id"] == "UC-78ys2S3cQ3lpqgXfo-SvQ"
    assert payload["video"]["video_id"] == "x-puy27S2qs"
    assert payload["video"]["privacy_status"] == "public"
    assert payload["video"]["uploaded_media_sha256"] == (
        "sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0"
    )
    assert payload["video"]["custom_thumbnail"]["verified_present"] is True
    assert payload["completion"]["provider_rollout_historical_media"] == "verified_public"
    assert payload["completion"]["current_policy_artifact_completion"] == "not_proven_issue_154_open"
    assert payload["execution_authority"] is False
    assert payload["provider_writes_authorized"] is False


def test_superseded_black_man_youtube_branches_are_retired() -> None:
    registry = json.loads((ROOT / "docs/operations/retirement-registry-v1.json").read_text(encoding="utf-8"))
    retired = {item["id"]: item for item in registry["retired_families"]}

    for identifier in ("black-man-youtube-upload-pr171", "youtube-copy-apply-pr197"):
        assert retired[identifier]["execution_prohibited"] is True
        assert retired[identifier]["status"] == "retired_non_executable"


def test_windows_handoff_assumes_normal_whole_block_copy_paste() -> None:
    copilot = (ROOT / ".github/copilot-instructions.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs/operations/operator-output-handoff-rule.md").read_text(encoding="utf-8")

    assert "Ctrl+C → Ctrl+V on the entire shown command block" in copilot
    assert "one executable fenced block" in copilot
    assert "Do not put long YouTube descriptions" in copilot
    assert "`\\_` or `\\:`" in copilot
    assert "deliver an exact `.ps1` file artifact" in copilot
    assert "current-`main` repository-owned entrypoint" in copilot
    assert "Do not embed `googleapis.com`" in copilot

    assert "Ctrl+C → Ctrl+V of the entire executable block" in handoff
    assert "one operator action gets at most one executable fenced block" in handoff
    assert "literal `\\_` or `\\:`" in handoff
    assert "must not become a second provider client" in handoff
    assert "classify the effect as `may_exist`" in handoff


def test_stable_upload_guard_names_known_public_target_and_semantic_repairs() -> None:
    text = (ROOT / "docs/operations/youtube-upload-stable-key-guard.md").read_text(encoding="utf-8")

    assert "has provider target `x-puy27S2qs`" in text
    assert "verified public at the end of the 2026-08-09 release session" in text
    assert "Existing remote target adoption/reconciliation" in text
    assert "multiplicity preserved" in text
    assert "an omitted key is `unobserved`, not `false`" in text
    assert "accepted provider mutation plus one empty/non-converged read is `may_exist`" in text
    assert "There is no provider `execute` command in this baseline." in text


def test_public_readme_does_not_hide_active_youtube_implementation_scope() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "единственный активный owning issue #154" not in readme
    assert "Текущий repository-level backlog закрыт" not in readme
    assert "Issue #154" in readme
    assert "Issue #232" in readme
    assert "x-puy27S2qs" in readme
    assert "не разрешает повторный upload" in readme
