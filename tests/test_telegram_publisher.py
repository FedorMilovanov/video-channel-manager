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
    load_or_initialize_ledger,
    load_queue,
    prepare_next,
    preflight_target,
    publication_local_date,
    require_execution_enabled,
    resolve_entry,
    verify_persisted_intent,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/verified-30-posts.json"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/lordchrist-telegram-poster.yml"
EXPECTED_QUEUE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"


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
        schema_version=1,
        bot_id=bot_id,
        bot_username="lordchrist_publisher_bot",
        chat_id=chat_id,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=checked_at or datetime.now(tz=UTC),
    )


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


def test_queue_rejects_non_contiguous_or_unaccepted_source_proof() -> None:
    payload = queue_payload()
    first = payload["posts"][0]  # type: ignore[index]
    first["source"]["selection_policy"] = "abridged"  # type: ignore[index]
    with pytest.raises(ValidationError):
        TelegramQueue.model_validate(payload)

    payload = queue_payload()
    first = payload["posts"][0]  # type: ignore[index]
    first["source"]["verification_status"] = "pending"  # type: ignore[index]
    with pytest.raises(ValidationError):
        TelegramQueue.model_validate(payload)


def test_queue_digest_covers_source_proof_and_translation_payload() -> None:
    first = TelegramQueue.model_validate(queue_payload())

    changed_source = queue_payload()
    changed_source["posts"][0]["source"]["location"] = "Другое место"  # type: ignore[index]
    assert TelegramQueue.model_validate(changed_source).digest != first.digest

    changed_text = queue_payload()
    changed_text["posts"][0]["text"] = str(changed_text["posts"][0]["text"]).replace(  # type: ignore[index]
        "едва Христианин", "как только Христианин", 1
    )
    assert TelegramQueue.model_validate(changed_text).digest != first.digest


