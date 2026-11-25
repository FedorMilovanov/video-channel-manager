"""Provider-inert quote-v6 candidate checks with immutable 30-card source proofs."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import scripts.lordchrist_quote_v6_release_candidate as candidate

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_FILE = ROOT / candidate.DEFAULT_OUT
READER_FILE = ROOT / candidate.READER_FILE


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exact_provider_candidate_is_reproducible_without_provider_calls() -> None:
    regenerated = candidate.build_candidate(ROOT)
    frozen = _json(CANDIDATE_FILE)
    assert regenerated == frozen
    assert regenerated["schema_name"] == "video-channel-manager.lordchrist-quote-v6-payload-candidate-inert"
    assert regenerated["project_key"] == "lord-god-strength"
    assert regenerated["channel_username"] == "@lordchrist"
    assert len(regenerated["items"]) == 30
    assert [p["sequence"] for p in regenerated["items"]] == list(range(1, 31))
    assert len({p["publication_id"] for p in regenerated["items"]}) == 30
    assert regenerated["candidate_digest"].startswith("sha256:")
    assert regenerated["new_release_digest"] is None
    assert regenerated["live_schedule_enabled"] is False
    assert regenerated["approved_new_queue"] is False
    assert regenerated["rights_review_complete"] is False
    assert regenerated["full_bilingual_review_complete"] is False
    assert regenerated["responsible_editor_approval"] is False
    assert regenerated["provider_write_authorization"] is False
    assert regenerated["historical_v4_replay_authorized"] is False
    assert regenerated["read_only"] is True
    assert len(regenerated["pending_prerequisites"]) >= 5


def test_each_provider_html_is_exact_source_bound_and_within_telegram_limit() -> None:
    frozen = _json(CANDIDATE_FILE)
    reader = _json(READER_FILE)
    for post, original in zip(frozen["items"], reader["posts"], strict=True):
        assert post["publication_id"] == original["publication_id"]
        assert post["html_text"] == original["reader_html_preview"]
        assert post["quoted_russian_sha256"] == original["quote_sha256"]
        assert post["source_render_html_sha256"] == original["candidate_render_html_sha256"]
        assert post["historical_english_span_sha256"] == original["historical_english_span_sha256"]
        assert post["source_anchors"] == {
            "start": original["source_anchor_start"],
            "end": original["source_anchor_end"],
        }
        assert post["parse_mode"] == "HTML"
        assert post["link_preview_disabled"] is True
        assert post["candidate_payload_sha256"].startswith("sha256:")
        assert post["rights_review_complete"] is False
        assert post["responsible_editor_approval"] is False
        assert post["provider_write_authorization"] is False
        visible, actual_units = candidate.validate_provider_html(
            post["html_text"], expected_attribution=original["reader_attribution"]
        )
        assert post["visible_utf16_units"] == actual_units
        assert 0 < actual_units <= 4096
        assert "Примечание редакции:" not in visible
        assert "Контекст:" not in visible
    assert frozen["first_canary_candidate"]["publication_id"] == frozen["items"][0]["publication_id"]
    assert frozen["first_canary_candidate"]["provider_write_authorization"] is False


@pytest.mark.parametrize(
    ("invalid", "expected"),
    [
        ("<script>alert(1)</script>", "unexpected"),
        ("<blockquote>«Text»<i>nested</i></blockquote>", "unexpected"),
        ("<blockquote>«Text»</blockquote><blockquote>«Double»</blockquote>", "unexpected"),
        ("<blockquote>«Text»</blockquote><i>— Author</i><i>dup</i>", "unexpected"),
        ("<blockquote>«Text»</blockquote><i>— Author</i>", "spacing"),
        ("<blockquote>«Text»</blockquote><i>— Author", "complete"),
    ],
)
def test_unreviewed_html_or_loss_of_attribution_fails_closed(invalid: str, expected: str) -> None:
    with pytest.raises(ValueError):
        candidate.validate_provider_html(invalid, expected_attribution="— Author")


def test_changed_source_render_is_rejected_not_rehashed_silently(monkeypatch: pytest.MonkeyPatch) -> None:
    original_loader = candidate._load
    modified = copy.deepcopy(_json(READER_FILE))
    modified["posts"][0]["reader_html_preview"] = modified["posts"][0]["reader_html_preview"].replace(
        "Я охотно", "Я вольно", 1
    )

    def injected_loader(root: Path, relative: Path) -> dict:
        if relative == candidate.READER_FILE:
            return modified
        return original_loader(root, relative)

    monkeypatch.setattr(candidate, "_load", injected_loader)
    with pytest.raises(ValueError, match="provider HTML changed"):
        candidate.build_candidate(ROOT)


def test_modifying_authorization_or_publication_id_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original_loader = candidate._load
    for mutator in (
        lambda obj: obj.__setitem__("provider_write_authorization", True),
        lambda obj: obj["posts"][0].__setitem__("publication_id", "lordchrist-unreviewed-duplicate"),
        lambda obj: obj["posts"][0].__setitem__("quote_sha256", "sha256:" + "0" * 64),
    ):
        modified = copy.deepcopy(_json(READER_FILE))
        mutator(modified)

        def injected_loader(root: Path, relative: Path, *, _record: dict = modified) -> dict:
            if relative == candidate.READER_FILE:
                return _record
            return original_loader(root, relative)

        monkeypatch.setattr(candidate, "_load", injected_loader)
        with pytest.raises(ValueError):
            candidate.build_candidate(ROOT)


def test_candidate_does_not_activate_legacy_pending_queue() -> None:
    frozen = _json(CANDIDATE_FILE)
    assert "state_ledger" not in frozen
    assert "workflow" not in frozen
    assert "scheduled_at" not in frozen
    assert "dispatch" not in frozen
    assert frozen["historical_v4_replay_authorized"] is False
    assert frozen["live_schedule_enabled"] is False
    assert all("state" not in p for p in frozen["items"])
    assert all("message_id" not in p for p in frozen["items"])
