"""Offline native-provider compatibility proof for all 30 quote-v6 cards."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import lordchrist_quote_v6_native_readonly as native
from video_channel_manager.telegram_presentation import _RenderBuilder
from video_channel_manager.telegram_state import initialize_ledger, strict_next_post

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / native.SOURCE_PATH


def _candidate() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8"))


def test_native_v6_identity_and_ledger_adapter_are_deterministic() -> None:
    queue = native.build_quote_v6_native_queue(FILE)
    assert queue.schema_name == native.NATIVE_SCHEMA
    assert queue.release_state == "provider_inert_candidate"
    assert queue.provider_writes_authorized is False
    assert queue.digest == "sha256:a1d865277e794aa5d47ea8248bfab9406b05a44e0ec822400650ed3f580e06f0"
    assert len(queue.posts) == 30
    assert [p.sequence for p in queue.posts] == list(range(1, 31))
    assert len({p.publication_id for p in queue.posts}) == 30
    assert queue.posts[0].publication_id == "lordchrist-ryle-religion-cost"
    assert queue.posts[-1].publication_id == "lordchrist-whitefield-self-denial"

    ledger = initialize_ledger(queue)
    assert ledger.queue_digest == queue.digest
    assert all(x.state == "pending" and x.provider_effect == "impossible" for x in ledger.entries.values())
    next_post, reason = strict_next_post(queue, ledger)
    assert next_post is not None and next_post.publication_id == queue.posts[0].publication_id
    assert reason == "next pending publication"
    # This is an in-memory simulation. No real state branch, intent or provider action is created.


def test_all_thirty_source_frozen_html_payloads_match_shared_telegram_renderer() -> None:
    queue = native.build_quote_v6_native_queue(FILE)
    original = _candidate()["items"]
    for post, source in zip(queue.posts, original, strict=True):
        builder = _RenderBuilder()
        builder.append_styled(post.quote_text, "blockquote")
        builder.append("\n")
        builder.append_styled(post.attribution_line, "italic")
        builder.append("\n\n")
        builder.append(post.hashtags)
        assert builder.html_text == post.html_text == source["html_text"]
        assert builder.text == post.text
        assert tuple(e.type for e in builder.entities) == ("blockquote", "italic")
        assert post.payload_sha256 == source["candidate_payload_sha256"]
        assert post.source.original_english_span_sha256 == source["historical_english_span_sha256"]
        assert post.source.original_ru_quote_sha256 == source["quoted_russian_sha256"]
        assert post.source.url == source["source_url"]
        assert len(post.text.encode("utf-16-le")) // 2 <= 4096
        assert "Контекст:" not in post.text
        assert "Примечание редакции:" not in post.text


@pytest.mark.parametrize(
    "modified",
    (
        lambda d: d["items"][0].__setitem__("html_text", d["items"][0]["html_text"] + "\n"),
        lambda d: d["items"][0].__setitem__("candidate_payload_sha256", "sha256:" + "0" * 64),
        lambda d: d["items"][0].__setitem__("historical_english_span_sha256", "INVALID"),
        lambda d: d["items"][0].__setitem__("publication_id", d["items"][1]["publication_id"]),
        lambda d: d.__setitem__("provider_write_authorization", True),
        lambda d: d.__setitem__("rights_review_complete", True),
        lambda d: d.__setitem__("new_release_digest", "sha256:" + "1" * 64),
    ),
)
def test_unreviewed_tampering_or_authorization_claim_is_rejected(tmp_path: Path, modified: object) -> None:
    data = copy.deepcopy(_candidate())
    modified(data)
    source = tmp_path / "tampered.json"
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises((ValueError, KeyError)):
        native.build_quote_v6_native_queue(source)


def test_cli_remains_inert_and_emits_source_bound_identity(capsys: pytest.CaptureFixture[str]) -> None:
    assert native.main(["--root", str(ROOT)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["posts"] == 30
    assert result["provider_writes_authorized"] is False
    assert result["release_state"] == "provider_inert_candidate"
    assert result["candidate_digest"] == _candidate()["candidate_digest"]
