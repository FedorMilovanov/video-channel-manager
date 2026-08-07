from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from video_channel_manager.telegram_presentation import render_post
from video_channel_manager.telegram_publisher import (
    TargetProof,
    dispatch_prepared,
    initialize_ledger,
    load_queue,
    prepare_next,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/verified-30-posts.json"
GITHUB_SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def _target(*, checked_at: datetime) -> TargetProof:
    return TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=42,
        bot_username="lordchrist_publisher_bot",
        chat_id=-1001234567890,
        chat_username="lordchrist",
        chat_title="Господь Бог — Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=checked_at,
    )


def _prepared(now: datetime):
    queue = load_queue(QUEUE_PATH)
    ledger = initialize_ledger(queue)
    result = prepare_next(
        queue,
        ledger,
        run_id="12345",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=_target(checked_at=now),
        expected_publication_id=queue.posts[0].publication_id,
        now=now,
    )
    assert result.envelope is not None
    return queue, ledger, result.envelope


def test_formatted_transport_sends_html_and_verifies_returned_entities() -> None:
    now = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)
    queue, ledger, envelope = _prepared(now)
    rendered = render_post(queue.posts[0])
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendMessage")
        payload = json.loads(request.content.decode("utf-8"))
        captured_payload.update(payload)
        entities = [entity.model_dump(mode="json") for entity in rendered.expected_entities]
        entities.append({"type": "hashtag", "offset": 9999, "length": 10})
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 778,
                    "chat": {
                        "id": envelope.target.chat_id,
                        "username": "lordchrist",
                        "type": "channel",
                    },
                    "text": rendered.text,
                    "entities": entities,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        entry = dispatch_prepared(
            queue,
            envelope,
            ledger,
            token="secret",
            rendered=rendered,
            api_base="https://api.telegram.test",
            client=client,
            now=now + timedelta(minutes=1),
        )

    assert captured_payload["chat_id"] == envelope.target.chat_id
    assert captured_payload["text"] == rendered.html_text
    assert captured_payload["parse_mode"] == "HTML"
    assert captured_payload["link_preview_options"] == {"is_disabled": True}
    assert "© " not in str(captured_payload["text"])
    assert "<b>Джон Беньян</b>" in str(captured_payload["text"])
    assert "<i>«Путешествие Пилигрима»</i>" in str(captured_payload["text"])
    assert entry.state == "published"
    assert entry.provider_effect == "verified"
    assert entry.message_id == 778


def test_formatted_transport_entity_mismatch_is_unknown_may_exist() -> None:
    now = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)
    queue, ledger, envelope = _prepared(now)
    rendered = render_post(queue.posts[0])

    def handler(request: httpx.Request) -> httpx.Response:
        entities = [entity.model_dump(mode="json") for entity in rendered.expected_entities]
        entities[0]["length"] += 1
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 779,
                    "chat": {
                        "id": envelope.target.chat_id,
                        "username": "lordchrist",
                        "type": "channel",
                    },
                    "text": rendered.text,
                    "entities": entities,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        entry = dispatch_prepared(
            queue,
            envelope,
            ledger,
            token="secret",
            rendered=rendered,
            api_base="https://api.telegram.test",
            client=client,
            now=now + timedelta(minutes=1),
        )

    assert entry.state == "unknown"
    assert entry.provider_effect == "may_exist"
    assert entry.message_id is None
    assert "formatting entities" in (entry.last_error or "")


def test_formatted_transport_plain_text_mismatch_is_unknown_may_exist() -> None:
    now = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)
    queue, ledger, envelope = _prepared(now)
    rendered = render_post(queue.posts[0])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 780,
                    "chat": {
                        "id": envelope.target.chat_id,
                        "username": "lordchrist",
                        "type": "channel",
                    },
                    "text": rendered.text + " изменено",
                    "entities": [entity.model_dump(mode="json") for entity in rendered.expected_entities],
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        entry = dispatch_prepared(
            queue,
            envelope,
            ledger,
            token="secret",
            rendered=rendered,
            api_base="https://api.telegram.test",
            client=client,
            now=now + timedelta(minutes=1),
        )

    assert entry.state == "unknown"
    assert entry.provider_effect == "may_exist"
    assert entry.message_id is None
    assert "plain text" in (entry.last_error or "")


def test_production_workflow_persists_rendered_evidence_before_send() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/lordchrist-telegram-poster.yml").read_text(encoding="utf-8")

    render_index = workflow.index("- name: Render exact Telegram provider payload")
    persist_index = workflow.index("- name: Persist intent and rendered payload before sendMessage")
    send_index = workflow.index("- name: Send exactly one prepared message")
    assert render_index < persist_index < send_index
    assert "content/telegram/lordchrist/dispatches/$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT" in workflow
    assert 'cp -- "$DISPATCH_PATH" "$evidence_abs_dir/dispatch.json"' in workflow
    assert 'cp -- "$RENDERED_PATH" "$evidence_abs_dir/rendered.json"' in workflow
    assert 'cmp -s "$RENDERED_PATH" .runtime/remote-rendered.json' in workflow
    assert "verify-rendered" in workflow
    assert '--rendered "$RENDERED_PATH"' in workflow
    assert "if: steps.persist_intent.outputs.persisted == 'true'" in workflow
