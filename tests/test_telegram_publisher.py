from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_publisher import (
    TelegramApiError,
    TelegramQueue,
    TargetProof,
    dispatch_prepared,
    initialize_ledger,
    initialize_ledger_file,
    load_ledger,
    load_queue,
    prepare_next,
    preflight_target,
    preview_next,
    publication_local_date,
    require_execution_enabled,
    require_preflight_config,
    resolve_entry,
    save_ledger,
    verify_persisted_intent,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/verified-30-posts.json"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
CI_PATH = REPOSITORY_ROOT / ".github/workflows/ci.yml"
RUNTIME_REQUIREMENTS = REPOSITORY_ROOT / "requirements/telegram-publisher.txt"
EXPECTED_QUEUE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
GITHUB_SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def queue_payload() -> dict[str, object]:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def target(
    *,
    bot_id: int = 42,
    chat_id: int = -1001234567890,
    checked_at: datetime | None = None,
) -> TargetProof:
    return TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=bot_id,
        bot_username="lordchrist_publisher_bot",
        chat_id=chat_id,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=checked_at or datetime.now(tz=UTC),
    )


def prepare_manual(
    queue: TelegramQueue,
    ledger: object,
    *,
    now: datetime | None = None,
    publication_id: str | None = None,
):
    exact_id = publication_id or queue.posts[0].publication_id
    return prepare_next(
        queue,
        ledger,  # type: ignore[arg-type]
        run_id="12345",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target(checked_at=now),
        expected_publication_id=exact_id,
        now=now,
    )


def mark_published(
    entry: object,
    *,
    published_at: datetime,
    mode: str = "manual",
    chat_id: int = -1001234567890,
    bot_id: int = 42,
    message_id: int = 101,
) -> None:
    entry.state = "published"  # type: ignore[attr-defined]
    entry.provider_effect = "verified"  # type: ignore[attr-defined]
    entry.dispatch_mode = mode  # type: ignore[attr-defined]
    entry.message_id = message_id  # type: ignore[attr-defined]
    entry.message_url = f"https://t.me/lordchrist/{message_id}"  # type: ignore[attr-defined]
    entry.actual_chat_id = chat_id  # type: ignore[attr-defined]
    entry.actual_chat_username = "lordchrist"  # type: ignore[attr-defined]
    entry.bot_id = bot_id  # type: ignore[attr-defined]
    entry.bot_username = "lordchrist_publisher_bot"  # type: ignore[attr-defined]
    entry.published_at_utc = published_at  # type: ignore[attr-defined]


def test_repository_queue_is_exactly_thirty_primary_public_domain_passages() -> None:
    queue = load_queue(QUEUE_PATH)
    assert len(queue.posts) == 30
    assert queue.digest == EXPECTED_QUEUE_DIGEST
    assert [post.sequence for post in queue.posts] == list(range(1, 31))
    assert all(post.source.source_type == "primary" for post in queue.posts)
    assert all(post.source.copyright_status == "public_domain" for post in queue.posts)
    assert all(post.source.selection_policy == "contiguous_complete_no_omissions" for post in queue.posts)
    assert all(post.source.verification_status == "accepted" for post in queue.posts)
    assert all(post.source.verified_on == date(2026, 8, 6) for post in queue.posts)
    assert max(len(post.text) for post in queue.posts) <= 4096


def test_every_repository_post_has_two_or_three_dense_quote_paragraphs() -> None:
    queue = load_queue(QUEUE_PATH)
    for post in queue.posts:
        blocks = post.text.split("\n\n")
        quote_paragraphs = blocks[:-2]
        assert 2 <= len(quote_paragraphs) <= 3, post.publication_id
        assert all(len(paragraph) >= 80 for paragraph in quote_paragraphs), post.publication_id
        assert blocks[-2] == f"© {post.source.author}, «{post.source.work}»"
        assert blocks[-1].startswith("#")


