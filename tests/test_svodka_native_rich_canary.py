from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.svodka_native_rich_canary import (
    CONFIRMATION,
    EXPECTED_BOT_ID,
    EXPECTED_BOT_USERNAME,
    EXPECTED_CHANNEL_USERNAME,
    EXPECTED_CHAT_ID,
    EXPECTED_GITHUB_REF,
    EXPECTED_REPOSITORY,
    NativeRichCanaryIntent,
    NativeRichCanaryOutcomeState,
    build_document,
    build_future_edit_test_plan,
    dispatch_canary_once,
    finalize_outcome_state,
    load_canary_spec,
    load_canary_state,
    prepare_intent,
    prove_remote_media,
    require_exact_invocation,
    require_no_prior_state,
    write_model,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_rich_provider import (
    TelegramRichOutcomeArchiveReceipt,
    TelegramRichProviderResponse,
    TelegramRichProviderTimeout,
    TelegramRichRequestTimeout,
)
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
SPEC_PATH = ROOT / "content/telegram/svodka/native-rich-canary/canary-spec.json"
NOW = datetime(2026, 8, 10, 21, 15, tzinfo=UTC)
GITHUB_SHA = "a" * 40
WORKFLOW_RUN_ID = "31422000000"


class FakeProvider:
    def __init__(self, result: TelegramRichProviderResponse | Exception) -> None:
        self.result = result
        self.identity_calls = 0
        self.mutation_calls: list[dict[str, Any]] = []

    def get_me(self, *, timeout: TelegramRichRequestTimeout) -> TelegramRichProviderResponse:
        assert isinstance(timeout, TelegramRichRequestTimeout)
        self.identity_calls += 1
        return TelegramRichProviderResponse(
            status_code=200,
            body={
                "ok": True,
                "result": {"id": EXPECTED_BOT_ID, "is_bot": True, "username": EXPECTED_BOT_USERNAME},
            },
        )

    def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message: dict[str, Any],
        timeout: TelegramRichRequestTimeout,
    ) -> TelegramRichProviderResponse:
        self.mutation_calls.append({"chat_id": chat_id, "rich_message": rich_message, "timeout": timeout})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class OrderingArchiver:
    def __init__(self, durable_intent_path: Path, events: list[str]) -> None:
        self.durable_intent_path = durable_intent_path
        self.events = events

    def archive(self, outcome_bytes: bytes, *, outcome_sha256: str) -> TelegramRichOutcomeArchiveReceipt:
        durable = load_canary_state(self.durable_intent_path)
        assert isinstance(durable, NativeRichCanaryIntent)
        self.events.append("archive")
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=outcome_sha256,
            archive_reference="test:exact-provider-outcome",
            durable_before_state_mutation=True,
        )


def _target_proof(*, checked_at: datetime = NOW, bot_id: int = EXPECTED_BOT_ID) -> GenericTargetProof:
    profile = load_channel_profile(PROFILE_PATH)
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="svodka",
        channel_username=EXPECTED_CHANNEL_USERNAME,
        profile_sha256=profile.digest,
        bot_id=bot_id,
        bot_username=EXPECTED_BOT_USERNAME,
        chat_id=EXPECTED_CHAT_ID,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=checked_at,
    )


