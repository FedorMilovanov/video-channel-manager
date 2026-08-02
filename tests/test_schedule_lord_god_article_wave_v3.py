from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "schedule_lord_god_article_wave_v3.py"
POLICY = ROOT / "content" / "policies" / "lord-god-article-wave-v3-202608.json"


def load_module() -> Any:
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("lord_god_article_v3_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def implementation_source() -> str:
    package = ROOT / "scripts" / "lord_god_article_wave_v3"
    paths = [SCRIPT, *sorted(package.glob("*.py"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_policy_is_static_v3_and_exact() -> None:
    module = load_module()
    policy = load_policy()

    module.validate_policy(policy)

    assert policy["schema_version"] == 3
    assert policy["decision_set_id"] == module.DECISION_SET_ID
    assert policy["policy_sha256"] == module.EXPECTED_POLICY_SHA
    assert policy["attachment_mode"] == "explicit-wall-photo-plus-text-link"
    assert policy["asset_mode"] == "materialized-jpeg-1200x630"
    assert policy["source_repository_commit"] == "aed8ed2244ad566b0458e490f629d394122dbf95"


def test_policy_has_ten_unique_public_resources_and_exact_schedule() -> None:
    module = load_module()
    operations = load_policy()["operations"]

    assert len(operations) == 10
    assert len({item["operation_id"] for item in operations}) == 10
    assert len({item["url"] for item in operations}) == 10
    assert len({item["image_url"] for item in operations}) == 10
    assert len({item["source_path"] for item in operations}) == 10
    assert all("diotref" not in item["url"] for item in operations)
    assert all("tma-na-serdce" not in item["url"] for item in operations)
    assert all("strah-bozhij" not in item["url"] for item in operations)
    assert all("duhi-v-temnice" not in item["url"] for item in operations)
    assert all("1-enohu" not in item["url"] for item in operations)

    for ordinal, operation in enumerate(operations, start=1):
        publish_at = datetime.fromisoformat(operation["publish_at"])
        assert operation["ordinal"] == ordinal
        assert publish_at.hour == 14 and publish_at.minute == 0
        assert publish_at.day == ordinal + 2
        assert operation["url"] in operation["message"]
        assert len(operation["source_markers"]) == 2
        assert all(len(marker) >= 8 for marker in operation["source_markers"])
        assert "💬" in operation["message"]
        assert 400 <= len(operation["message"]) <= 1000
        assert operation["message_sha256"] == module.message_sha(operation["message"])


def test_policy_digest_blocks_any_change() -> None:
    module = load_module()
    policy = load_policy()
    policy["operations"][0]["title"] += " drift"

    with pytest.raises(ValueError, match="digest"):
        module.validate_policy(policy)


def test_source_audit_contract_is_exactly_thirty_unique_urls() -> None:
    module = load_module()
    policy = load_policy()
    urls: set[str] = set()

    for operation in policy["operations"]:
        urls.add(module.normalize_url(operation["url"]))
        urls.add(module.normalize_url(operation["image_url"]))
        urls.add(module.source_raw_url(policy, operation))

    assert len(urls) == 30
    assert sum(url.startswith("https://gospod-bog.ru/") for url in urls) == 20
    assert sum(url.startswith("https://raw.githubusercontent.com/") for url in urls) == 10


def test_post_reference_accepts_photo_and_url_in_text_without_link_card() -> None:
    module = load_module()
    operation = load_policy()["operations"][0]
    post = {
        "owner_id": module.OWNER_ID,
        "id": 77,
        "date": operation["publish_date"],
        "text": operation["message"],
        "attachments": [
            {
                "type": "photo",
                "photo": {
                    "owner_id": module.OWNER_ID,
                    "id": 123,
                    "access_key": "secret",
                },
            }
        ],
    }

    reference = module.post_reference(post, "postponed")

    assert reference["has_photo"] is True
    assert operation["url"] in reference["text_urls"]
    assert reference["link_urls"] == []
    assert "photo-60805374_123_secret" in reference["photo_tokens"]
    assert module.exact_reference(
        operation,
        reference,
        expected_photo_token="photo-60805374_123_secret",
    )


def test_photo_identity_matches_even_if_wall_get_omits_access_key() -> None:
    module = load_module()
    operation = load_policy()["operations"][0]
    reference = module.post_reference(
        {
            "owner_id": module.OWNER_ID,
            "id": 78,
            "date": operation["publish_date"],
            "text": operation["message"],
            "attachments": [
                {
                    "type": "photo",
                    "photo": {"owner_id": module.OWNER_ID, "id": 123},
                }
            ],
        },
        "postponed",
    )

    assert reference["photo_tokens"] == ["photo-60805374_123"]
    assert reference["photo_identities"] == ["photo-60805374_123"]
    assert module.exact_reference(
        operation,
        reference,
        expected_photo_token="photo-60805374_123_secret",
    )


def test_post_reference_rejects_missing_photo_or_missing_text_url() -> None:
    module = load_module()
    operation = load_policy()["operations"][0]
    no_photo = module.post_reference(
        {
            "owner_id": module.OWNER_ID,
            "id": 1,
            "date": operation["publish_date"],
            "text": operation["message"],
            "attachments": [],
        },
        "postponed",
    )
    assert not module.exact_reference(operation, no_photo, expected_photo_token=None)

    no_url = dict(no_photo)
    no_url["has_photo"] = True
    no_url["photo_tokens"] = ["photo-60805374_1"]
    no_url["text_urls"] = []
    assert not module.exact_reference(operation, no_url, expected_photo_token=None)


def test_preflight_blocks_nearby_postponed_slot() -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    nearby = {
        "owner_id": module.OWNER_ID,
        "id": 9,
        "date": operation["publish_date"] + 60 * 60,
        "text": "Другой пост https://gospod-bog.ru/about/",
        "attachments": [
            {"type": "photo", "photo": {"owner_id": module.OWNER_ID, "id": 9}}
        ],
    }
    journal = module.fresh_journal(policy)

    report = module.preflight(
        policy,
        [],
        [nearby],
        journal,
        minimum_future_seconds=-10**9,
    )

    first = report["states"][0]
    assert first["state"] == "conflict"
    assert "two-hour" in first["detail"]


def test_preflight_accepts_one_exact_photo_post() -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    post = {
        "owner_id": module.OWNER_ID,
        "id": 11,
        "date": operation["publish_date"],
        "text": operation["message"],
        "attachments": [
            {"type": "photo", "photo": {"owner_id": module.OWNER_ID, "id": 22}}
        ],
    }
    journal = module.fresh_journal(policy)
    journal["operations"][operation["operation_id"]] = {
        "stage": "verified",
        "photo_token": "photo-60805374_22_key",
    }

    report = module.preflight(
        policy,
        [],
        [post],
        journal,
        minimum_future_seconds=-10**9,
    )

    assert report["states"][0]["state"] == "already_applied"


def test_unjournaled_existing_photo_post_is_not_silently_adopted() -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    post = {
        "owner_id": module.OWNER_ID,
        "id": 12,
        "date": operation["publish_date"],
        "text": operation["message"],
        "attachments": [
            {"type": "photo", "photo": {"owner_id": module.OWNER_ID, "id": 23}}
        ],
    }

    report = module.preflight(
        policy,
        [],
        [post],
        module.fresh_journal(policy),
        minimum_future_seconds=-10**9,
    )

    assert report["states"][0]["state"] == "conflict"
    assert "journal photo identity" in report["states"][0]["detail"]


def test_blocking_journal_stage_prevents_write() -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    journal["operations"][operation["operation_id"]] = {
        "stage": "photo_save_unknown",
        "photo_token": None,
    }

    report = module.preflight(
        policy,
        [],
        [],
        journal,
        minimum_future_seconds=-10**9,
    )

    assert report["states"][0]["state"] == "conflict"
    assert "photo_save_unknown" in report["states"][0]["detail"]


def test_load_journal_rejects_non_object_operations(tmp_path: Path) -> None:
    module = load_module()
    policy = load_policy()
    journal_path = tmp_path / "journal.json"
    journal_path.write_text(
        json.dumps(
            {
                "decision_set_id": "older-plan",
                "policy_sha256": "sha256:older",
                "operations": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="operations map"):
        module.load_journal(journal_path, policy)


def test_photo_save_explicit_rejection_is_blocking(tmp_path: Path) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    journal["operations"][operation["operation_id"]] = {
        "stage": "photo_save_rejected",
        "upload_payload": {"photo": "[]", "server": 1, "hash": "h"},
    }

    report = module.preflight(
        policy,
        [],
        [],
        journal,
        minimum_future_seconds=-10**9,
    )
    assert report["states"][0]["state"] == "conflict"
    assert "photo_save_rejected" in report["states"][0]["detail"]

    with pytest.raises(RuntimeError, match="blocking journal stage"):
        module.prepare_photo_token(
            operation=operation,
            jpeg=b"\xff\xd8" + b"x" * 20_000 + b"\xff\xd9",
            read_client=FakeClient(),
            mutation_client=FakeClient(),
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )


def test_saved_photo_response_requires_exact_group_owner() -> None:
    module = load_module()
    good = FakeClient(
        {
            "photos.saveWallPhoto": [
                {"owner_id": module.OWNER_ID, "id": 55, "access_key": "k"}
            ]
        }
    )
    token = module.saved_photo_token(
        good,
        {"photo": "[]", "server": 1, "hash": "h"},
    )
    assert token == "photo-60805374_55_k"

    bad = FakeClient({"photos.saveWallPhoto": [{"owner_id": 1, "id": 55}]})
    with pytest.raises(RuntimeError, match="unexpected owner"):
        module.saved_photo_token(
            bad,
            {"photo": "[]", "server": 1, "hash": "h"},
        )


def test_prepare_photo_reuses_saved_token_without_remote_calls(tmp_path: Path) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    journal["operations"][operation["operation_id"]] = {
        "stage": "photo_saved",
        "photo_token": "photo-60805374_88",
    }
    journal_path = tmp_path / "journal.json"
    read_client = FakeClient()
    mutation_client = FakeClient()

    token = module.prepare_photo_token(
        operation=operation,
        jpeg=b"\xff\xd8" + b"x" * 20_000 + b"\xff\xd9",
        read_client=read_client,
        mutation_client=mutation_client,
        journal=journal,
        journal_path=journal_path,
    )

    assert token == "photo-60805374_88"
    assert read_client.calls == []
    assert mutation_client.calls == []


def test_prepare_photo_blocks_unknown_save_stage(tmp_path: Path) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    journal["operations"][operation["operation_id"]] = {
        "stage": "photo_save_unknown"
    }

    with pytest.raises(RuntimeError, match="blocking journal stage"):
        module.prepare_photo_token(
            operation=operation,
            jpeg=b"\xff\xd8" + b"x" * 20_000 + b"\xff\xd9",
            read_client=FakeClient(),
            mutation_client=FakeClient(),
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )


def test_wall_post_uses_only_saved_photo_attachment_and_exact_text_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    mutation = FakeClient({"wall.post": {"post_id": 700}})
    expected_reference = {
        "has_photo": True,
        "post_id": 700,
        "photo_tokens": ["photo-60805374_99"],
    }
    monkeypatch.setattr(
        module.mutations_module,
        "wait_for_exact_post",
        lambda *args, **kwargs: expected_reference,
    )

    post_id, reference = module.submit_wall_post(
        operation=operation,
        photo_token_value="photo-60805374_99",
        read_client=FakeClient(),
        mutation_client=mutation,
        journal=journal,
        journal_path=tmp_path / "journal.json",
    )

    assert post_id == 700
    assert reference == expected_reference
    assert mutation.calls == [
        (
            "wall.post",
            {
                "owner_id": module.OWNER_ID,
                "from_group": True,
                "message": operation["message"],
                "attachments": "photo-60805374_99",
                "publish_date": operation["publish_date"],
                "guid": operation["operation_id"],
            },
        )
    ]
    assert operation["url"] in operation["message"]
    assert journal["operations"][operation["operation_id"]]["stage"] == "verified"


def test_explicit_wall_post_rejection_keeps_photo_for_safe_resume(
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    rejection = module.VkApiError(
        "rejected",
        method="wall.post",
        code=100,
        retryable=False,
    )
    mutation = FakeClient({"wall.post": rejection})

    with pytest.raises(RuntimeError, match="wall_post_rejected"):
        module.submit_wall_post(
            operation=operation,
            photo_token_value="photo-60805374_99",
            read_client=FakeClient(),
            mutation_client=mutation,
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )

    entry = journal["operations"][operation["operation_id"]]
    assert entry["stage"] == "wall_post_rejected"
    assert entry["photo_token"] == "photo-60805374_99"


def test_read_and_mutation_clients_have_different_retry_contracts() -> None:
    source = implementation_source()

    assert "max_attempts=4" in source
    assert "max_attempts=1" in source
    assert '"photos.getWallUploadServer"' in source
    assert '"photos.saveWallPhoto"' in source
    assert '"wall.post"' in source


def test_no_destructive_or_editing_vk_methods_exist() -> None:
    source = implementation_source()

    forbidden = [
        '"wall.delete"',
        '"wall.edit"',
        '"wall.pin"',
        '"wall.unpin"',
        '"wall.repost"',
        '"photos.delete"',
    ]
    for method in forbidden:
        assert method not in source


def test_plan_branch_never_calls_execute_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = load_policy()
    output = tmp_path / "data" / "vk-wall" / module.DECISION_SET_ID
    policy_path = tmp_path / module.POLICY_PATH
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "external_urls_checked": 30,
        "article_pages_verified": 10,
        "source_images_verified": 10,
        "pinned_source_files_verified": 10,
        "manifest_sha256": "sha256:assets",
        "items": [
            {
                "operation_id": operation["operation_id"],
                "asset_path": str(tmp_path / f"{operation['operation_id']}.jpg"),
                "asset_sha256": "sha256:x",
                "asset_bytes": 1,
            }
            for operation in policy["operations"]
        ],
    }
    monkeypatch.setattr(
        module.workflow_module,
        "materialize_and_verify_sources",
        lambda *args, **kwargs: (manifest["items"], manifest),
    )
    monkeypatch.setattr(
        module.workflow_module,
        "get_settings",
        lambda: SimpleNamespace(
            data_dir=tmp_path / "data",
            vk_api_version="5.199",
        ),
    )

    class FakeVkClient:
        def __init__(self, **kwargs: object) -> None:
            self.max_attempts = kwargs["max_attempts"]

        def get_community(self, community: int) -> Any:
            assert community == module.COMMUNITY_ID
            return SimpleNamespace(
                ref=SimpleNamespace(remote_id=str(module.COMMUNITY_ID)),
                metadata={"managed_by_token": True},
            )

    monkeypatch.setattr(module.workflow_module, "VkApiClient", FakeVkClient)
    monkeypatch.setattr(
        module.workflow_module,
        "verify_upload_server",
        lambda client: {"verified": True, "upload_server_host": "upload.vk.test"},
    )
    monkeypatch.setattr(module.workflow_module, "wall_snapshot", lambda client: ([], []))
    monkeypatch.setattr(
        module.workflow_module,
        "preflight",
        lambda *args, **kwargs: {
            "total_operations": 10,
            "ready": 10,
            "already_applied": 0,
            "conflicts": 0,
            "global_conflicts": [],
            "postponed_wall_posts": 0,
            "minimum_gap_minutes": 120,
            "states": [
                {
                    "operation_id": operation["operation_id"],
                    "state": "ready",
                }
                for operation in policy["operations"]
            ],
        },
    )
    monkeypatch.setattr(
        module.workflow_module,
        "review_markdown",
        lambda policy, report: "# review\n",
    )
    monkeypatch.setattr(
        module.workflow_module,
        "execute_scope",
        lambda **kwargs: pytest.fail("Plan must not execute remote writes"),
    )

    assert module.workflow_module.run(tmp_path, mode="plan") == 0
    assert (output / "preflight.json").is_file()


def test_photo_uploaded_stage_resumes_at_save_without_reupload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    journal["operations"][operation["operation_id"]] = {
        "stage": "photo_uploaded",
        "upload_payload": {"photo": "[]", "server": 1, "hash": "h"},
    }
    read_client = FakeClient()
    mutation_client = FakeClient()
    monkeypatch.setattr(
        module.mutations_module,
        "saved_photo_token",
        lambda client, payload: "photo-60805374_321_key",
    )
    monkeypatch.setattr(
        module.mutations_module,
        "upload_photo_bytes",
        lambda *args, **kwargs: pytest.fail("prepared upload must be reused"),
    )

    token = module.prepare_photo_token(
        operation=operation,
        jpeg=b"\xff\xd8" + b"x" * 20_000 + b"\xff\xd9",
        read_client=read_client,
        mutation_client=mutation_client,
        journal=journal,
        journal_path=tmp_path / "journal.json",
    )

    assert token == "photo-60805374_321_key"
    assert read_client.calls == []
    assert journal["operations"][operation["operation_id"]]["stage"] == "photo_saved"


def test_unknown_wall_post_reconciles_exact_remote_effect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    ambiguous = module.VkApiError(
        "network timeout",
        method="wall.post",
        code=None,
        retryable=True,
    )
    mutation = FakeClient({"wall.post": ambiguous})
    reference = {
        "post_id": 812,
        "has_photo": True,
        "photo_tokens": ["photo-60805374_99"],
        "photo_identities": ["photo-60805374_99"],
    }
    monkeypatch.setattr(
        module.mutations_module,
        "find_exact_post",
        lambda *args, **kwargs: reference,
    )

    post_id, found = module.submit_wall_post(
        operation=operation,
        photo_token_value="photo-60805374_99_key",
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


def test_unknown_wall_post_without_remote_effect_blocks_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = load_policy()
    operation = policy["operations"][0]
    journal = module.fresh_journal(policy)
    ambiguous = module.VkApiError(
        "network timeout",
        method="wall.post",
        code=None,
        retryable=True,
    )
    mutation = FakeClient({"wall.post": ambiguous})
    monkeypatch.setattr(
        module.mutations_module,
        "find_exact_post",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(RuntimeError, match="wall_post_unknown"):
        module.submit_wall_post(
            operation=operation,
            photo_token_value="photo-60805374_99_key",
            read_client=FakeClient(),
            mutation_client=mutation,
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )

    entry = journal["operations"][operation["operation_id"]]
    assert entry["stage"] == "wall_post_unknown"
    report = module.preflight(
        policy,
        [],
        [],
        journal,
        minimum_future_seconds=-10**9,
    )
    assert report["states"][0]["state"] == "conflict"


def test_current_v3_has_no_dynamic_policy_rewrite_or_link_parser() -> None:
    source = implementation_source()

    assert "wall.parseAttachedLink" not in source
    assert "schedule_lord_god_article_wave.py" not in source
    assert "importlib" not in source
    assert "module.EXPECTED_SHA" not in source
    assert "explicit-wall-photo-plus-text-link" in source


def test_result_rows_do_not_expose_photo_access_keys() -> None:
    source = implementation_source()

    assert '"photo_token": photo,' not in source
    assert "photo_token=photo_token_value" in source
    assert "SCHEDULED" in source
    assert "photo=yes url=yes" in source