def test_queue_rejects_reserve_editorial_composite_and_secondary_material() -> None:
    for forbidden in ("Резерв", "Контекст редактора", "Пересказ", "Синтез", "GraceGems"):
        payload = queue_payload()
        first = payload["posts"][0]  # type: ignore[index]
        first["text"] = str(first["text"]).replace("И увидел", f"{forbidden}: И увидел", 1)  # type: ignore[index]
        with pytest.raises(ValidationError):
            TelegramQueue.model_validate(payload)

    payload = queue_payload()
    first = payload["posts"][0]  # type: ignore[index]
    first["source"]["url"] = "https://www.gracegems.org/example.html"  # type: ignore[index]
    with pytest.raises(ValidationError):
        TelegramQueue.model_validate(payload)


def test_queue_digest_covers_source_proof_and_translation_payload() -> None:
    original = TelegramQueue.model_validate(queue_payload())

    changed_source = queue_payload()
    changed_source["posts"][0]["source"]["location"] = "Другое место"  # type: ignore[index]
    assert TelegramQueue.model_validate(changed_source).digest != original.digest

    changed_text = queue_payload()
    changed_text["posts"][0]["text"] = str(changed_text["posts"][0]["text"]).replace(  # type: ignore[index]
        "едва Христианин", "как только Христианин", 1
    )
    assert TelegramQueue.model_validate(changed_text).digest != original.digest


def test_production_ledger_missing_is_fatal_and_never_auto_initialized(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger_path = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="must never be auto-initialized"):
        load_ledger(ledger_path, queue)
    assert not ledger_path.exists()


