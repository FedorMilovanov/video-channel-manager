from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import link_cards  # noqa: E402
from lord_god_article_wave_v3.wall import post_reference  # noqa: E402


class FakeClient:
    def __init__(self, responses: dict[str, object] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def _call(self, method: str, *, params: dict[str, object] | None = None) -> object:
        self.calls.append((method, dict(params or {})))
        value = self.responses.get(method)
        if isinstance(value, Exception):
            raise value
        return value


def policy() -> dict[str, Any]:
    return link_cards.load_policy(ROOT)


def exact_link_post(operation: dict[str, Any], *, post_id: int = 77) -> dict[str, Any]:
    return {
        "owner_id": link_cards.OWNER_ID,
        "id": post_id,
        "date": operation["publish_date"],
        "text": operation["message"],
        "attachments": [
            {
                "type": "link",
                "link": {"url": operation["url"]},
            }
        ],
    }


def test_exact_link_card_requires_link_attachment_and_no_photo() -> None:
    operation = policy()["operations"][0]
    reference = post_reference(exact_link_post(operation), "postponed")

    assert link_cards.link_card_exact_reference(operation, reference)
    assert operation["url"] in reference["text_urls"]
    assert operation["url"] in reference["link_urls"]
    assert reference["has_photo"] is False

    text_only = post_reference(
        {
            **exact_link_post(operation),
            "attachments": [],
        },
        "postponed",
    )
    assert not link_cards.link_card_exact_reference(operation, text_only)

    link_and_photo = post_reference(
        {
            **exact_link_post(operation),
            "attachments": [
                {"type": "link", "link": {"url": operation["url"]}},
                {
                    "type": "photo",
                    "photo": {"owner_id": link_cards.OWNER_ID, "id": 5},
                },
            ],
        },
        "postponed",
    )
    assert not link_cards.link_card_exact_reference(operation, link_and_photo)


def test_submit_uses_article_url_attachment_and_never_calls_photo_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    current_policy = policy()
    operation = current_policy["operations"][0]
    journal = link_cards.fresh_link_card_journal(current_policy)
    mutation = FakeClient({"wall.post": {"post_id": 123}})
    expected_reference = post_reference(
        exact_link_post(operation, post_id=123),
        "postponed",
    )
    monkeypatch.setattr(
        link_cards,
        "wait_for_exact_link_card",
        lambda *args, **kwargs: expected_reference,
    )

    post_id, reference = link_cards.submit_link_card_post(
        operation=operation,
        read_client=FakeClient(),
        mutation_client=mutation,
        journal=journal,
        journal_path=tmp_path / "link-card-journal.json",
    )

    assert post_id == 123
    assert reference == expected_reference
    assert [method for method, _ in mutation.calls] == ["wall.post"]
    params = mutation.calls[0][1]
    assert params["attachments"] == operation["url"]
    assert params["message"] == operation["message"]
    assert all(not method.startswith("photos.") for method, _ in mutation.calls)
    entry = journal["operations"][operation["operation_id"]]
    assert entry["stage"] == "verified"
    assert entry["attachment_url"] == operation["url"]


def test_unknown_wall_post_reconciles_exact_link_card(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    current_policy = policy()
    operation = current_policy["operations"][0]
    journal = link_cards.fresh_link_card_journal(current_policy)
    ambiguous = link_cards.VkApiError(
        "network timeout",
        method="wall.post",
        code=None,
        retryable=True,
    )
    mutation = FakeClient({"wall.post": ambiguous})
    reference = post_reference(exact_link_post(operation, post_id=812), "postponed")
    monkeypatch.setattr(
        link_cards,
        "find_exact_link_card",
        lambda *args, **kwargs: reference,
    )

    post_id, found = link_cards.submit_link_card_post(
        operation=operation,
        read_client=FakeClient(),
        mutation_client=mutation,
        journal=journal,
        journal_path=tmp_path / "link-card-journal.json",
    )

    assert post_id == 812
    assert found == reference
    entry = journal["operations"][operation["operation_id"]]
    assert entry["stage"] == "verified"
    assert entry["reconciled_from"] == "wall_post_unknown"


def test_legacy_photo_unknown_is_observed_but_not_reused(tmp_path: Path) -> None:
    current_policy = policy()
    operation = current_policy["operations"][0]
    legacy = tmp_path / "journal.json"
    legacy.write_text(
        json.dumps(
            {
                "operations": {
                    operation["operation_id"]: {
                        "stage": "photo_save_unknown",
                        "upload_payload": {"photo": "secret"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    observation = link_cards.observe_legacy_photo_journal(legacy)
    report = link_cards.preflight_link_cards(
        current_policy,
        [],
        [],
        link_cards.fresh_link_card_journal(current_policy),
        minimum_future_seconds=-(10**9),
    )

    assert observation["remote_photo_may_exist"] is True
    assert observation["legacy_photo_state_is_not_reused"] is True
    assert "upload_payload" not in json.dumps(observation)
    assert report["states"][0]["state"] == "ready"


def test_link_card_source_does_not_contain_vk_photo_mutations_or_jpeg_conversion() -> None:
    source = Path(link_cards.__file__).read_text(encoding="utf-8")

    assert '"photos.getWallUploadServer"' not in source
    assert '"photos.saveWallPhoto"' not in source
    assert "convert_webp_to_jpeg" not in source
    assert "ffmpeg" not in source.lower()
    assert '"attachments": article_url' in source
    assert '"vk_photo_api_calls": 0' in source


def test_entrypoint_routes_runtime_to_photo_wave_v4() -> None:
    entrypoint = (
        ROOT / "scripts" / "schedule_lord_god_article_wave_v3.py"
    ).read_text(encoding="utf-8")
    runner = (ROOT / "scripts" / "run-lord-god-article-wave.ps1").read_text(
        encoding="utf-8"
    )

    assert "photo_wave_v4 as photo_wave_module" in entrypoint
    assert "photo_wave_module.guarded_main()" in entrypoint
    assert "10 JPEG-обложек" in runner
    assert "один отложенный пост с JPEG-обложкой" in runner
    assert "wall.parseAttachedLink" not in runner