def test_ledger_is_bound_to_immutable_queue_digest_and_payloads(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger_path = tmp_path / "ledger.json"
    ledger = load_or_initialize_ledger(ledger_path, queue)
    ledger_path.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")

    changed = deepcopy(queue_payload())
    changed["posts"][0]["title"] = "Изменённый заголовок"  # type: ignore[index]
    with pytest.raises(ValueError, match="queue digest"):
        load_or_initialize_ledger(ledger_path, TelegramQueue.model_validate(changed))


def test_strict_order_blocks_failed_dispatching_or_unknown_first_item(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    for blocked_state in ("failed", "dispatching", "unknown"):
        ledger = load_or_initialize_ledger(tmp_path / f"{blocked_state}.json", queue)
        ledger.entries[queue.posts[0].publication_id].state = blocked_state  # type: ignore[assignment]
        result = prepare_next(queue, ledger, run_id="2", mode="manual", target=target())
        assert result.envelope is None
        assert "strict queue blocked" in result.reason


def test_scheduled_mode_requires_exact_verified_manual_canary(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    now = datetime(2026, 8, 6, 6, 17, tzinfo=UTC)

    result = prepare_next(queue, ledger, run_id="1", mode="scheduled", target=target(checked_at=now), now=now)
    assert result.envelope is None
    assert "manual canary" in result.reason

    first = ledger.entries[queue.posts[0].publication_id]
    first.state = "published"
    first.provider_effect = "verified"
    first.dispatch_mode = "manual"
    first.message_id = 101
    first.actual_chat_id = target().chat_id
    first.bot_id = target().bot_id
    first.published_at_utc = now - timedelta(days=1)

    result = prepare_next(queue, ledger, run_id="2", mode="scheduled", target=target(checked_at=now), now=now)
    assert result.envelope is not None
    assert result.envelope.publication_id == queue.posts[1].publication_id


def test_manual_canary_from_another_bot_or_chat_is_rejected(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    now = datetime(2026, 8, 6, 6, 17, tzinfo=UTC)
    first = ledger.entries[queue.posts[0].publication_id]
    first.state = "published"
    first.provider_effect = "verified"
    first.dispatch_mode = "manual"
    first.message_id = 101
    first.actual_chat_id = -1009999999999
    first.bot_id = 999
    first.published_at_utc = now - timedelta(days=1)

    result = prepare_next(queue, ledger, run_id="2", mode="scheduled", target=target(checked_at=now), now=now)
    assert result.envelope is None
    assert "manual canary" in result.reason


def test_scheduled_mode_allows_at_most_one_verified_post_per_moscow_date(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    now = datetime(2026, 8, 6, 18, 17, tzinfo=UTC)  # 21:17 Moscow

    first = ledger.entries[queue.posts[0].publication_id]
    first.state = "published"
    first.provider_effect = "verified"
    first.dispatch_mode = "manual"
    first.message_id = 101
    first.actual_chat_id = target().chat_id
    first.bot_id = target().bot_id
    first.published_at_utc = datetime(2026, 8, 6, 6, 17, tzinfo=UTC)  # 09:17 Moscow

    guarded = prepare_next(queue, ledger, run_id="2", mode="scheduled", target=target(checked_at=now), now=now)
    assert guarded.envelope is None
    assert "already verified" in guarded.reason

    tomorrow = now + timedelta(days=1)
    allowed = prepare_next(
        queue, ledger, run_id="3", mode="scheduled", target=target(checked_at=tomorrow), now=tomorrow
    )
    assert allowed.envelope is not None
    assert allowed.envelope.publication_id == queue.posts[1].publication_id


def test_publication_date_uses_moscow_timezone() -> None:
    assert publication_local_date(datetime(2026, 8, 5, 21, 30, tzinfo=UTC)) == date(2026, 8, 6)


def test_preflight_verifies_exact_bot_channel_and_post_permission() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getMe":
            result = {"id": 42, "username": "lordchrist_publisher_bot"}
        elif method == "getChat":
            result = {"id": -1001234567890, "username": "lordchrist", "title": "Господь Бог — Сила Моя"}
        else:
            result = {"status": "administrator", "can_post_messages": True}
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        proof = preflight_target(
            token="secret",
            expected_chat_id=-1001234567890,
            expected_bot_username="lordchrist_publisher_bot",
            api_base="https://api.telegram.test",
            client=client,
            now=datetime(2026, 8, 6, 9, 0, tzinfo=UTC),
        )
    assert proof.bot_id == 42
    assert proof.chat_id == -1001234567890
    assert proof.chat_username == "lordchrist"
    assert proof.can_post_messages is True


def test_preflight_rejects_identity_or_permission_mismatch() -> None:
    def wrong_chat(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getMe":
            result = {"id": 42, "username": "lordchrist_publisher_bot"}
        elif method == "getChat":
            result = {"id": -1001111111111, "username": "another", "title": "Wrong"}
        else:
            result = {"status": "member"}
        return httpx.Response(200, json={"ok": True, "result": result})

    with httpx.Client(transport=httpx.MockTransport(wrong_chat)) as client:
        with pytest.raises(TelegramApiError, match="identity"):
            preflight_target(
                token="secret",
                expected_chat_id=-1001234567890,
                expected_bot_username="lordchrist_publisher_bot",
                api_base="https://api.telegram.test",
                client=client,
            )


def test_preflight_transport_error_is_not_dispatched_and_never_leaks_token() -> None:
    token = "123456:SUPER-SECRET"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError) as captured:
            preflight_target(
                token=token,
                expected_chat_id=-1001234567890,
                expected_bot_username="lordchrist_publisher_bot",
                api_base="https://api.telegram.test",
                client=client,
            )
    assert captured.value.provider_effect == "not_dispatched"
    assert token not in str(captured.value)
    assert "api.telegram.test" not in str(captured.value)


def test_prepare_persists_conservative_may_exist_intent_before_dispatch(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run-1", mode="manual", target=target())
    assert prepared.envelope is not None
    entry = ledger.entries[prepared.envelope.publication_id]
    assert entry.state == "dispatching"
    assert entry.provider_effect == "may_exist"
    assert entry.intent_id == prepared.envelope.intent_id
    assert entry.workflow_run_id == "run-1"


def test_read_timeout_after_send_becomes_unknown_without_secret_leak(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run", mode="manual", target=target())
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
    assert prepare_next(queue, ledger, run_id="retry", mode="manual", target=target()).envelope is None


def test_success_requires_exact_returned_chat_text_and_positive_message_id(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run", mode="manual", target=target())
    assert prepared.envelope is not None

    def success(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 777,
                    "chat": {"id": target().chat_id, "username": "lordchrist"},
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
    assert entry.actual_chat_id == target().chat_id


def test_mismatched_returned_message_stays_unknown(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run", mode="manual", target=target())
    assert prepared.envelope is not None

    def mismatch(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 777,
                    "chat": {"id": -1009999999999, "username": "wrong"},
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


def test_manual_reconciliation_requires_concrete_evidence(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run", mode="manual", target=target())
    assert prepared.envelope is not None
    ledger.entries[prepared.envelope.publication_id].state = "unknown"

    with pytest.raises(ValueError, match="evidence note"):
        resolve_entry(
            ledger,
            prepared.envelope.publication_id,
            resolution="confirmed_published",
            evidence_note="видел",
            resolved_by="FedorMilovanov",
            message_id=777,
            expected_chat_id=target().chat_id,
        )

    resolved = resolve_entry(
        ledger,
        prepared.envelope.publication_id,
        resolution="confirmed_published",
        evidence_note="Пост открыт в публичном канале, текст сверен, message_id 777 зафиксирован.",
        resolved_by="FedorMilovanov",
        message_id=777,
        expected_chat_id=target().chat_id,
    )
    assert resolved.state == "published"
    assert resolved.provider_effect == "verified"
    assert resolved.message_id == 777


def test_confirmed_absent_is_the_only_resolution_that_reopens_pending(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run", mode="manual", target=target())
    assert prepared.envelope is not None
    ledger.entries[prepared.envelope.publication_id].state = "unknown"

    entry = resolve_entry(
        ledger,
        prepared.envelope.publication_id,
        resolution="confirmed_absent",
        evidence_note="Канал проверен вручную по соседним message_id; публикация подтверждённо отсутствует.",
        resolved_by="FedorMilovanov",
    )
    assert entry.state == "pending"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None


def test_execution_gate_requires_enabled_exact_digest_and_separate_schedule_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = load_queue(QUEUE_PATH)
    monkeypatch.delenv("LORDCHRIST_POSTING_ENABLED", raising=False)
    monkeypatch.delenv("LORDCHRIST_APPROVED_QUEUE_DIGEST", raising=False)
    monkeypatch.delenv("LORDCHRIST_SCHEDULE_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="provider execution is disabled"):
        require_execution_enabled(queue_digest=queue.digest, mode="manual")

    monkeypatch.setenv("LORDCHRIST_POSTING_ENABLED", "true")
    monkeypatch.setenv("LORDCHRIST_APPROVED_QUEUE_DIGEST", "sha256:wrong")
    with pytest.raises(RuntimeError, match="digest"):
        require_execution_enabled(queue_digest=queue.digest, mode="manual")

    monkeypatch.setenv("LORDCHRIST_APPROVED_QUEUE_DIGEST", queue.digest)
    require_execution_enabled(queue_digest=queue.digest, mode="manual")
    with pytest.raises(RuntimeError, match="scheduled execution is disabled"):
        require_execution_enabled(queue_digest=queue.digest, mode="scheduled")

    monkeypatch.setenv("LORDCHRIST_SCHEDULE_ENABLED", "true")
    require_execution_enabled(queue_digest=queue.digest, mode="scheduled")


def test_workflow_uses_separate_state_branch_and_fifo_concurrency() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "queue: max" in workflow
    assert "state/lordchrist-telegram" in workflow
    assert "LORDCHRIST_SCHEDULE_ENABLED" in workflow
    assert "HEAD:main" not in workflow
    assert "publication-ledger.json" in workflow
    assert "Persist intent before sendMessage" in workflow


def test_verified_corpus_has_only_the_approved_primary_source_author_set() -> None:
    from collections import Counter

    queue = load_queue(QUEUE_PATH)
    assert Counter(post.source.author for post in queue.posts) == Counter(
        {
            "Джон Беньян": 5,
            "Чарльз Сперджен": 5,
            "Жан Кальвин": 5,
            "Джон Оуэн": 5,
            "Томас Уотсон": 5,
            "Джонатан Эдвардс": 3,
            "Джон Гилл": 2,
        }
    )
    assert all(post.source.anchor_start != post.source.anchor_end for post in queue.posts)
    assert all(len(post.source.anchor_start.split()) <= 28 for post in queue.posts)
    assert all(len(post.source.anchor_end.split()) <= 28 for post in queue.posts)


def test_dispatch_envelope_cannot_change_text_sequence_or_queue_digest(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run", mode="manual", target=target())
    assert prepared.envelope is not None

    for update in (
        {"text": prepared.envelope.text + "\nподмена"},
        {"sequence": prepared.envelope.sequence + 1},
        {"queue_digest": "sha256:wrong"},
        {"workflow_run_id": "other-run"},
    ):
        tampered = prepared.envelope.model_copy(update=update)
        with pytest.raises(ValueError):
            verify_persisted_intent(queue, ledger, tampered)


def test_stale_target_proof_is_rejected_before_intent_creation(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    now = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    stale = target(checked_at=now - timedelta(minutes=16))
    with pytest.raises(ValueError, match="stale"):
        prepare_next(queue, ledger, run_id="run", mode="manual", target=stale, now=now)
    assert all(entry.state == "pending" for entry in ledger.entries.values())


def test_explicit_telegram_rejection_is_confirmed_absent_not_unknown(tmp_path: Path) -> None:
    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    prepared = prepare_next(queue, ledger, run_id="run", mode="manual", target=target())
    assert prepared.envelope is not None

    def rejected(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "Bad Request: message is too long"})

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


def test_save_ledger_refuses_internally_inconsistent_published_state(tmp_path: Path) -> None:
    from video_channel_manager.telegram_publisher import save_ledger

    queue = load_queue(QUEUE_PATH)
    ledger = load_or_initialize_ledger(tmp_path / "ledger.json", queue)
    entry = ledger.entries[queue.posts[0].publication_id]
    entry.state = "published"
    entry.provider_effect = "verified"
    with pytest.raises(ValidationError, match="message_id"):
        save_ledger(tmp_path / "ledger.json", ledger)