def test_explicit_ledger_initialization_is_complete_and_refuses_overwrite(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger_path = tmp_path / "ledger.json"
    ledger = initialize_ledger_file(ledger_path, queue)
    assert len(ledger.entries) == 30
    assert set(ledger.entries) == {post.publication_id for post in queue.posts}
    with pytest.raises(ValueError, match="refusing to overwrite"):
        initialize_ledger_file(ledger_path, queue)


def test_production_ledger_rejects_missing_or_extra_publication(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)

    missing = deepcopy(ledger.model_dump(mode="json"))
    missing["entries"].pop(queue.posts[0].publication_id)
    missing_path = tmp_path / "missing-entry.json"
    missing_path.write_text(json.dumps(missing), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage"):
        load_ledger(missing_path, queue)

    extra = deepcopy(ledger.model_dump(mode="json"))
    extra["entries"]["lordchrist-impossible-extra"] = {
        "publication_id": "lordchrist-impossible-extra",
        "payload_sha256": "sha256:extra",
        "state": "pending",
        "provider_effect": "impossible",
    }
    extra_path = tmp_path / "extra-entry.json"
    extra_path.write_text(json.dumps(extra), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage"):
        load_ledger(extra_path, queue)


def test_ledger_rejects_queue_or_payload_drift(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    path = tmp_path / "ledger.json"
    save_ledger(path, ledger)

    changed = deepcopy(queue_payload())
    changed["posts"][0]["title"] = "Изменённый заголовок"  # type: ignore[index]
    with pytest.raises(ValueError, match="queue digest"):
        load_ledger(path, TelegramQueue.model_validate(changed))

    payload = ledger.model_dump(mode="json")
    payload["entries"][queue.posts[0].publication_id]["payload_sha256"] = "sha256:wrong"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="payload changed"):
        load_ledger(path, queue)


def test_preview_is_strict_order_and_does_not_mutate_ledger() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    before = ledger.model_dump(mode="json")
    preview = preview_next(queue, ledger)
    assert preview.envelope is None
    assert preview.post is not None
    assert preview.post.publication_id == queue.posts[0].publication_id
    assert ledger.model_dump(mode="json") == before


def test_strict_order_blocks_failed_dispatching_or_unknown_first_item() -> None:
    queue = load_queue(QUEUE_PATH)
    for blocked_state, provider_effect in (
        ("failed", "confirmed_absent"),
        ("dispatching", "may_exist"),
        ("unknown", "may_exist"),
    ):
        ledger = initialize_ledger(queue)
        entry = ledger.entries[queue.posts[0].publication_id]
        entry.state = blocked_state  # type: ignore[assignment]
        entry.provider_effect = provider_effect  # type: ignore[assignment]
        if blocked_state in {"dispatching", "unknown"}:
            entry.intent_id = "intent"
            entry.workflow_run_id = "run"
            entry.workflow_run_attempt = "1"
            entry.github_sha = GITHUB_SHA
            entry.github_workflow_sha = WORKFLOW_SHA
            entry.actual_chat_id = target().chat_id
            entry.actual_chat_username = "lordchrist"
            entry.bot_id = target().bot_id
            entry.bot_username = target().bot_username
        result = prepare_manual(queue, ledger)
        assert result.envelope is None
        assert "strict queue blocked" in result.reason


def test_manual_publish_requires_exact_current_publication_id() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)

    missing = prepare_next(
        queue,
        ledger,
        run_id="1",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target(),
    )
    assert missing.envelope is None
    assert "requires an exact publication_id" in missing.reason

    mismatch = prepare_manual(queue, ledger, publication_id=queue.posts[1].publication_id)
    assert mismatch.envelope is None
    assert "mismatch" in mismatch.reason

    exact = prepare_manual(queue, ledger)
    assert exact.envelope is not None
    assert exact.envelope.publication_id == queue.posts[0].publication_id


def test_stale_manual_rerun_cannot_advance_to_the_next_post() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    yesterday = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
    mark_published(ledger.entries[queue.posts[0].publication_id], published_at=yesterday)

    today = yesterday + timedelta(days=1)
    stale = prepare_next(
        queue,
        ledger,
        run_id="old-run",
        run_attempt="2",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target(checked_at=today),
        expected_publication_id=queue.posts[0].publication_id,
        now=today,
    )
    assert stale.envelope is None
    assert queue.posts[1].publication_id in stale.reason
    assert "mismatch" in stale.reason


def test_daily_guard_applies_to_manual_and_scheduled_modes() -> None:
    queue = load_queue(QUEUE_PATH)
    now = datetime(2026, 8, 6, 18, 17, tzinfo=UTC)

    for mode in ("manual", "scheduled"):
        ledger = initialize_ledger(queue)
        mark_published(
            ledger.entries[queue.posts[0].publication_id],
            published_at=datetime(2026, 8, 6, 6, 17, tzinfo=UTC),
        )
        result = prepare_next(
            queue,
            ledger,
            run_id="2",
            run_attempt="1",
            github_sha=GITHUB_SHA,
            github_workflow_sha=WORKFLOW_SHA,
            mode=mode,  # type: ignore[arg-type]
            target=target(checked_at=now),
            expected_publication_id=queue.posts[1].publication_id if mode == "manual" else None,
            now=now,
        )
        assert result.envelope is None
        assert "already verified" in result.reason


def test_scheduled_mode_requires_verified_manual_canary_for_same_bot_and_chat() -> None:
    queue = load_queue(QUEUE_PATH)
    now = datetime(2026, 8, 7, 6, 17, tzinfo=UTC)
    ledger = initialize_ledger(queue)

    without = prepare_next(
        queue,
        ledger,
        run_id="1",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=target(checked_at=now),
        now=now,
    )
    assert without.envelope is None
    assert "manual canary" in without.reason

    mark_published(
        ledger.entries[queue.posts[0].publication_id],
        published_at=now - timedelta(days=1),
    )
    allowed = prepare_next(
        queue,
        ledger,
        run_id="2",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=target(checked_at=now),
        now=now,
    )
    assert allowed.envelope is not None
    assert allowed.envelope.publication_id == queue.posts[1].publication_id

    other = initialize_ledger(queue)
    mark_published(
        other.entries[queue.posts[0].publication_id],
        published_at=now - timedelta(days=1),
        chat_id=-1009999999999,
        bot_id=999,
    )
    rejected = prepare_next(
        queue,
        other,
        run_id="3",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=target(checked_at=now),
        now=now,
    )
    assert rejected.envelope is None
    assert "manual canary" in rejected.reason


def test_publication_date_uses_moscow_timezone() -> None:
    assert publication_local_date(datetime(2026, 8, 5, 21, 30, tzinfo=UTC)) == date(2026, 8, 6)


def test_preflight_uses_exact_bot_channel_and_admin_list_without_get_chat_member() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        calls.append((method, payload))
        if method == "getMe":
            result: object = {"id": 42, "username": "lordchrist_publisher_bot", "is_bot": True}
        elif method == "getChat":
            result = {
                "id": -1001234567890,
                "username": "lordchrist",
                "title": "Господь Бог — Сила Моя",
                "type": "channel",
            }
        elif method == "getChatAdministrators":
            result = [
                {
                    "status": "administrator",
                    "can_post_messages": True,
                    "user": {"id": 42, "username": "lordchrist_publisher_bot", "is_bot": True},
                }
            ]
        elif method == "getChatMember":
            return httpx.Response(400, json={"ok": False, "description": "Bad Request: member list is inaccessible"})
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        proof = preflight_target(
            token="secret",
            expected_chat_id=-1001234567890,
            expected_bot_id=42,
            expected_bot_username="lordchrist_publisher_bot",
            api_base="https://api.telegram.test",
            client=client,
            now=datetime(2026, 8, 6, 9, 0, tzinfo=UTC),
        )

    assert proof.bot_id == 42
    assert proof.chat_id == -1001234567890
    assert proof.chat_type == "channel"
    assert proof.can_post_messages is True
    assert [method for method, _ in calls] == ["getMe", "getChat", "getChat", "getChatAdministrators"]
    assert calls[-1][1]["return_bots"] is True


def test_preflight_rejects_bot_id_username_channel_type_and_permissions() -> None:
    scenarios = (
        ({"id": 99, "username": "lordchrist_publisher_bot", "is_bot": True}, "bot id"),
        ({"id": 42, "username": "wrong_bot", "is_bot": True}, "bot username"),
    )

    for me_result, expected_error in scenarios:

        def handler(request: httpx.Request, result: dict[str, object] = me_result) -> httpx.Response:
            method = request.url.path.rsplit("/", 1)[-1]
            if method == "getMe":
                return httpx.Response(200, json={"ok": True, "result": result})
            raise AssertionError("identity mismatch must fail before channel calls")

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(TelegramApiError, match=expected_error):
                preflight_target(
                    token="secret",
                    expected_chat_id=-1001234567890,
                    expected_bot_id=42,
                    expected_bot_username="lordchrist_publisher_bot",
                    api_base="https://api.telegram.test",
                    client=client,
                )

    def wrong_type(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getMe":
            result: object = {"id": 42, "username": "lordchrist_publisher_bot", "is_bot": True}
        else:
            result = {"id": -1001234567890, "username": "lordchrist", "title": "Wrong", "type": "supergroup"}
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(wrong_type)) as client:
        with pytest.raises(TelegramApiError, match="not a channel"):
            preflight_target(
                token="secret",
                expected_chat_id=-1001234567890,
                expected_bot_id=42,
                expected_bot_username="lordchrist_publisher_bot",
                api_base="https://api.telegram.test",
                client=client,
            )

    def no_permission(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getMe":
            result: object = {"id": 42, "username": "lordchrist_publisher_bot", "is_bot": True}
        elif method == "getChat":
            result = {
                "id": -1001234567890,
                "username": "lordchrist",
                "title": "Channel",
                "type": "channel",
            }
        else:
            result = [
                {
                    "status": "administrator",
                    "can_post_messages": False,
                    "user": {"id": 42, "username": "lordchrist_publisher_bot", "is_bot": True},
                }
            ]
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(no_permission)) as client:
        with pytest.raises(TelegramApiError, match="lacks can_post_messages"):
            preflight_target(
                token="secret",
                expected_chat_id=-1001234567890,
                expected_bot_id=42,
                expected_bot_username="lordchrist_publisher_bot",
                api_base="https://api.telegram.test",
                client=client,
            )


def test_preflight_transport_error_is_read_only_and_never_leaks_token() -> None:
    token = "123456:SUPER-SECRET"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError) as captured:
            preflight_target(
                token=token,
                expected_chat_id=-1001234567890,
                expected_bot_id=42,
                expected_bot_username="lordchrist_publisher_bot",
                api_base="https://api.telegram.test",
                client=client,
            )
    assert captured.value.provider_effect == "not_dispatched"
    assert token not in str(captured.value)
    assert "api.telegram.test" not in str(captured.value)


def test_prepare_persists_exact_provenance_before_dispatch() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None
    entry = ledger.entries[prepared.envelope.publication_id]
    assert entry.state == "dispatching"
    assert entry.provider_effect == "may_exist"
    assert entry.intent_id == prepared.envelope.intent_id
    assert entry.workflow_run_id == "12345"
    assert entry.workflow_run_attempt == "1"
    assert entry.github_sha == GITHUB_SHA
    assert entry.github_workflow_sha == WORKFLOW_SHA
    verify_persisted_intent(queue, ledger, prepared.envelope)


def test_read_timeout_after_send_becomes_unknown_and_blocks_replay() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None
    token = "123456:SUPER-SECRET"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lost response", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        entry = dispatch_prepared(
            queue,
            prepared.envelope,
            ledger,
            token=token,
            api_base="https://api.telegram.test",
            client=client,
        )
    assert entry.state == "unknown"
    assert entry.provider_effect == "may_exist"
    assert token not in (entry.last_error or "")

    retry = prepare_next(
        queue,
        ledger,
        run_id="retry",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target(),
        expected_publication_id=queue.posts[0].publication_id,
    )
    assert retry.envelope is None
    assert "strict queue blocked" in retry.reason