def _write_target(path: Path, **updates: Any) -> None:
    proof = _target_proof(**updates)
    path.write_text(proof.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _media_fetcher(url: str) -> tuple[int, str, bytes]:
    return (
        200,
        "image/jpeg",
        (b"\xff\xd8\xffexact-nasa-map-bytes" if "eclipse_map" in url else b"\xff\xd8\xffexact-nasa-plane-bytes"),
    )


def _write_media_proof(path: Path, *, checked_at: datetime = NOW) -> None:
    media_proof = prove_remote_media(
        spec=load_canary_spec(SPEC_PATH),
        repository_root=ROOT,
        fetcher=_media_fetcher,
        now=checked_at,
    )
    write_model(path, media_proof)


def _prepare(tmp_path: Path, *, checked_at: datetime = NOW) -> tuple[NativeRichCanaryIntent, Path, Path, Path]:
    target_path = tmp_path / "target.json"
    media_proof_path = tmp_path / "media-proof.json"
    state_path = tmp_path / "state.json"
    _write_target(target_path, checked_at=checked_at)
    _write_media_proof(media_proof_path, checked_at=checked_at)
    intent = prepare_intent(
        profile_path=PROFILE_PATH,
        binding_path=BINDING_PATH,
        spec_path=SPEC_PATH,
        target_proof_path=target_path,
        media_proof_path=media_proof_path,
        state_path=state_path,
        repository_root=ROOT,
        confirmation=CONFIRMATION,
        github_repository=EXPECTED_REPOSITORY,
        github_ref=EXPECTED_GITHUB_REF,
        github_sha=GITHUB_SHA,
        github_workflow_sha=GITHUB_SHA,
        run_id=WORKFLOW_RUN_ID,
        run_attempt="1",
        now=NOW,
    )
    write_model(state_path, intent)
    return intent, target_path, state_path, media_proof_path


def _returned_rich_message() -> dict[str, Any]:
    rich = copy.deepcopy(load_canary_spec(SPEC_PATH).expected_returned_rich_message)
    rich["blocks"][2]["photo"] = [
        {
            "file_id": "telegram-map-small-file-id",
            "file_unique_id": "telegram-map-small-identity",
            "width": 320,
            "height": 320,
            "file_size": 23139,
        },
        {
            "file_id": "telegram-map-large-file-id",
            "file_unique_id": "telegram-map-large-identity",
            "width": 1024,
            "height": 1024,
            "file_size": 275149,
        },
    ]
    rich["blocks"][6]["photo"] = [
        {
            "file_id": "telegram-plane-file-id",
            "file_unique_id": "telegram-plane-identity",
            "width": 1280,
            "height": 798,
            "file_size": 312000,
        }
    ]
    return rich


def _response(*, rich_message: Any = None, message_id: Any = 912) -> TelegramRichProviderResponse:
    return TelegramRichProviderResponse(
        status_code=200,
        body={
            "ok": True,
            "result": {
                "message_id": message_id,
                "chat": {"id": EXPECTED_CHAT_ID, "username": "deep_info_life", "type": "channel"},
                "rich_message": _returned_rich_message() if rich_message is None else rich_message,
            },
        },
    )


def _dispatch(
    tmp_path: Path,
    provider: FakeProvider,
    *,
    archiver: OrderingArchiver | None = None,
) -> tuple[NativeRichCanaryIntent, Any, Path, Path]:
    intent, target_path, state_path, media_proof_path = _prepare(tmp_path)
    outcome_path = tmp_path / "provider-outcome.json"
    archived = dispatch_canary_once(
        profile_path=PROFILE_PATH,
        binding_path=BINDING_PATH,
        spec_path=SPEC_PATH,
        target_proof_path=target_path,
        media_proof_path=media_proof_path,
        durable_state_path=state_path,
        provider_outcome_path=outcome_path,
        repository_root=ROOT,
        provider=provider,
        archiver=archiver,
        now=NOW + timedelta(minutes=1),
    )
    return intent, archived, state_path, outcome_path


def test_exact_confirmation_is_required() -> None:
    require_exact_invocation(
        confirmation=CONFIRMATION,
        github_repository=EXPECTED_REPOSITORY,
        github_ref=EXPECTED_GITHUB_REF,
    )

    with pytest.raises(ValueError, match="confirmation must be exactly"):
        require_exact_invocation(
            confirmation="RICH-CANARY:@deep_info_life:ONE-ARTICLE ",
            github_repository=EXPECTED_REPOSITORY,
            github_ref=EXPECTED_GITHUB_REF,
        )


def test_wrong_branch_is_rejected() -> None:
    with pytest.raises(ValueError, match="only from refs/heads/main"):
        require_exact_invocation(
            confirmation=CONFIRMATION,
            github_repository=EXPECTED_REPOSITORY,
            github_ref="refs/heads/feature",
        )


def test_wrong_target_preflight_is_rejected_before_intent(tmp_path: Path) -> None:
    target_path = tmp_path / "target.json"
    media_proof_path = tmp_path / "media-proof.json"
    state_path = tmp_path / "state.json"
    _write_target(target_path, bot_id=EXPECTED_BOT_ID + 1)
    _write_media_proof(media_proof_path)

    with pytest.raises(ValueError, match="exact reviewed target"):
        prepare_intent(
            profile_path=PROFILE_PATH,
            binding_path=BINDING_PATH,
            spec_path=SPEC_PATH,
            target_proof_path=target_path,
            media_proof_path=media_proof_path,
            state_path=state_path,
            repository_root=ROOT,
            confirmation=CONFIRMATION,
            github_repository=EXPECTED_REPOSITORY,
            github_ref=EXPECTED_GITHUB_REF,
            github_sha=GITHUB_SHA,
            github_workflow_sha=GITHUB_SHA,
            run_id=WORKFLOW_RUN_ID,
            run_attempt="1",
            now=NOW,
        )

    assert not state_path.exists()


def test_stale_proof_is_rejected_before_intent(tmp_path: Path) -> None:
    target_path = tmp_path / "target.json"
    media_proof_path = tmp_path / "media-proof.json"
    state_path = tmp_path / "state.json"
    stale_time = NOW - timedelta(minutes=16)
    _write_target(target_path, checked_at=stale_time)
    _write_media_proof(media_proof_path, checked_at=stale_time)

    with pytest.raises(ValueError, match="proof is stale"):
        prepare_intent(
            profile_path=PROFILE_PATH,
            binding_path=BINDING_PATH,
            spec_path=SPEC_PATH,
            target_proof_path=target_path,
            media_proof_path=media_proof_path,
            state_path=state_path,
            repository_root=ROOT,
            confirmation=CONFIRMATION,
            github_repository=EXPECTED_REPOSITORY,
            github_ref=EXPECTED_GITHUB_REF,
            github_sha=GITHUB_SHA,
            github_workflow_sha=GITHUB_SHA,
            run_id=WORKFLOW_RUN_ID,
            run_attempt="1",
            now=NOW,
        )


def test_remote_media_reproof_blocks_changed_bytes_before_mutation() -> None:
    spec = load_canary_spec(SPEC_PATH)
    initial = prove_remote_media(
        spec=spec,
        repository_root=ROOT,
        fetcher=_media_fetcher,
        now=NOW,
    )

    def changed_fetcher(url: str) -> tuple[int, str, bytes]:
        status, content_type, content = _media_fetcher(url)
        return status, content_type, content + b"changed"

    with pytest.raises(ValueError, match="media bytes changed"):
        prove_remote_media(
            spec=spec,
            repository_root=ROOT,
            expected_proof=initial,
            fetcher=changed_fetcher,
            now=NOW + timedelta(minutes=1),
        )


def test_durable_intent_exists_before_mutation_and_outcome_archive(tmp_path: Path) -> None:
    intent, target_path, state_path, media_proof_path = _prepare(tmp_path)
    events: list[str] = []

    class OrderedProvider(FakeProvider):
        def send_rich_message(self, **kwargs: Any) -> TelegramRichProviderResponse:
            durable = load_canary_state(state_path)
            assert durable == intent
            events.append("mutation")
            return super().send_rich_message(**kwargs)

    provider = OrderedProvider(_response())
    archiver = OrderingArchiver(state_path, events)
    archived = dispatch_canary_once(
        profile_path=PROFILE_PATH,
        binding_path=BINDING_PATH,
        spec_path=SPEC_PATH,
        target_proof_path=target_path,
        media_proof_path=media_proof_path,
        durable_state_path=state_path,
        provider_outcome_path=tmp_path / "unused.json",
        repository_root=ROOT,
        provider=provider,
        archiver=archiver,
        now=NOW + timedelta(minutes=1),
    )

    assert archived.outcome.provider_effect == "verified"
    assert events == ["mutation", "archive"]
    assert isinstance(load_canary_state(state_path), NativeRichCanaryIntent)


def test_exactly_one_send_rich_message_and_same_credential_get_me(tmp_path: Path) -> None:
    provider = FakeProvider(_response())

    intent, archived, _, _ = _dispatch(tmp_path, provider)

    assert archived.outcome.provider_effect == "verified"
    assert intent.rich_article_sha256.startswith("sha256:")
    assert intent.rich_render_sha256.startswith("sha256:")
    assert provider.identity_calls == 1
    assert len(provider.mutation_calls) == 1
    assert provider.mutation_calls[0]["chat_id"] == EXPECTED_CHAT_ID
    assert provider.mutation_calls[0]["rich_message"] == intent.document.input_rich_message
    assert archived.outcome.mutation_request_count == 1
    assert archived.outcome.provider_method == "sendRichMessage"


def test_ambiguous_timeout_is_may_exist_and_never_retried(tmp_path: Path) -> None:
    provider = FakeProvider(TelegramRichProviderTimeout(request_may_have_been_dispatched=True))

    _, archived, _, _ = _dispatch(tmp_path, provider)

    assert archived.outcome.provider_effect == "may_exist"
    assert archived.outcome.automatic_retry_allowed is False
    assert archived.outcome.mutation_request_count == 1
    assert provider.identity_calls == 1
    assert len(provider.mutation_calls) == 1


def test_every_second_run_is_blocked_even_after_intent(tmp_path: Path) -> None:
    _, _, state_path, _ = _prepare(tmp_path)

    with pytest.raises(ValueError, match="second run and blind retry are forbidden"):
        require_no_prior_state(state_path)
    with pytest.raises(ValueError, match="second run and blind retry are forbidden"):
        prepare_intent(
            profile_path=PROFILE_PATH,
            binding_path=BINDING_PATH,
            spec_path=SPEC_PATH,
            target_proof_path=tmp_path / "target.json",
            media_proof_path=tmp_path / "media-proof.json",
            state_path=state_path,
            repository_root=ROOT,
            confirmation=CONFIRMATION,
            github_repository=EXPECTED_REPOSITORY,
            github_ref=EXPECTED_GITHUB_REF,
            github_sha=GITHUB_SHA,
            github_workflow_sha=GITHUB_SHA,
            run_id=WORKFLOW_RUN_ID,
            run_attempt="2",
            now=NOW,
        )


def test_malformed_rich_message_response_is_may_exist(tmp_path: Path) -> None:
    provider = FakeProvider(_response(rich_message={"blocks": "not-a-list"}))

    _, archived, _, _ = _dispatch(tmp_path, provider)

    assert archived.outcome.provider_effect == "may_exist"
    assert archived.outcome.structure_verification == "malformed"
    assert archived.outcome.message_id is None
    assert len(provider.mutation_calls) == 1


def test_missing_inline_media_is_may_exist(tmp_path: Path) -> None:
    returned = _returned_rich_message()
    returned["blocks"][2] = {"type": "paragraph", "text": "Карта отсутствует"}
    returned["blocks"][6] = {"type": "paragraph", "text": "Фотография отсутствует"}
    provider = FakeProvider(_response(rich_message=returned))

    _, archived, _, _ = _dispatch(tmp_path, provider)

    assert archived.outcome.provider_effect == "may_exist"
    assert archived.outcome.media_verification == "missing"
    assert archived.outcome.message_id is None
    assert len(provider.mutation_calls) == 1


def test_exact_success_requires_chat_message_rich_structure_and_media_then_finalizes(tmp_path: Path) -> None:
    provider = FakeProvider(_response())

    intent, archived, state_path, outcome_path = _dispatch(tmp_path, provider)
    outcome = archived.outcome

    assert outcome.provider_effect == "verified"
    assert outcome.expected_chat_id == EXPECTED_CHAT_ID
    assert outcome.message_id == 912
    assert outcome.returned_rich_message == _returned_rich_message()
    assert outcome.structure_verification == "exact"
    assert outcome.media_verification == "exact"
    assert outcome.returned_rich_structure_sha256 == intent.expected_rich_structure_sha256
    assert outcome.returned_media_sha256 == intent.expected_media_sha256
    assert outcome_path.exists()

    terminal = finalize_outcome_state(
        durable_intent_path=state_path,
        provider_outcome_path=outcome_path,
        artifact_name=f"svodka-native-rich-canary-outcome-{WORKFLOW_RUN_ID}-1",
        artifact_id="999",
        artifact_url=(f"https://github.com/{EXPECTED_REPOSITORY}/actions/runs/{WORKFLOW_RUN_ID}/artifacts/999"),
        artifact_digest="b" * 64,
        now=NOW + timedelta(minutes=2),
    )

    assert isinstance(terminal, NativeRichCanaryOutcomeState)
    assert terminal.state == "verified"
    assert terminal.provider_effect == "verified"
    assert terminal.second_run_allowed is False
    assert terminal.publication_ledger_consumed is False
    assert terminal.counts_as_pilot_post is False
    assert terminal.pilot_release_modified is False
    assert terminal.legacy_scheduler_unlocked is False
    assert terminal.automatic_delete_allowed is False
    assert terminal.automatic_edit_allowed is False


def test_state_is_separate_from_publication_ledger(tmp_path: Path) -> None:
    ledger_path = tmp_path / "publication-ledger.json"
    ledger_path.write_bytes(b'{"sentinel":"pilot-ledger-must-not-change"}\n')
    ledger_before = ledger_path.read_bytes()
    intent, _, state_path, _ = _prepare(tmp_path)

    assert state_path.name == "state.json"
    assert intent.publication_ledger_consumed is False
    assert intent.counts_as_pilot_post is False
    assert intent.pilot_release_modified is False
    assert intent.legacy_scheduler_unlocked is False
    assert ledger_path.read_bytes() == ledger_before
    assert "publication-ledger" not in state_path.read_text(encoding="utf-8")


def test_reviewed_document_has_useful_native_features_and_two_registry_photos() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    spec = load_canary_spec(SPEC_PATH)
    document = build_document(
        profile=profile,
        binding=binding,
        spec=spec,
        github_repository=EXPECTED_REPOSITORY,
        github_sha=GITHUB_SHA,
        repository_root=ROOT,
    )
    blocks = document.input_rich_message["blocks"]
    block_types = [block["type"] for block in blocks]

    assert document.legacy_fallback is None
    assert document.provider_assigned_media_paths == ("$/blocks/2", "$/blocks/6")
    assert block_types.count("photo") == 2
    assert {
        "heading",
        "paragraph",
        "list",
        "divider",
        "blockquote",
        "table",
        "mathematical_expression",
        "details",
        "photo",
    }.issubset(block_types)
    assert spec.media_registry.source_pr == 293
    assert document.input_rich_message["blocks"][2]["photo"]["media"] == (
        "https://assets.science.nasa.gov/dynamicimage/assets/science/hpd/eclipse/"
        "eclipse_map_20260812.jpg?w=1024&h=1024&fit=clip&crop=faces%2Cfocalpoint"
    )
    assert document.input_rich_message["blocks"][6]["photo"]["media"] == (
        "https://science.nasa.gov/wp-content/uploads/2024/02/05pd1556medium-e1707864845295.jpg"
    )


def test_future_edit_test_is_separate_provider_disabled_and_uses_rich_message() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    spec = load_canary_spec(SPEC_PATH)
    document = build_document(
        profile=profile,
        binding=binding,
        spec=spec,
        github_repository=EXPECTED_REPOSITORY,
        github_sha=GITHUB_SHA,
        repository_root=ROOT,
    )

    plan = build_future_edit_test_plan(document, spec)

    assert plan.provider_method == "editMessageText"
    assert plan.request_parameter_name == "rich_message"
    assert plan.provider_writes_authorized is False
    assert plan.wired_to_workflow is False
    assert plan.provider_request_count == 0
    assert plan.automatic_dispatch_allowed is False
    assert plan.text_parameter_used is False
    details = next(block for block in plan.replacement_rich_message["blocks"] if block["type"] == "details")
    assert details["summary"] == "Источники и точная карта — проверено"
    assert "message_id" not in json.dumps(plan.replacement_rich_message, ensure_ascii=False)
