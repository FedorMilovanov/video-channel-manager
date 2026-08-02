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


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.headers = {"content-type": "image/webp"}

    def raise_for_status(self) -> None:
        return None


class FakeHttpClient:
    def __init__(self, content: bytes, **_: object) -> None:
        self.content = content
        self.calls: list[str] = []

    def __enter__(self) -> FakeHttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str) -> FakeResponse:
        self.calls.append(url)
        return FakeResponse(self.content)


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    return hardened.load_hardened_policy(ROOT)


def expectations(operation: dict[str, Any]) -> dict[str, str]:
    return {
        "title": str(operation["title"]),
        "description": (
            "Проверенное подробное описание статьи для внешней карточки "
            "ВКонтакте, содержащее больше сорока символов."
        ),
    }


def exact_post(
    operation: dict[str, Any],
    expected: dict[str, str],
    *,
    post_id: int = 77,
    queue: str = "postponed",
) -> tuple[dict[str, Any], str]:
    post = {
        "owner_id": hardened.OWNER_ID,
        "id": post_id,
        "date": operation["publish_date"],
        "text": operation["message"],
        "attachments": [
            {
                "type": "link",
                "link": {
                    "url": operation["url"],
                    "title": expected["title"],
                    "description": expected["description"],
                    "photo": {
                        "id": 123,
                        "owner_id": hardened.OWNER_ID,
                        "sizes": [{"width": 1200, "height": 630}],
                    },
                },
            }
        ],
    }
    return post, queue