def test_connect_failure_is_safe_pending_and_retryable() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        entry = dispatch_prepared(
            queue,
            prepared.envelope,
            ledger,
            token="secret",
            api_base="https://api.telegram.test",
            client=client,
        )
    assert entry.state == "pending"
    assert entry.provider_effect == "not_dispatched"
    assert entry.intent_id is None


def test_telegram_429_is_confirmed_absent_and_safe_to_retry_later() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 5},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        entry = dispatch_prepared(
            queue,
            prepared.envelope,
            ledger,
            token="secret",
            api_base="https://api.telegram.test",
            client=client,
        )
    assert entry.state == "pending"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None


def test_success_requires_exact_returned_channel_text_and_message_id() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None

    def success(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 777,
                    "chat": {
                        "id": target().chat_id,
                        "username": "lordchrist",
                        "type": "channel",
                    },
                    "text": prepared.envelope.text,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(success)) as client:
        entry = dispatch_prepared(
            queue,
            prepared.envelope,
            ledger,
            token="secret",
            api_base="https://api.telegram.test",
            client=client,
            now=prepared.envelope.prepared_at_utc + timedelta(minutes=1),
        )
    assert entry.state == "published"
    assert entry.provider_effect == "verified"
    assert entry.message_id == 777
    assert entry.message_url == "https://t.me/lordchrist/777"


