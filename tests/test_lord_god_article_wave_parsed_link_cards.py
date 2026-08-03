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

from lord_god_article_wave_v3 import link_cards_hardened as hardened  # noqa: E402
from lord_god_article_wave_v3 import link_cards_hardened_entry as strict  # noqa: E402
from lord_god_article_wave_v3 import parsed_link_contract as contract  # noqa: E402
from lord_god_article_wave_v3 import parsed_link_mutations as mutations  # noqa: E402
from lord_god_article_wave_v3 import parsed_link_preview as preview  # noqa: E402


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


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    return contract.load_parsed_policy(ROOT)


def expected(operation: dict[str, Any]) -> dict[str, str]:
    return {
        "title": str(operation["title"]),
        "description": ("Проверенное полное описание статьи для карточки ВКонтакте длиной более сорока символов."),
    }


def parse_response(
    operation: dict[str, Any],
    metadata: dict[str, str],
    *,
    owner_id: int = -60805374,
    photo_id: int = 991,
) -> dict[str, object]:
    return {
        "data": [
            {
                "type": "link",
                "link": {
                    "url": operation["url"],
                    "title": metadata["title"],
                    "description": metadata["description"],
                    "photo": {
                        "owner_id": owner_id,
                        "id": photo_id,
                        "sizes": [{"width": 1200, "height": 630}],
                    },
                },
            }
        ]
    }


def exact_reference(
    operation: dict[str, Any],
    metadata: dict[str, str],
    *,
    post_id: int,
) -> dict[str, Any]:
    raw = {
        "owner_id": hardened.OWNER_ID,
        "id": post_id,
        "date": operation["publish_date"],
        "text": operation["message"],
        "attachments": [
            {
                "type": "link",
                "link": {
                    "url": operation["url"],
                    "title": metadata["title"],
                    "description": metadata["description"],
                    "photo": {
                        "owner_id": -60805374,
                        "id": 991,
                        "sizes": [{"width": 1200, "height": 630}],
                    },
                },
            }
        ],
    }
    reference = hardened.hardened_post_reference(raw, "postponed")
    assert strict.strict_exact_reference(operation, reference, metadata)
    return reference


def test_delivery_contract_v3_is_digest_locked() -> None:
    policy, delivery = load()

    assert delivery["schema_version"] == 3
    assert delivery["contract_sha256"] == contract.EXPECTED_DELIVERY_CONTRACT_SHA
    assert delivery["link_preparation_method"] == "wall.parseAttachedLink"
    assert delivery["write_method"] == "wall.post"
    assert delivery["separate_vk_photo"] is False
    assert delivery["vk_photo_api_calls"] == 0
    assert delivery["prepared_jpeg_assets"] == 0
    assert policy["attachment_mode"] == "parsed-external-link-card"


