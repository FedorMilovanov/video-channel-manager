"""The live v4 queue is bound, post by post, to recorded primary sources.

Every post's English anchors must appear verbatim and in order in exactly
one recorded excerpt file under ``verified-sources/``, the file's URL must
match the post's source URL, and the Russian text must be a full-size
translation of the anchored span (neither a one-line excerpt nor a
condensed retelling). This is the guard that caught the fabricated
Bunyan ending and the abridged Bunyan/Edwards cards on 2026-10-28.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LORDCHRIST = ROOT / "content/telegram/lordchrist"
QUEUE_PATH = LORDCHRIST / "verified-30-posts.json"
ACTIVATION_PATH = LORDCHRIST / "quote-v4-runtime-activation.json"
SCHEDULE_PATH = LORDCHRIST / "production-schedule.json"


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _queue() -> dict:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def _excerpt_files() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in (LORDCHRIST / "verified-sources").glob("*.txt")}


def test_every_v4_post_anchors_verbatim_into_exactly_one_recorded_excerpt() -> None:
    files = _excerpt_files()
    assert len(files) == 30
    for post in _queue()["posts"]:
        source = post["source"]
        start, end = _norm(source["anchor_start"]), _norm(source["anchor_end"])
        hits = []
        for name, text in files.items():
            normalized = _norm(text)
            i, j = normalized.find(start), normalized.find(end)
            if i >= 0 and j > i:
                hits.append((name, normalized, i, j + len(end)))
        assert len(hits) == 1, f"sequence {post['sequence']}: anchors bind to {len(hits)} excerpts"
        name, normalized, i, j = hits[0]
        url = re.search(r"^URL: (.+)$", files[name], re.M)
        assert url is not None and url.group(1).strip() == source["url"], f"sequence {post['sequence']}: URL drift"
        en_words = len(normalized[i:j].split())
        ru_words = len(post["text"].split())
        ratio = ru_words / en_words
        assert 0.55 <= ratio <= 1.35, f"sequence {post['sequence']}: RU/EN word ratio {ratio:.2f} (abridged or padded)"


def test_v4_activation_artifact_binds_queue_schedule_and_policy() -> None:
    from video_channel_manager.telegram_models import TelegramQueue
    from video_channel_manager.telegram_presentation import load_presentation_policy

    queue = TelegramQueue.model_validate_json(QUEUE_PATH.read_text(encoding="utf-8"), strict=True)
    activation = json.loads(ACTIVATION_PATH.read_text(encoding="utf-8"))
    schedule = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    policy = load_presentation_policy(LORDCHRIST / "presentation-policy.json")

    assert activation["release_id"] == "lordchrist-puritan-spurgeon-v4"
    assert activation["provider_writes_authorized"] is True
    assert activation["queue_digest"] == queue.digest == schedule["queue_digest"]
    assert activation["presentation_policy_sha256"] == policy.digest == schedule["presentation_policy_sha256"]
    assert activation["presentation_policy_id"] == policy.policy_id


def test_publisher_reads_the_committed_activation_instead_of_fabricating_one() -> None:
    poster = (ROOT / ".github/workflows/lordchrist-telegram-poster.yml").read_text(encoding="utf-8")
    preflight = (ROOT / ".github/workflows/lordchrist-quote-v4-preflight.yml").read_text(encoding="utf-8")

    assert "QUOTE_V4_ACTIVATION_PATH: content/telegram/lordchrist/quote-v4-runtime-activation.json" in poster
    assert "ACTIVATION_PATH: content/telegram/lordchrist/quote-v4-runtime-activation.json" in preflight
    # No self-authorization anywhere: neither workflow may hardcode the write
    # flag nor mint a checkpoint; both must read the reviewed artifact.
    assert '"provider_writes_authorized": True' not in poster
    assert '"provider_writes_authorized": bool(schedule.get(' not in poster
    assert "checkpoint = {" not in poster
    assert 'digest == activation["queue_digest"] == schedule["queue_digest"]' in preflight
