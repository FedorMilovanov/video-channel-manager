"""Regression: agents must discover the right channel/surface YouTube contracts.
No owner credentials, network calls, model or provider mutations.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from video_channel_manager.editorial.youtube_copy import validate_youtube_description
from video_channel_manager.platforms.youtube.comments import validate_comment_text
from video_channel_manager.platforms.youtube.lord_god_presentation import presentation_issues

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/operations/lord-god-youtube-agent-decision-contract.md"
OWNER = "UCeSJsC6go2c9pdJCuUI1BYA"
FULL = "https://www.youtube.com/watch?v=k2Fh8aJfhOA"


@pytest.mark.parametrize(
    "location",
    [
        "AGENTS.md",
        "docs/operations/lord-god-strength-description-profile.md",
        "docs/operations/lord-god-youtube-description-wave.md",
        "docs/operations/shortorez-publication-routing.md",
        "docs/operations/shortorez-chat-workflow.md",
        "docs/youtube-comment-editorial-standard.md",
        "docs/editorial/platform-rendering-rules.md",
    ],
)
def test_lord_god_agent_rules_are_discoverable_from_all_entrypoints(location: str) -> None:
    text = (ROOT / location).read_text(encoding="utf-8")
    assert "lord-god-youtube-agent-decision-contract.md" in text


def test_lord_god_contract_has_current_owner_and_separate_surfaces() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert OWNER in text
    assert "lord-god-strength" in text
    assert "SHORTOREZ" in text
    assert "The Legendary Poet" in text
    assert "Related Video" in text
    assert "PINNED_STUDIO_CONFIRMED" in text
    assert "RIGHTS_APPROVED" in text
    assert "localizations" in text


def test_lord_god_short_description_example_validates_under_actual_code() -> None:
    doc = CONTRACT.read_text(encoding="utf-8")
    after_heading = doc.split("## Описание Short:", 1)[1]
    fence = chr(96) * 3
    example = after_heading.split(fence + "text\n", 1)[1].split("\n" + fence, 1)[0]
    substantive = [line for line in example.splitlines() if line.strip()]
    assert len(substantive) >= 9
    assert all("*" not in s and "_" not in s and "https://" not in s for s in substantive[:2])
    urls = re.findall(r"https?://\S+", example)
    assert urls[0] == FULL
    assert urls.index("https://gospod-bog.ru/") > urls.index(FULL)
    assert urls.index("https://t.me/lordchrist") > urls.index("https://gospod-bog.ru/")
    assert not presentation_issues(example)
    assert not [f for f in validate_youtube_description(example) if f.severity == "error"]


@pytest.mark.parametrize(
    ("incorrect", "correct"),
    [
        ("_греческий текст сохранился_, но", "_греческий текст сохранился,_ но"),
        ("_не оправдывать себя_, однако", "_не оправдывать себя,_ однако"),
        ("*27 января 1983 года*.", "*27 января 1983 года.*"),
        ("*Источник*: https://example.org", "*Источник:* https://example.org"),
    ],
)
def test_comment_example_punctuation_enforced_by_real_preflight(incorrect: str, correct: str) -> None:
    with pytest.raises(ValueError, match="emphasis punctuation"):
        validate_comment_text(incorrect)
    assert validate_comment_text(correct) == correct


def test_all_relative_links_in_decision_contract_resolve() -> None:
    doc = CONTRACT.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", doc)
    for link in links:
        if link.startswith(("http://", "https://", "#")):
            continue
        target = (CONTRACT.parent / link.split("#", 1)[0]).resolve()
        assert target.is_file(), f"Missing agent contract target: {link}"


def test_q02_delayed_locale_reconciliation_is_readonly_until_exact_verified() -> None:
    """Provider may return an older localization map immediately after a 200 PUT."""
    contract = CONTRACT.read_text(encoding="utf-8")
    runbook = (ROOT / "docs/operations/lord-god-youtube-description-wave.md").read_text(encoding="utf-8")
    for text in (contract, runbook):
        assert "HOLD_NO_RETRY" in text
        assert "VERIFIED_BY_RECONCILIATION" in text
        assert "part=localizations" in text
    assert "read-only owner GETs" in runbook
    assert "No second PUT was sent" in runbook
    assert "18 non-Russian translations" in runbook


def test_real_qna54_ai_disclosure_is_explicit_and_never_inherited() -> None:
    """Original MacArthur footage must not inherit an old 'AI: Yes' upload plan."""
    contract = CONTRACT.read_text(encoding="utf-8")
    assert "contains_synthetic_media=True" in contract
    assert "containsSyntheticMedia=false" in contract
    assert "prepare_six_private_youtube_uploads.py" in contract
    assert "stage_private_6_guarded.py" in contract
    assert "с обычным переводом" in contract
    assert "подписанные upload-планы" in contract
    assert "отсутствующего поля в owner GET" in contract
