from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

POLICY = Path("content/telegram/lordchrist/shorts-feed-policy.json")
PREVIEW = Path("content/telegram/lordchrist/shorts-piper-macarthur-deferred-review-20261106.json")


def test_four_specific_shorts_are_prepared_without_provider_authorization() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    data = json.loads(PREVIEW.read_text(encoding="utf-8"))
    assert policy["telegram_provider_mutation_allowed"] is False
    assert policy["slot_local_time"] == "16:00"
    assert data["owner_upload_request_recorded"] is True
    assert data["active_telegram_native_video_queue"] is False
    assert data["active_telegram_schedule_count"] == 0
    assert data["rights_verification_approved_count"] == 0
    assert data["telegram_provider_mutation_allowed"] is False
    assert data["telegram_provider_write_performed"] is False
    assert data["jude_nov7_14_00_is_separate"] is True
    assert data["charnock_and_quote_writers_unchanged"] is True
    vids = ["ba4ZahiY-U0", "_aDIR0D7rSk", "tELrnM71TQA", "VeY1tpoLUJU"]
    assert len(data["items"]) == len(vids) == 4
    assert [r["youtube_video_id"] for r in data["items"]] == vids
    assert len({r["media_sha256"] for r in data["items"]}) == 4
    for i, r in enumerate(data["items"]):
        at = datetime.fromisoformat(r["proposed_at"])
        assert at.isoformat() == f"2026-11-{8 + i:02d}T16:00:00+03:00"
        assert r["publication_id"] == "lordchrist-short-" + vids[i]
        assert r["caption_sha256"] == "sha256:" + hashlib.sha256(r["caption"].encode("utf-8")).hexdigest()
        assert "????" not in r["caption"], "Windows console codepage corrupted Russian caption"
        assert "Исходное видео:" in r["caption"]
        assert "#ГосподьБог" in r["caption"]
        assert f"https://www.youtube.com/watch?v={vids[i]}" in r["caption"]
        assert r["original_rightsholder_written_telegram_reupload_permission_verified"] is False
        assert r["video_release_authorized"] is False
        assert r["video_publish_operation_allowed"] is False
        assert r["telegram_state_mutation_performed"] is False
        assert r["schedule_active"] is False
        assert r["media_byte_size"] <= 50_000_000
    assert [r["speaker"] for r in data["items"]] == ["John MacArthur", "John MacArthur", "John MacArthur", "John Piper"]