def test_mismatched_returned_message_stays_unknown() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None

    def mismatch(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 777,
                    "chat": {"id": -1009999999999, "username": "wrong", "type": "channel"},
                    "text": prepared.envelope.text,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(mismatch)) as client:
        entry = dispatch_prepared(
            queue,
            prepared.envelope,
            ledger,
            token="secret",
            api_base="https://api.telegram.test",
            client=client,
        )
    assert entry.state == "unknown"
    assert entry.provider_effect == "may_exist"


def test_explicit_terminal_telegram_rejection_is_failed_not_unknown() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None

    def rejected(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"ok": False, "error_code": 400, "description": "Bad Request: message is too long"},
        )

    with httpx.Client(transport=httpx.MockTransport(rejected)) as client:
        entry = dispatch_prepared(
            queue,
            prepared.envelope,
            ledger,
            token="secret",
            api_base="https://api.telegram.test",
            client=client,
        )
    assert entry.state == "failed"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None


def test_manual_reconciliation_requires_concrete_evidence_and_durable_target() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None
    entry = ledger.entries[prepared.envelope.publication_id]
    entry.state = "unknown"

    with pytest.raises(ValueError, match="evidence note"):
        resolve_entry(
            ledger,
            prepared.envelope.publication_id,
            resolution="confirmed_published",
            evidence_note="видел",
            resolved_by="operator",
            message_id=777,
            expected_chat_id=target().chat_id,
        )

    with pytest.raises(ValueError, match="differs from the durable dispatch target"):
        resolve_entry(
            ledger,
            prepared.envelope.publication_id,
            resolution="confirmed_published",
            evidence_note="Пост найден вручную и его идентичность тщательно сверена оператором.",
            resolved_by="operator",
            message_id=777,
            expected_chat_id=-1009999999999,
        )

    resolved = resolve_entry(
        ledger,
        prepared.envelope.publication_id,
        resolution="confirmed_published",
        evidence_note="Пост открыт в публичном канале, текст сверен и message_id подтверждён вручную.",
        resolved_by="operator",
        message_id=777,
        expected_chat_id=target().chat_id,
    )
    assert resolved.state == "published"
    assert resolved.message_url == "https://t.me/lordchrist/777"