def valid_webp(width: int = 1200, height: int = 630) -> bytes:
    vp8x = (
        b"\x00\x00\x00\x00"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    payload = (
        b"RIFF"
        + (10_020).to_bytes(4, "little")
        + b"WEBP"
        + b"VP8X"
        + len(vp8x).to_bytes(4, "little")
        + vp8x
    )
    return payload + b"\x00" * (10_028 - len(payload))


def test_delivery_contract_is_digest_locked_and_effective_policy_is_consistent() -> None:
    policy, contract = load()

    assert contract["contract_sha256"] == hardened.EXPECTED_DELIVERY_CONTRACT_SHA
    assert policy["attachment_mode"] == "external-link-card"
    assert policy["asset_mode"] == "remote-open-graph-only"
    assert policy["delivery_contract_sha256"] == contract["contract_sha256"]
    assert contract["allowed_attachment_types"] == ["link"]
    assert contract["vk_photo_api_calls"] == 0


def test_exact_reference_requires_only_one_complete_link_card() -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    expected = expectations(operation)
    post, queue = exact_post(operation, expected)
    reference = hardened.hardened_post_reference(post, queue)

    assert hardened.exact_reference(operation, reference, expected)

    extra_video = {
        **post,
        "attachments": [
            *post["attachments"],
            {"type": "video", "video": {"owner_id": -1, "id": 2}},
        ],
    }
    assert not hardened.exact_reference(
        operation,
        hardened.hardened_post_reference(extra_video, queue),
        expected,
    )

    malformed_photo = {
        **post,
        "attachments": [
            *post["attachments"],
            {"type": "photo", "photo": {}},
        ],
    }
    malformed_reference = hardened.hardened_post_reference(
        malformed_photo,
        queue,
    )
    assert malformed_reference["has_photo"] is True
    assert not hardened.exact_reference(
        operation,
        malformed_reference,
        expected,
    )

    duplicate_link = {
        **post,
        "attachments": [*post["attachments"], *post["attachments"]],
    }
    assert not hardened.exact_reference(
        operation,
        hardened.hardened_post_reference(duplicate_link, queue),
        expected,
    )


def test_exact_reference_requires_title_description_preview_and_schedule() -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    expected = expectations(operation)
    post, queue = exact_post(operation, expected)

    wrong_title = json.loads(json.dumps(post))
    wrong_title["attachments"][0]["link"]["title"] = "Другой заголовок"
    assert not hardened.exact_reference(
        operation,
        hardened.hardened_post_reference(wrong_title, queue),
        expected,
    )

    no_description = json.loads(json.dumps(post))
    no_description["attachments"][0]["link"]["description"] = ""
    assert not hardened.exact_reference(
        operation,
        hardened.hardened_post_reference(no_description, queue),
        expected,
    )

    no_preview = json.loads(json.dumps(post))
    no_preview["attachments"][0]["link"]["photo"] = {}
    assert not hardened.exact_reference(
        operation,
        hardened.hardened_post_reference(no_preview, queue),
        expected,
    )

    wrong_time = json.loads(json.dumps(post))
    wrong_time["date"] += 1
    assert not hardened.exact_reference(
        operation,
        hardened.hardened_post_reference(wrong_time, queue),
        expected,
    )


def test_published_exact_post_is_accepted_only_at_exact_approved_time() -> None:
    policy, _ = load()
    operation = policy["operations"][0]
    expected = expectations(operation)
    post, _ = exact_post(operation, expected, queue="published")

    reference = hardened.hardened_post_reference(post, "published")
    assert hardened.exact_reference(operation, reference, expected)

    post["date"] -= 86_400
    old_reference = hardened.hardened_post_reference(post, "published")
    assert not hardened.exact_reference(operation, old_reference, expected)


def test_wall_post_accepted_stage_is_blocking_until_reconciled() -> None:
    policy, contract = load()
    operation = policy["operations"][0]
    expected_by_id = {
        str(item["operation_id"]): expectations(item)
        for item in policy["operations"]
    }
    journal = hardened.fresh_journal(policy, contract)
    journal["operations"][operation["operation_id"]] = {
        "stage": "wall_post_accepted",
        "post_id": 123,
    }

    report = hardened.preflight(
        policy,
        contract,
        expected_by_id,
        [],
        [],
        journal,
        minimum_future_seconds=-(10**9),
    )

    assert report["states"][0]["state"] == "conflict"
    assert "wall_post_accepted" in report["states"][0]["detail"]


def test_contract_guid_is_short_stable_and_contract_bound() -> None:
    policy, contract = load()
    first = hardened.contract_guid(policy["operations"][0], policy, contract)
    second = hardened.contract_guid(policy["operations"][1], policy, contract)

    assert first == hardened.contract_guid(policy["operations"][0], policy, contract)
    assert first != second
    assert first.startswith("lgaw3-01-")
    assert len(first) < 50


def test_submit_calls_only_wall_post_with_exact_url_and_hardened_guid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy, contract = load()
    operation = policy["operations"][0]
    expected = expectations(operation)
    post, queue = exact_post(operation, expected, post_id=321)
    reference = hardened.hardened_post_reference(post, queue)
    mutation = FakeClient({"wall.post": {"post_id": 321}})
    journal = hardened.fresh_journal(policy, contract)

    monkeypatch.setattr(
        hardened,
        "wait_for_exact",
        lambda *args, **kwargs: reference,
    )

    post_id, found = hardened.submit(
        operation=operation,
        expected_metadata=expected,
        policy=policy,
        contract=contract,
        read_client=FakeClient(),
        mutation_client=mutation,
        journal=journal,
        journal_path=tmp_path / "journal.json",
    )

    assert post_id == 321
    assert found == reference
    assert [method for method, _ in mutation.calls] == ["wall.post"]
    params = mutation.calls[0][1]
    assert params["attachments"] == operation["url"]
    assert params["message"] == operation["message"]
    assert params["publish_date"] == operation["publish_date"]
    assert params["guid"] == hardened.contract_guid(operation, policy, contract)
    assert all(not method.startswith("photos.") for method, _ in mutation.calls)


def test_unknown_wall_post_reconciles_only_complete_exact_card(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy, contract = load()
    operation = policy["operations"][0]
    expected = expectations(operation)
    post, queue = exact_post(operation, expected, post_id=812)
    reference = hardened.hardened_post_reference(post, queue)
    mutation = FakeClient(
        {
            "wall.post": hardened.VkApiError(
                "network timeout",
                method="wall.post",
                code=None,
                retryable=True,
            )
        }
    )
    journal = hardened.fresh_journal(policy, contract)
    monkeypatch.setattr(
        hardened,
        "find_exact",
        lambda *args, **kwargs: reference,
    )

    post_id, found = hardened.submit(
        operation=operation,
        expected_metadata=expected,
        policy=policy,
        contract=contract,
        read_client=FakeClient(),
        mutation_client=mutation,
        journal=journal,
        journal_path=tmp_path / "journal.json",
    )

    assert post_id == 812
    assert found == reference
    entry = journal["operations"][operation["operation_id"]]
    assert entry["stage"] == "verified"
    assert entry["reconciled_from"] == "wall_post_unknown"


def test_journal_contract_mismatch_blocks_when_write_state_exists(
    tmp_path: Path,
) -> None:
    policy, contract = load()
    path = tmp_path / "journal.json"
    path.write_text(
        json.dumps(
            {
                **hardened.fresh_journal(policy, contract),
                "delivery_contract_sha256": "sha256:older",
                "operations": {
                    policy["operations"][0]["operation_id"]: {
                        "stage": "wall_post_intent"
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="another execution contract"):
        hardened.load_journal(path, policy, contract)


def test_dimension_audit_requires_ten_valid_1200x630_webp_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, contract = load()
    rows = [
        {
            "operation_id": operation["operation_id"],
            "live_page_og_title": operation["title"],
            "live_page_og_description": expectations(operation)["description"],
            "checks": {
                "live_page_verified": True,
                "live_content_markers_verified": True,
                "live_og_image_verified": True,
                "content_source_verified": True,
                "metadata_source_verified": True,
                "live_metadata_matches_pinned_source": True,
            },
            "conflicts": [],
            "status": "verified",
        }
        for operation in policy["operations"]
    ]
    manifest = {
        "schema_name": "legacy",
        "schema_version": 1,
        "status": "verified",
        "expected_external_resources": 40,
        "external_urls_checked": 40,
        "article_pages_verified": 10,
        "live_content_markers_verified": 10,
        "og_images_verified": 10,
        "pinned_source_files_verified": 10,
        "pinned_metadata_files_verified": 10,
        "live_metadata_matches_pinned_source": 10,
        "prepared_jpeg_assets": 0,
        "vk_photo_uploads_required": False,
        "conflicts": 0,
        "global_conflicts": [],
        "items": rows,
    }
    monkeypatch.setattr(
        hardened.legacy,
        "audit_link_card_sources",
        lambda *args, **kwargs: (rows, manifest),
    )
    payload = valid_webp()
    clients: list[FakeHttpClient] = []

    def factory(**kwargs: object) -> FakeHttpClient:
        client = FakeHttpClient(payload, **kwargs)
        clients.append(client)
        return client

    audited_rows, audited = hardened.audit_sources(
        policy,
        contract,
        client_factory=factory,
    )

    assert len(clients) == 1
    assert len(clients[0].calls) == 10
    assert audited["schema_version"] == 2
    assert audited["og_image_dimensions_verified"] == 10
    assert audited["conflicts"] == 0
    assert audited["status"] == "verified"
    assert all(
        row["checks"]["og_image_dimensions_verified"] for row in audited_rows
    )


def test_active_entrypoint_and_runner_require_hardened_contract() -> None:
    entrypoint = (
        ROOT / "scripts" / "schedule_lord_god_article_wave_v3.py"
    ).read_text(encoding="utf-8")
    runner = (
        ROOT / "scripts" / "run-lord-god-article-wave.ps1"
    ).read_text(encoding="utf-8")
    source = Path(hardened.__file__).read_text(encoding="utf-8")

    assert "link_cards_hardened as link_cards_module" in entrypoint
    assert "link_cards_module.guarded_main()" in entrypoint
    assert "link_cards_hardened.py" in runner
    assert "link-card-delivery-contract.json" in runner
    assert '"photos.getWallUploadServer"' not in source
    assert '"photos.saveWallPhoto"' not in source
    assert "convert_webp_to_jpeg" not in source