def test_parse_request_is_exact_single_link_attachment_json() -> None:
    policy, _ = load()
    article_url = policy["operations"][0]["url"]

    payload = preview.parse_request_json(article_url)

    expected_payload = [{"type": "link", "link": article_url}]
    assert payload == json.dumps(
        expected_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert json.loads(payload) == expected_payload


def test_parse_response_requires_matching_complete_link_preview() -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    metadata = expected(operation)

    parsed = preview.parse_link_response(
        parse_response(operation, metadata),
        article_url=operation["url"],
        expected_metadata=metadata,
    )

    assert parsed["article_url"] == operation["url"]
    assert parsed["title"] == metadata["title"]
    assert parsed["description"] == metadata["description"]
    assert parsed["link_photo_id"] == "-60805374_991"
    assert parsed["attachment_type"] == "link"
    assert parsed["has_preview_photo"] is True


def test_parse_response_blocks_missing_preview_photo() -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    metadata = expected(operation)
    response = parse_response(operation, metadata)
    response["data"][0]["link"].pop("photo")

    with pytest.raises(RuntimeError, match="no preview photo"):
        preview.parse_link_response(
            response,
            article_url=operation["url"],
            expected_metadata=metadata,
        )


def test_parse_response_blocks_wrong_url_title_and_description() -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    metadata = expected(operation)

    wrong_url = parse_response(operation, metadata)
    wrong_url["data"][0]["link"]["url"] = "https://gospod-bog.ru/other/"
    with pytest.raises(RuntimeError, match="URL mismatch"):
        preview.parse_link_response(
            wrong_url,
            article_url=operation["url"],
            expected_metadata=metadata,
        )

    wrong_title = parse_response(operation, metadata)
    wrong_title["data"][0]["link"]["title"] = "Другой заголовок"
    with pytest.raises(RuntimeError, match="title"):
        preview.parse_link_response(
            wrong_title,
            article_url=operation["url"],
            expected_metadata=metadata,
        )

    wrong_description = parse_response(operation, metadata)
    wrong_description["data"][0]["link"]["description"] = "Коротко"
    with pytest.raises(RuntimeError, match="description"):
        preview.parse_link_response(
            wrong_description,
            article_url=operation["url"],
            expected_metadata=metadata,
        )


def test_submit_parses_then_posts_with_link_title_and_link_photo_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy, delivery = load()
    operation = policy["operations"][0]
    metadata = expected(operation)
    read_client = FakeClient({"wall.parseAttachedLink": parse_response(operation, metadata)})
    mutation_client = FakeClient({"wall.post": {"post_id": 771}})
    reference = exact_reference(operation, metadata, post_id=771)
    journal = contract.fresh_journal(policy, delivery)
    monkeypatch.setattr(
        mutations,
        "wait_for_exact",
        lambda *args, **kwargs: reference,
    )

    post_id, found, parsed = mutations.submit(
        operation=operation,
        expected_metadata=metadata,
        policy=policy,
        contract=delivery,
        read_client=read_client,
        mutation_client=mutation_client,
        journal=journal,
        journal_path=tmp_path / "journal.json",
    )

    assert post_id == 771
    assert found == reference
    assert parsed["link_photo_id"] == "-60805374_991"
    assert [method for method, _ in read_client.calls] == ["wall.parseAttachedLink"]
    assert [method for method, _ in mutation_client.calls] == ["wall.post"]
    parse_params = read_client.calls[0][1]
    assert json.loads(str(parse_params["links"])) == [{"type": "link", "link": operation["url"]}]
    post_params = mutation_client.calls[0][1]
    assert post_params["attachments"] == operation["url"]
    assert post_params["link_title"] == metadata["title"]
    assert post_params["link_photo_id"] == "-60805374_991"
    assert post_params["publish_date"] == operation["publish_date"]
    assert all(not method.startswith("photos.") for method, _ in read_client.calls)
    assert all(not method.startswith("photos.") for method, _ in mutation_client.calls)
    entry = journal["operations"][operation["operation_id"]]
    assert entry["stage"] == "verified"
    assert entry["post_id"] == 771


def test_submit_never_calls_wall_post_when_preview_is_invalid(
    tmp_path: Path,
) -> None:
    policy, delivery = load()
    operation = policy["operations"][0]
    metadata = expected(operation)
    response = parse_response(operation, metadata)
    response["data"][0]["link"].pop("photo")
    read_client = FakeClient({"wall.parseAttachedLink": response})
    mutation_client = FakeClient({"wall.post": {"post_id": 1}})
    journal = contract.fresh_journal(policy, delivery)

    with pytest.raises(RuntimeError, match="Link preview preparation"):
        mutations.submit(
            operation=operation,
            expected_metadata=metadata,
            policy=policy,
            contract=delivery,
            read_client=read_client,
            mutation_client=mutation_client,
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )

    assert [method for method, _ in read_client.calls] == ["wall.parseAttachedLink"]
    assert mutation_client.calls == []
    entry = journal["operations"][operation["operation_id"]]
    assert entry["stage"] == "link_parse_unknown"


def test_parse_audit_calls_all_ten_urls_without_wall_post() -> None:
    policy, _ = load()
    expectations = {
        str(operation["operation_id"]): expected(operation)
        for operation in policy["operations"]
    }
    responses = {
        operation["url"]: parse_response(
            operation,
            expectations[operation["operation_id"]],
            photo_id=900 + int(operation["ordinal"]),
        )
        for operation in policy["operations"]
    }

    class ParseClient(FakeClient):
        def _call(
            self,
            method: str,
            *,
            params: dict[str, object] | None = None,
        ) -> object:
            self.calls.append((method, dict(params or {})))
            assert method == "wall.parseAttachedLink"
            links = json.loads(str((params or {})["links"]))
            assert links[0]["type"] == "link"
            return responses[links[0]["link"]]

    client = ParseClient()
    items, report = preview.audit_parsed_link_cards(
        client,
        policy,
        expectations,
    )

    assert len(items) == 10
    assert report["calls"] == 10
    assert report["verified"] == 10
    assert report["conflicts"] == 0
    assert report["request_item_shape"] == "type-link/link-url"
    assert {method for method, _ in client.calls} == {"wall.parseAttachedLink"}


def test_superseded_v2_rejection_is_observed_but_not_reused(
    tmp_path: Path,
) -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    path = tmp_path / "link-card-journal-v2.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "operations": {
                    operation["operation_id"]: {
                        "operation_id": operation["operation_id"],
                        "stage": "wall_post_rejected",
                        "error": (
                            "VkApiError: VK API 100 in wall.post: Violated: link_photo_sizing_rule. No photo given"
                        ),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    observation = contract.observe_superseded_v2(path, policy)

    assert observation["safe_to_supersede"] is True
    assert len(observation["observed_operations"]) == 1
    assert observation["observed_operations"][0]["accepted_superseded_rejection"] is True


def test_superseded_v2_unknown_or_post_id_blocks_new_contract(
    tmp_path: Path,
) -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    path = tmp_path / "link-card-journal-v2.json"
    path.write_text(
        json.dumps(
            {
                "operations": {
                    operation["operation_id"]: {
                        "stage": "wall_post_unknown",
                        "post_id": 777,
                        "error": "timeout",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="cannot be safely superseded"):
        contract.observe_superseded_v2(path, policy)


def test_active_entrypoint_and_runner_use_photo_wave_v4() -> None:
    entrypoint = (
        ROOT / "scripts" / "schedule_lord_god_article_wave_v3.py"
    ).read_text(encoding="utf-8")
    runner = (ROOT / "scripts" / "run-lord-god-article-wave.ps1").read_text(
        encoding="utf-8"
    )
    photo_orchestrator = (
        ROOT / "scripts" / "lord_god_article_wave_v3" / "photo_wave_v4.py"
    ).read_text(encoding="utf-8")
    photo_mutations = (
        ROOT / "scripts" / "lord_god_article_wave_v3" / "mutations.py"
    ).read_text(encoding="utf-8")

    assert "photo_wave_v4 as photo_wave_module" in entrypoint
    assert "photo_wave_module.guarded_main()" in entrypoint
    assert "photo_wave_v4.py" in runner
    assert "wall.parseAttachedLink" not in runner
    assert "photo-journal-v4.json" in photo_orchestrator
    assert "lord-god-article-photo-wave-v4-202608" in photo_orchestrator
    assert '"photos.getWallUploadServer"' in photo_mutations
    assert '"photos.saveWallPhoto"' in photo_mutations
    assert '"attachments": photo_token_value' in photo_mutations
    assert '"publish_date": int(operation["publish_date"])' in photo_mutations