def test_confirmed_absent_is_the_only_resolution_that_reopens_pending() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None
    ledger.entries[prepared.envelope.publication_id].state = "unknown"

    entry = resolve_entry(
        ledger,
        prepared.envelope.publication_id,
        resolution="confirmed_absent",
        evidence_note="Канал проверен вручную по соседним message_id; публикация подтверждённо отсутствует.",
        resolved_by="operator",
    )
    assert entry.state == "pending"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None


def test_preflight_gate_works_while_posting_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = load_queue(QUEUE_PATH)
    monkeypatch.setenv("LORDCHRIST_APPROVED_QUEUE_DIGEST", queue.digest)
    monkeypatch.setenv("LORDCHRIST_POSTING_ENABLED", "false")
    monkeypatch.setenv("LORDCHRIST_SCHEDULE_ENABLED", "false")
    require_preflight_config(queue_digest=queue.digest)
    with pytest.raises(RuntimeError, match="provider execution is disabled"):
        require_execution_enabled(queue_digest=queue.digest, mode="manual")


def test_execution_gate_requires_exact_digest_and_separate_schedule_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = load_queue(QUEUE_PATH)
    monkeypatch.delenv("LORDCHRIST_POSTING_ENABLED", raising=False)
    monkeypatch.delenv("LORDCHRIST_APPROVED_QUEUE_DIGEST", raising=False)
    monkeypatch.delenv("LORDCHRIST_SCHEDULE_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="digest"):
        require_execution_enabled(queue_digest=queue.digest, mode="manual")

    monkeypatch.setenv("LORDCHRIST_APPROVED_QUEUE_DIGEST", queue.digest)
    monkeypatch.setenv("LORDCHRIST_POSTING_ENABLED", "true")
    require_execution_enabled(queue_digest=queue.digest, mode="manual")
    with pytest.raises(RuntimeError, match="scheduled execution is disabled"):
        require_execution_enabled(queue_digest=queue.digest, mode="scheduled")

    monkeypatch.setenv("LORDCHRIST_SCHEDULE_ENABLED", "true")
    require_execution_enabled(queue_digest=queue.digest, mode="scheduled")


def test_dispatch_envelope_cannot_change_payload_or_github_provenance() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    prepared = prepare_manual(queue, ledger)
    assert prepared.envelope is not None

    for update in (
        {"text": prepared.envelope.text + "\nподмена"},
        {"sequence": prepared.envelope.sequence + 1},
        {"queue_digest": "sha256:wrong"},
        {"workflow_run_id": "other-run"},
        {"workflow_run_attempt": "2"},
        {"github_sha": "c" * 40},
        {"github_workflow_sha": "d" * 40},
    ):
        tampered = prepared.envelope.model_copy(update=update)
        with pytest.raises(ValueError):
            verify_persisted_intent(queue, ledger, tampered)


def test_stale_target_proof_and_expired_dispatch_are_rejected_before_send() -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    now = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="stale"):
        prepare_next(
            queue,
            ledger,
            run_id="run",
            run_attempt="1",
            github_sha=GITHUB_SHA,
            github_workflow_sha=WORKFLOW_SHA,
            mode="manual",
            target=target(checked_at=now - timedelta(minutes=16)),
            expected_publication_id=queue.posts[0].publication_id,
            now=now,
        )
    assert all(entry.state == "pending" for entry in ledger.entries.values())

    prepared = prepare_next(
        queue,
        ledger,
        run_id="run",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target(checked_at=now),
        expected_publication_id=queue.posts[0].publication_id,
        now=now,
    )
    assert prepared.envelope is not None
    with pytest.raises(ValueError, match="expired"):
        dispatch_prepared(
            queue,
            prepared.envelope,
            ledger,
            token="secret",
            api_base="https://api.telegram.test",
            client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
            now=now + timedelta(minutes=16),
        )


