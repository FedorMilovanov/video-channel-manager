from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_publisher import load_queue

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/editorial-portfolio-v1.json"
QUOTE_QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/verified-30-posts.json"
RESEARCH_QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"
EXPECTED_QUOTE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"


def portfolio() -> dict[str, object]:
    return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))


def lanes_by_id(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    lanes = payload["lanes"]
    assert isinstance(lanes, list)
    return {str(lane["lane_id"]): lane for lane in lanes if isinstance(lane, dict)}


def test_portfolio_is_provider_inert_and_quote_queue_identity_is_unchanged() -> None:
    payload = portfolio()
    assert payload["provider_writes_authorized"] is False
    assert payload["project_key"] == "lord-god-strength"
    assert payload["channel_username"] == "@lordchrist"

    queue = load_queue(QUOTE_QUEUE_PATH)
    assert queue.digest == EXPECTED_QUOTE_DIGEST
    assert len(queue.posts) == 30


def test_only_legacy_quotes_are_live_ready_now() -> None:
    payload = portfolio()
    lanes = lanes_by_id(payload)
    live_ready = {lane_id for lane_id, lane in lanes.items() if lane["eligibility"] == "live_ready"}
    runtime_lanes = {lane_id for lane_id, lane in lanes.items() if lane["current_runtime_consumes_lane"] is True}

    assert live_ready == {"legacy_quotes"}
    assert runtime_lanes == {"legacy_quotes"}
    assert lanes["legacy_quotes"]["next_gate"] == "none"

    for lane_id, lane in lanes.items():
        if lane_id == "legacy_quotes":
            continue
        assert lane["next_gate"] != "none"
        assert lane["current_runtime_consumes_lane"] is False


def test_research_v2_portfolio_binding_matches_staged_fact_checked_queue() -> None:
    payload = portfolio()
    lane = lanes_by_id(payload)["historical_preaching_research_v2"]
    queue = json.loads(RESEARCH_QUEUE_PATH.read_text(encoding="utf-8"))

    assert lane["eligibility"] == "release_reviewed_provider_inert"
    assert lane["candidate_count"] == 5
    assert queue["schedule"]["state"] == "staged"
    assert queue["schedule"]["activation_at_utc"] is None
    assert queue["schedule"]["canary_publication_id"] is None
    assert queue["schedule"]["canary_message_id"] is None

    posts = queue["posts"]
    assert len(posts) == 5
    assert all(post["editorial_status"] == "ready" for post in posts)
    assert all(post["fact_check_status"] == "accepted" for post in posts)
    assert all(post["rights_status"] == "original_editorial_no_long_quotes" for post in posts)
    assert [post["publication_id"] for post in posts] == lane["candidate_publication_ids"]


def test_preferred_cycle_is_multi_lane_without_adjacent_repetition() -> None:
    payload = portfolio()
    lanes = lanes_by_id(payload)
    cycle = payload["preferred_cycle"]
    assert isinstance(cycle, list)
    assert len(cycle) >= 6
    assert all(lane_id in lanes for lane_id in cycle)
    assert all(left != right for left, right in zip(cycle, cycle[1:], strict=False))
    assert payload["selection_policy"]["fallback_lane"] == "legacy_quotes"


def test_next_adaptation_pool_is_broad_but_fail_closed() -> None:
    payload = portfolio()
    lanes = lanes_by_id(payload)

    heart = lanes["heart_series_adaptations"]
    assert heart["eligibility"] == "candidate_requires_telegram_adaptation"
    assert len(heart["candidate_topics"]) == 9

    assert lanes["deep_bible_study_adaptations"]["eligibility"] == "publication_hold"
    assert lanes["genesis_enoch_hard_texts"]["eligibility"] == "publication_hold"
    assert lanes["pulpit_and_church_history"]["eligibility"] == "publication_hold_or_active_research"
    assert lanes["biblical_atlas"]["eligibility"] == "active_research"

    research = payload["research_repository"]
    assert research["repository"] == "FedorMilovanov/Research"
    assert len(research["checked_main_anchor"]) == 40