def test_save_ledger_refuses_internally_inconsistent_published_state(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    entry = ledger.entries[queue.posts[0].publication_id]
    entry.state = "published"
    entry.provider_effect = "verified"
    with pytest.raises(ValidationError, match="message_id"):
        save_ledger(tmp_path / "ledger.json", ledger)


def test_workflow_exposes_read_only_preflight_exact_manual_binding_and_single_queue() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    header = workflow.split("jobs:", maxsplit=1)[0]
    assert "queue: single" in workflow
    assert "- preflight" in workflow
    assert "LORDCHRIST_TELEGRAM_BOT_ID" in workflow
    assert 'expected_confirmation="PUBLISH:$REQUESTED_PUBLICATION_ID"' in workflow
    assert "--expected-publication-id" in workflow
    assert "$GITHUB_RUN_ATTEMPT" in workflow
    assert "github.workflow_sha" in workflow
    assert "push_exact_state" in workflow
    assert "requirements/telegram-publisher.txt" in workflow
    assert "state/lordchrist-telegram" in workflow
    assert "getChatMember" not in workflow
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in header
    assert workflow.count("${{ secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN }}") == 2


def test_ci_runs_branch_work_only_via_pull_request_to_avoid_duplicate_matrices() -> None:
    workflow = CI_PATH.read_text(encoding="utf-8")
    assert "      - main\n" in workflow
    assert '"agent/**"' not in workflow
    assert '"feature/**"' not in workflow
    assert '"integration/**"' not in workflow
    assert "pull_request:" in workflow


def test_minimal_telegram_runtime_is_exactly_pinned() -> None:
    requirements = RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    assert requirements
    assert all("==" in line for line in requirements if line.strip())
    assert "httpx==0.28.1" in requirements
    assert any(line.startswith("pydantic==") for line in requirements)
    assert all(not line.startswith(("sqlalchemy", "alembic", "typer", "rich")) for line in requirements)
