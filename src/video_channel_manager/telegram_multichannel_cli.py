from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_editorial_hold import require_execution_not_held
from video_channel_manager.telegram_multichannel_outcome import (
    GenericProviderOutcome,
    GenericSendProviderEffect,
    apply_provider_outcome,
)
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue, load_release
from video_channel_manager.telegram_multichannel_state import (
    GenericDispatchEnvelope,
    GenericPublicationLedger,
    OwnerScheduledCanaryApproval,
    audit_audio_history,
    initialize_ledger,
    load_ledger,
    prepare_next,
    require_audio_channel_admission,
    save_ledger,
    skip_expired_pending,
    strict_next_item,
    verify_dispatch_against_release,
    verify_persisted_intent,
)
from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPhotoPayload,
    GenericPollPayload,
    GenericTargetProof,
    TelegramApiError,
    preflight_channel,
    send_message_once,
    send_photo_once,
    send_poll_once,
)
from video_channel_manager.telegram_multichannel_audio import GenericAudioPayload, send_audio_once
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload, send_video_once
from video_channel_manager.telegram_publication_freshness import (
    publication_freshness,
    skip_expired_pending_by_freshness,
)

from video_channel_manager.telegram_target_binding import load_target_binding

ModelT = TypeVar("ModelT", bound=BaseModel)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Durable generic multi-channel Telegram publication runtime")
    sub = root.add_subparsers(dest="command", required=True)

    initialize = sub.add_parser("initialize-ledger")
    initialize.add_argument("--release", type=Path, required=True)
    initialize.add_argument("--output", type=Path, required=True)
    initialize.add_argument("--confirm", required=True)

    skip_expired = sub.add_parser("skip-expired")
    skip_expired.add_argument("--release", type=Path, required=True)
    skip_expired.add_argument("--ledger", type=Path, required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--profile", type=Path, required=True)
    prepare.add_argument("--release", type=Path, required=True)
    prepare.add_argument("--ledger", type=Path, required=True)
    target_source = prepare.add_mutually_exclusive_group(required=True)
    target_source.add_argument("--target-proof", type=Path, help="Use an existing fresh target proof.")
    target_source.add_argument("--binding", type=Path, help="Run exact pinned-target preflight within prepare.")
    prepare.add_argument("--mode", choices=("manual", "scheduled"), required=True)
    prepare.add_argument("--publication-id")
    prepare.add_argument("--scheduled-canary-authorization", type=Path)
    prepare.add_argument("--verified-manual-canary-release", type=Path)
    prepare.add_argument("--verified-manual-canary-ledger", type=Path)
    prepare.add_argument(
        "--recover-stale-predecessors",
        action="store_true",
        help="Recover only bounded-stale pending predecessors before an exact manual dispatch.",
    )
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--run-attempt", required=True)
    prepare.add_argument("--github-sha", required=True)
    prepare.add_argument("--github-workflow-sha", required=True)
    prepare.add_argument("--envelope-output", type=Path, required=True)

    publish = sub.add_parser("publish-audio", help="Prepare and publish one exact authorized audio item.")
    publish.add_argument("--profile", type=Path, required=True)
    publish.add_argument("--release", type=Path, required=True)
    publish.add_argument("--ledger", type=Path, required=True)
    publish.add_argument("--binding", type=Path, required=True)
    publish.add_argument("--publication-id", required=True)
    publish.add_argument("--outcome-output", type=Path, required=True)
    for flag, env in (
        ("--run-id", "GITHUB_RUN_ID"),
        ("--run-attempt", "GITHUB_RUN_ATTEMPT"),
        ("--github-sha", "GITHUB_SHA"),
        ("--github-workflow-sha", "GITHUB_WORKFLOW_SHA"),
    ):
        value = os.environ.get(env)
        publish.add_argument(flag, default=value, required=not value)
    publish.set_defaults(
        mode="manual",
        target_proof=None,
        scheduled_canary_authorization=None,
        verified_manual_canary_release=None,
        verified_manual_canary_ledger=None,
        recover_stale_predecessors=False,
    )

    verify = sub.add_parser("verify-intent")
    verify.add_argument("--release", type=Path, required=True)
    verify.add_argument("--ledger", type=Path, required=True)
    verify.add_argument("--envelope", type=Path, required=True)

    send = sub.add_parser("send-once")
    send.add_argument("--profile", type=Path, required=True)
    send.add_argument("--release", type=Path, required=True)
    send.add_argument("--ledger", type=Path, required=True)
    send.add_argument("--envelope", type=Path, required=True)
    send.add_argument("--outcome-output", type=Path, required=True)

    apply = sub.add_parser("apply-outcome")
    apply.add_argument("--release", type=Path, required=True)
    apply.add_argument("--ledger", type=Path, required=True)
    apply.add_argument("--envelope", type=Path, required=True)
    apply.add_argument("--outcome", type=Path, required=True)

    recover = sub.add_parser("recover-outcome")
    recover.add_argument("--release", type=Path, required=True)
    recover.add_argument("--ledger", type=Path, required=True)
    recover.add_argument("--envelope", type=Path, required=True)
    recover.add_argument("--profile", type=Path, help="Required for recovery of remote audio state.")

    audio_history = sub.add_parser("audit-audio-history")
    audio_history.add_argument("--release", type=Path, required=True)
    audio_history.add_argument("--publication-id", required=True)
    audio_history.add_argument("--history", type=Path, nargs=2, action="append", required=True)

    validate = sub.add_parser("validate-ledger")
    validate.add_argument("--release", type=Path, required=True)
    validate.add_argument("--ledger", type=Path, required=True)
    return root


def _load_model(path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid runtime artifact {path}: {exc}") from exc


def _read_scheduled_canary_authorization(path: Path) -> OwnerScheduledCanaryApproval:
    try:
        authority = OwnerScheduledCanaryApproval.model_validate_json(path.read_text(encoding="utf-8"))
        manifest_path = Path(authority.source_manifest_path)
        if manifest_path.is_absolute() or ".." in manifest_path.parts:
            raise ValueError("owner-scheduled canary manifest path must be repository-relative")
        source = manifest_path.read_bytes()
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid owner-scheduled canary evidence: {exc}") from exc
    git_blob_sha1 = hashlib.sha1(b"blob " + str(len(source)).encode("ascii") + b"\0" + source).hexdigest()
    if git_blob_sha1 != authority.source_manifest_git_blob_sha1:
        raise ValueError("owner-scheduled canary source manifest changed after owner approval")
    return authority


def _write_model(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _require_runtime_profile(profile: TelegramChannelProfile, release: GenericReleaseQueue) -> None:
    if not profile.provider_writes_authorized:
        raise ValueError("selected Telegram channel profile is write-disabled")
    if not release.release_authorized:
        raise ValueError("selected Telegram release is not authorized")
    if (
        release.project_key != profile.project_key
        or release.channel_username.casefold() != profile.channel_username.casefold()
        or release.profile_sha256 != profile.digest
    ):
        raise ValueError("selected Telegram release differs from channel profile")


def _require_release_target(release: GenericReleaseQueue, target: GenericTargetProof) -> None:
    if release.chat_id is None or release.bot_id is None or release.bot_username is None:
        raise ValueError("authorized release has no exact Telegram target identity")
    if (
        target.chat_id != release.chat_id
        or target.bot_id != release.bot_id
        or target.bot_username.casefold() != release.bot_username.casefold()
        or target.channel_username.casefold() != release.channel_username.casefold()
    ):
        raise ValueError("dispatch target differs from exact release-bound Telegram identity")


def _token(profile: TelegramChannelProfile) -> str:
    token = os.environ.get(profile.bot_token_env, "").strip()
    if not token:
        raise ValueError(f"missing Telegram token in {profile.bot_token_env}")
    return token


def _preflight_release_target(
    profile: TelegramChannelProfile, release: GenericReleaseQueue, binding_path: Path
) -> GenericTargetProof:
    """Resolve the pinned release target without a separate proof-file handoff."""
    _require_runtime_profile(profile, release)
    binding = load_target_binding(binding_path, profile)
    if (
        release.target_binding_sha256 != binding.digest
        or release.chat_id != binding.chat_id
        or release.bot_id != binding.bot_id
        or (release.bot_username or "").casefold() != binding.bot_username.casefold()
    ):
        raise ValueError("pinned Telegram binding differs from exact release-bound target")
    target = preflight_channel(
        profile,
        token=_token(profile),
        expected_chat_id=binding.chat_id,
        expected_bot_id=binding.bot_id,
        expected_bot_username=binding.bot_username,
    )
    _require_release_target(release, target)
    return target


def _configured_max_publication_lag_minutes() -> int | None:
    raw = os.environ.get("MAX_PUBLICATION_LAG_MINUTES", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("MAX_PUBLICATION_LAG_MINUTES must be an integer") from exc
    if not 1 <= value <= 360:
        raise ValueError("MAX_PUBLICATION_LAG_MINUTES must be between 1 and 360")
    return value


def _recover_expired_before_exact_manual_prepare(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    *,
    mode: str,
    expected_publication_id: str | None,
    recover_stale_predecessors: bool = False,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Apply bounded stale predecessors only under an explicit exact-manual opt-in.

    The caller persists this mutation only if the requested strict-next dispatch
    is successfully prepared, so a wrong or premature publication_id cannot
    advance durable state.
    """

    if not recover_stale_predecessors:
        return ()
    if mode != "manual" or expected_publication_id is None:
        raise ValueError("stale predecessor recovery requires exact manual prepare with publication_id")
    max_lag_minutes = _configured_max_publication_lag_minutes()
    if max_lag_minutes is None:
        raise ValueError("stale predecessor recovery requires MAX_PUBLICATION_LAG_MINUTES")
    return skip_expired_pending_by_freshness(
        release,
        ledger,
        now=now,
        max_lag_minutes=max_lag_minutes,
    )


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (TelegramApiError, ValueError)):
        return " ".join(str(exc).split())[:1000]
    return f"unexpected provider runtime error: {type(exc).__name__}"


def _provider_effect(exc: TelegramApiError) -> GenericSendProviderEffect:
    effect = exc.provider_effect
    if effect in {"not_dispatched", "confirmed_absent", "may_exist", "verified"}:
        return effect
    return "may_exist"


def _failure_outcome(
    envelope: GenericDispatchEnvelope,
    *,
    effect: GenericSendProviderEffect,
    retryable: bool,
    error: str,
) -> GenericProviderOutcome:
    return GenericProviderOutcome(
        schema_name="video-channel-manager.telegram-generic-provider-outcome",
        schema_version=1,
        publication_id=envelope.publication_id,
        provider_payload_sha256=envelope.provider_payload_sha256,
        intent_id=envelope.intent_id,
        provider_effect=effect,
        retryable=retryable,
        error=error,
        receipt=None,
    )


def _send_exact_payload(
    profile: TelegramChannelProfile,
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
    *,
    now: datetime | None = None,
) -> GenericProviderOutcome:
    # A prior intent may already have had an effect; HOLD must not fabricate
    # a no-effect outcome that would clear the conservative may_exist state.
    require_execution_not_held(release)
    try:
        _require_runtime_profile(profile, release)
        _require_release_target(release, envelope.target)
        item = verify_dispatch_against_release(release, envelope)
        verify_persisted_intent(release, ledger, envelope)
        token = _token(profile)
        max_lag_minutes = _configured_max_publication_lag_minutes()
        if max_lag_minutes is not None:
            decision = publication_freshness(
                release,
                envelope.publication_id,
                now=now or datetime.now(tz=UTC),
                max_lag_minutes=max_lag_minutes,
            )
            if not decision.eligible:
                return _failure_outcome(
                    envelope,
                    effect="confirmed_absent",
                    retryable=True,
                    error=f"publication freshness gate closed before provider mutation: {decision.reason}",
                )
        if isinstance(item.payload, GenericMessagePayload):
            receipt = send_message_once(profile, envelope.target, item.payload, token=token, now=now)
        elif isinstance(item.payload, GenericPollPayload):
            receipt = send_poll_once(profile, envelope.target, item.payload, token=token, now=now)
        elif isinstance(item.payload, GenericPhotoPayload):
            receipt = send_photo_once(profile, envelope.target, item.payload, token=token, now=now)
        elif isinstance(item.payload, GenericVideoPayload):
            receipt = send_video_once(profile, envelope.target, item.payload, token=token, now=now)
        elif isinstance(item.payload, GenericAudioPayload):
            receipt = send_audio_once(profile, envelope.target, item.payload, token=token, now=now)
        else:
            raise ValueError("unsupported generic Telegram provider payload")
    except TelegramApiError as exc:
        effect = _provider_effect(exc)
        retryable = exc.retryable if effect in {"not_dispatched", "confirmed_absent"} else False
        return _failure_outcome(
            envelope,
            effect=effect,
            retryable=retryable,
            error=_safe_error(exc),
        )
    except ValueError as exc:
        return _failure_outcome(
            envelope,
            effect="not_dispatched",
            retryable=True,
            error=_safe_error(exc),
        )
    except Exception as exc:
        return _failure_outcome(
            envelope,
            effect="may_exist",
            retryable=False,
            error=_safe_error(exc),
        )

    return GenericProviderOutcome(
        schema_name="video-channel-manager.telegram-generic-provider-outcome",
        schema_version=1,
        publication_id=envelope.publication_id,
        provider_payload_sha256=envelope.provider_payload_sha256,
        intent_id=envelope.intent_id,
        provider_effect="verified",
        retryable=False,
        error=None,
        receipt=receipt,
    )


def _local_dispatch_paths(ledger_path: Path, envelope: GenericDispatchEnvelope) -> tuple[Path, Path]:
    ledger_path = ledger_path.resolve()
    claim_dir = ledger_path.parent / f".{ledger_path.name}.dispatch-claims"
    intent_key = hashlib.sha256(envelope.intent_id.encode("utf-8")).hexdigest()
    return claim_dir / f"{intent_key}.json", claim_dir / f"{intent_key}.outcome.json"


def _write_atomic_outcome(path: Path, outcome: GenericProviderOutcome) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(outcome.model_dump_json(indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _load_local_outcome(ledger_path: Path, envelope: GenericDispatchEnvelope) -> GenericProviderOutcome:
    claim, result_path = _local_dispatch_paths(ledger_path, envelope)
    if _load_model(claim, GenericDispatchEnvelope) != envelope:
        raise ValueError("local dispatch claim differs from exact envelope")
    outcome = _load_model(result_path, GenericProviderOutcome)
    if outcome.intent_id != envelope.intent_id:
        raise ValueError("local outcome intent differs from exact envelope")
    return outcome


def _state_git(directory: Path, *args: str) -> str:
    """Run bounded Git state operations without exposing remote credentials."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.longpaths=true", "-C", str(directory), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("audio state Git operation unavailable; reconcile before retrying") from exc
    if result.returncode != 0:
        raise ValueError(f"audio state Git {args[0]} failed; reconcile before retrying")
    return result.stdout.strip()


def _require_state_origin(root: Path) -> None:
    allowed = {
        "https://github.com/fedormilovanov/video-channel-manager",
        "git@github.com:fedormilovanov/video-channel-manager",
        "ssh://git@github.com/fedormilovanov/video-channel-manager",
    }
    for flags in (("--all",), ("--push", "--all")):
        url = _state_git(root, "remote", "get-url", *flags, "origin")
        if url.casefold().removesuffix(".git") not in allowed:
            raise ValueError("audio state origin must be the exact canonical repository")


def _remote_state_head(root: Path, branch: str) -> str:
    ref = f"refs/heads/{branch}"
    expected = _state_git(root, "ls-remote", "--exit-code", "origin", ref).split()
    if len(expected) != 2 or expected[1] != ref:
        raise ValueError("audio state remote ref is missing or ambiguous")
    return expected[0]


def _audio_state_root(profile: TelegramChannelProfile, ledger_path: Path) -> Path:
    root = Path(_state_git(ledger_path.parent, "rev-parse", "--show-toplevel")).resolve()
    relative = ledger_path.relative_to(root)
    expected = Path("content/telegram") / profile.project_key / "audio-releases"
    if relative.parent.parent != expected:
        raise ValueError("audio ledger must be in the exact protected channel state checkout")
    _require_state_origin(root)
    return root


def _require_current_audio_state(profile: TelegramChannelProfile, ledger_path: Path) -> Path:
    root = _audio_state_root(profile, ledger_path)
    expected = Path("content/telegram") / profile.project_key / "audio-releases"
    if _state_git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("audio state checkout must be clean before dispatch")
    if _state_git(root, "rev-parse", "HEAD") != _remote_state_head(root, profile.state_branch):
        raise ValueError("audio state checkout is not the exact current remote state")
    tracked = _state_git(root, "ls-files", "-v", "--", expected.as_posix()).splitlines()
    if not tracked or any(not line.startswith("H ") for line in tracked):
        raise ValueError("audio state must contain the complete tracked channel history")
    paths = {line[2:] for line in tracked}
    for directory in (root / expected).iterdir():
        for name in ("release.json", "ledger.json"):
            path = directory / name
            if path.is_symlink() or path.relative_to(root).as_posix() not in paths:
                raise ValueError("audio history must contain only tracked release and ledger pairs")
    return root


def _persist_remote_audio_state(root: Path, profile: TelegramChannelProfile, phase: str, *paths: Path) -> None:
    relative = [path.relative_to(root).as_posix() for path in paths]
    _state_git(root, "add", "--", *relative)
    # Unique commits prevent two identical trees from the same parent
    # from turning a losing push into an already-up-to-date success.
    nonce = secrets.token_hex(16)
    _state_git(
        root,
        "-c",
        "user.name=telegram-audio-state",
        "-c",
        "user.email=telegram-audio-state@users.noreply.github.com",
        "commit",
        "--only",
        "-m",
        f"Record Telegram audio {phase} {nonce}",
        "--",
        *relative,
    )
    _push_audio_state(root, profile, phase)


def _push_audio_state(root: Path, profile: TelegramChannelProfile, phase: str) -> None:
    committed_head = _state_git(root, "rev-parse", "HEAD")
    _state_git(root, "push", "--no-force", "--no-follow-tags", "origin", f"HEAD:refs/heads/{profile.state_branch}")
    if _remote_state_head(root, profile.state_branch) != committed_head:
        raise ValueError(f"remote audio {phase} was not verified; reconcile before retrying")


def _audio_intent_path(ledger_path: Path, envelope: GenericDispatchEnvelope) -> Path:
    key = hashlib.sha256(envelope.intent_id.encode("utf-8")).hexdigest()
    return ledger_path.resolve().parent / ".intents" / f"{key}.json"


def _recover_remote_audio_outcome(
    profile: TelegramChannelProfile,
    release: GenericReleaseQueue,
    ledger_path: Path,
    envelope: GenericDispatchEnvelope,
) -> GenericProviderOutcome:
    """Finish only the exact recorded outcome; never invoke a provider sender."""
    if release.profile_sha256 != profile.digest or release.project_key != profile.project_key:
        raise ValueError("audio recovery profile differs from immutable release")
    _require_release_target(release, envelope.target)
    if not isinstance(verify_dispatch_against_release(release, envelope).payload, GenericAudioPayload):
        raise ValueError("audio recovery requires an audio dispatch")
    ledger_path = ledger_path.resolve()
    root = _audio_state_root(profile, ledger_path)
    if ledger_path.parent.name != release.release_id or ledger_path.name != "ledger.json":
        raise ValueError("audio recovery requires the canonical release ledger")
    claim, result = _local_dispatch_paths(ledger_path, envelope)
    intent = _audio_intent_path(ledger_path, envelope)
    release_path = ledger_path.parent / "release.json"
    for path in (claim, result, intent, release_path):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("audio recovery artifacts must not be symlinks")
    outcome = _load_local_outcome(ledger_path, envelope)
    ledger_rel, result_rel = (path.relative_to(root).as_posix() for path in (ledger_path, result))
    head = _state_git(root, "rev-parse", "HEAD")
    remote = _remote_state_head(root, profile.state_branch)
    committed = bool(_state_git(root, "ls-tree", "--name-only", head, "--", result_rel))
    base = head
    if committed:
        # Only an exact outcome transaction (two paths, one parent) can be
        # recovered. Never rebase, reset or replay a diverged state checkout.
        parents = _state_git(root, "rev-list", "--parents", "-n", "1", head).split()
        changed = _state_git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines()
        if len(parents) != 2 or set(changed) != {ledger_rel, result_rel}:
            raise ValueError("audio recovery requires the exact local outcome commit")
        base = parents[1]
        if remote not in {base, head}:
            raise ValueError("remote audio state diverged; reconcile without sending")
    elif remote != head:
        raise ValueError("remote audio state diverged; reconcile without sending")

    def committed_model(path: Path, model: type[ModelT], revision: str = base) -> ModelT:
        relative = path.relative_to(root).as_posix()
        return model.model_validate_json(_state_git(root, "show", f"{revision}:{relative}"))

    if committed_model(release_path, GenericReleaseQueue) != release:
        raise ValueError("audio recovery release differs from committed release")
    if any(committed_model(path, GenericDispatchEnvelope) != envelope for path in (claim, intent)):
        raise ValueError("audio recovery differs from committed intent or claim")
    before = committed_model(ledger_path, GenericPublicationLedger)
    verify_persisted_intent(release, before, envelope)
    expected = before.model_copy(deep=True)
    apply_provider_outcome(expected, envelope, outcome)
    local = load_ledger(ledger_path, release)
    if local not in (before, expected):
        raise ValueError("audio recovery ledger differs from exact outcome transition")

    if committed:
        if (
            committed_model(result, GenericProviderOutcome, head) != outcome
            or committed_model(ledger_path, GenericPublicationLedger, head) != expected
            or local != expected
            or _state_git(root, "status", "--porcelain=v1", "--untracked-files=all")
        ):
            raise ValueError("audio recovery outcome commit or checkout differs from exact result")
        if remote != head:
            _push_audio_state(root, profile, "outcome recovery")
    else:
        if _state_git(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
            f":(exclude){ledger_rel}",
            f":(exclude){result_rel}",
        ):
            raise ValueError("audio recovery checkout contains unrelated changes")
        save_ledger(ledger_path, expected)
        _persist_remote_audio_state(root, profile, "outcome recovery", result, ledger_path)
    return outcome


def _send_persisted_once(
    profile: TelegramChannelProfile,
    release: GenericReleaseQueue,
    ledger_path: Path,
    envelope: GenericDispatchEnvelope,
    outcome_path: Path,
) -> GenericProviderOutcome:
    """Consume a persisted intent once on the same canonical local ledger."""
    require_execution_not_held(release)
    _require_runtime_profile(profile, release)
    _require_release_target(release, envelope.target)
    ledger_path = ledger_path.resolve()
    ledger = load_ledger(ledger_path, release)
    verify_persisted_intent(release, ledger, envelope)
    item = verify_dispatch_against_release(release, envelope)
    if isinstance(item.payload, GenericAudioPayload):
        require_audio_channel_admission(
            release, ledger_path, envelope.publication_id, current_intent_id=envelope.intent_id
        )
    if outcome_path.exists():
        raise ValueError("Telegram outcome already exists; apply or reconcile it, never resend")
    claim, result_path = _local_dispatch_paths(ledger_path, envelope)
    if result_path.exists():
        raise ValueError("Telegram outcome already exists; recover it, never resend")
    if claim.exists():
        raise ValueError("Telegram intent already claimed; reconcile existing outcome, never resend")
    state_root = (
        _require_current_audio_state(profile, ledger_path) if isinstance(item.payload, GenericAudioPayload) else None
    )
    if state_root is not None:
        intent_path = _audio_intent_path(ledger_path, envelope)
        relative_intent = intent_path.relative_to(state_root).as_posix()
        if _state_git(state_root, "ls-files", "-v", "--", relative_intent) != f"H {relative_intent}":
            raise ValueError("audio dispatch requires the exact committed intent envelope")
        if intent_path.is_symlink() or _load_model(intent_path, GenericDispatchEnvelope) != envelope:
            raise ValueError("audio dispatch differs from the committed intent envelope")
    claim.parent.mkdir(parents=True, exist_ok=True)
    try:
        with claim.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(envelope.model_dump_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ValueError("Telegram intent already claimed; reconcile existing outcome, never resend") from exc

    # Audio claims must win the remote non-forced update before dispatch.
    # An interrupted or losing process retains its claim and cannot send again.
    if state_root is not None:
        _persist_remote_audio_state(state_root, profile, "claim", claim)
    outcome = _send_exact_payload(profile, release, ledger, envelope)
    if outcome.intent_id != envelope.intent_id:
        raise ValueError("new Telegram outcome is not bound to the consumed intent")
    # Persist the canonical result before exporting it to the workflow handoff.
    _write_atomic_outcome(result_path, outcome)
    if state_root is not None:
        # The immutable result and its ledger transition become visible together.
        # If commit/push fails, retain the local result and the remote claim.
        apply_provider_outcome(ledger, envelope, outcome)
        save_ledger(ledger_path, ledger)
        _persist_remote_audio_state(state_root, profile, "outcome", result_path, ledger_path)
    _write_atomic_outcome(outcome_path, outcome)
    return outcome


def main() -> int:
    args = parser().parse_args()

    if args.command == "initialize-ledger":
        release = load_release(args.release)
        require_execution_not_held(release)
        expected = f"INITIALIZE:{release.digest}"
        if args.confirm != expected:
            raise ValueError("ledger initialization confirmation does not match exact release digest")
        if not release.release_authorized:
            raise ValueError("publication ledger requires an authorized immutable release")
        if args.output.exists():
            raise ValueError(f"refusing to overwrite existing Telegram ledger: {args.output}")
        ledger = initialize_ledger(release)
        save_ledger(args.output, ledger)
        print(
            json.dumps(
                {
                    "initialized": True,
                    "release_id": release.release_id,
                    "release_digest": release.digest,
                    "entries": len(ledger.entries),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "skip-expired":
        release = load_release(args.release)
        require_execution_not_held(release)
        if not release.release_authorized:
            raise ValueError("stale-publication skipping requires an authorized immutable release")
        ledger = load_ledger(args.ledger, release)
        max_lag_minutes = _configured_max_publication_lag_minutes()
        if max_lag_minutes is None:
            skipped = skip_expired_pending(release, ledger)
        else:
            skipped = skip_expired_pending_by_freshness(
                release,
                ledger,
                max_lag_minutes=max_lag_minutes,
            )
        if skipped:
            save_ledger(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "skipped": list(skipped),
                    "count": len(skipped),
                    "release_digest": release.digest,
                    "ledger_changed": bool(skipped),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "audit-audio-history":
        candidate = load_release(args.release)
        history = []
        for release_path, ledger_path in args.history:
            historical_release = load_release(release_path)
            history.append((historical_release, load_ledger(ledger_path, historical_release)))
        matches = audit_audio_history(candidate, args.publication_id, tuple(history))
        print(
            json.dumps(
                {
                    "scope": "supplied_immutable_release_ledgers_only",
                    "publication_id": args.publication_id,
                    "release_count": len(history),
                    "known_matches": [match.model_dump(mode="json") for match in matches],
                    "complete_provider_history_verified": False,
                    "provider_write_authorized": False,
                },
                ensure_ascii=False,
            )
        )
        return 3 if matches else 0

    if args.command == "validate-ledger":
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        counts: dict[str, int] = {}
        for entry in ledger.entries.values():
            counts[entry.state] = counts.get(entry.state, 0) + 1
        print(json.dumps({"valid": True, "states": counts, "release_digest": release.digest}, ensure_ascii=False))
        return 0

    if args.command in {"prepare", "publish-audio"}:
        release = load_release(args.release)
        require_execution_not_held(release)
        profile = load_channel_profile(args.profile)
        ledger = load_ledger(args.ledger, release)
        recovered = _recover_expired_before_exact_manual_prepare(
            release,
            ledger,
            mode=args.mode,
            expected_publication_id=args.publication_id,
            recover_stale_predecessors=args.recover_stale_predecessors,
        )
        next_item, reason = strict_next_item(release, ledger)
        if args.command == "publish-audio":
            _require_runtime_profile(profile, release)
            if next_item is None:
                print(json.dumps({"prepared": False, "reason": reason}, ensure_ascii=False))
                return 3
            if next_item.publication_id != args.publication_id or not isinstance(
                next_item.payload, GenericAudioPayload
            ):
                raise ValueError("publish-audio requires the exact strict-next audio publication")
        audio_state_root = None
        if next_item is not None and isinstance(next_item.payload, GenericAudioPayload):
            audio_state_root = _require_current_audio_state(profile, args.ledger.resolve())
            handoff = args.outcome_output if args.command == "publish-audio" else args.envelope_output
            if handoff.exists() or handoff.resolve().is_relative_to(audio_state_root):
                raise ValueError("audio handoff must be a new file outside the durable state checkout")
            require_audio_channel_admission(release, args.ledger, next_item.publication_id)
        target = (
            _preflight_release_target(profile, release, args.binding)
            if args.binding is not None
            else _load_model(args.target_proof, GenericTargetProof)
        )
        owner_canary = (
            _read_scheduled_canary_authorization(args.scheduled_canary_authorization)
            if args.scheduled_canary_authorization is not None
            else None
        )
        if (args.verified_manual_canary_release is None) != (args.verified_manual_canary_ledger is None):
            raise ValueError("verified manual canary requires both a release and a durable ledger")
        verified_canary = None
        if args.mode == "scheduled" and args.verified_manual_canary_release is not None:
            canary_release = load_release(args.verified_manual_canary_release)
            canary_ledger = load_ledger(args.verified_manual_canary_ledger, canary_release)
            verified_canary = (canary_release, canary_ledger)
        prepared = prepare_next(
            profile,
            release,
            ledger,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            github_sha=args.github_sha,
            github_workflow_sha=args.github_workflow_sha,
            mode=args.mode,
            target=target,
            expected_publication_id=args.publication_id,
            scheduled_canary_approval=owner_canary,
            verified_canary=verified_canary,
        )
        if prepared.envelope is None:
            print(json.dumps({"prepared": False, "reason": prepared.reason}, ensure_ascii=False))
            return 3
        save_ledger(args.ledger, ledger)
        if audio_state_root is not None:
            intent_path = _audio_intent_path(args.ledger, prepared.envelope)
            _write_model(intent_path, prepared.envelope)
            _persist_remote_audio_state(audio_state_root, profile, "intent", args.ledger.resolve(), intent_path)
        if args.command == "publish-audio":
            outcome = _send_persisted_once(profile, release, args.ledger, prepared.envelope, args.outcome_output)
            print(
                json.dumps(
                    {
                        "publication_id": outcome.publication_id,
                        "intent_id": prepared.envelope.intent_id,
                        "provider_effect": outcome.provider_effect,
                        "message_url": outcome.receipt.message_url if outcome.receipt else None,
                        "outcome": str(args.outcome_output),
                    },
                    ensure_ascii=False,
                )
            )
            return 0 if outcome.provider_effect == "verified" else 4
        _write_model(args.envelope_output, prepared.envelope)
        print(
            json.dumps(
                {
                    "prepared": True,
                    "publication_id": prepared.envelope.publication_id,
                    "intent_id": prepared.envelope.intent_id,
                    "provider_payload_sha256": prepared.envelope.provider_payload_sha256,
                    "recovered_expired": list(recovered),
                    "reason": prepared.reason,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "verify-intent":
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        envelope = _load_model(args.envelope, GenericDispatchEnvelope)
        entry = verify_persisted_intent(release, ledger, envelope)
        print(
            json.dumps(
                {
                    "verified": True,
                    "publication_id": entry.publication_id,
                    "state": entry.state,
                    "provider_effect": entry.provider_effect,
                    "intent_id": entry.intent_id,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "send-once":
        release = load_release(args.release)
        require_execution_not_held(release)
        profile = load_channel_profile(args.profile)
        envelope = _load_model(args.envelope, GenericDispatchEnvelope)
        outcome = _send_persisted_once(profile, release, args.ledger, envelope, args.outcome_output)
        print(
            json.dumps(
                {
                    "provider_effect": outcome.provider_effect,
                    "publication_id": outcome.publication_id,
                    "retryable": outcome.retryable,
                    "message_url": outcome.receipt.message_url if outcome.receipt else None,
                    "outcome": str(args.outcome_output),
                },
                ensure_ascii=False,
            )
        )
        return 0 if outcome.provider_effect == "verified" else 4

    if args.command in {"apply-outcome", "recover-outcome"}:
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        envelope = _load_model(args.envelope, GenericDispatchEnvelope)
        item = verify_dispatch_against_release(release, envelope)
        if isinstance(item.payload, GenericAudioPayload):
            if args.command != "recover-outcome" or args.profile is None:
                raise ValueError("audio recovery requires recover-outcome with the exact channel profile")
            outcome = _recover_remote_audio_outcome(load_channel_profile(args.profile), release, args.ledger, envelope)
            entry = load_ledger(args.ledger, release).entries[envelope.publication_id]
            print(
                json.dumps(
                    {
                        "recovered": True,
                        "publication_id": entry.publication_id,
                        "state": entry.state,
                        "provider_effect": outcome.provider_effect,
                        "message_url": entry.message_url,
                    },
                    ensure_ascii=False,
                )
            )
            return 0 if outcome.provider_effect == "verified" else 4
        verify_persisted_intent(release, ledger, envelope)
        claim, _ = _local_dispatch_paths(args.ledger, envelope)
        if args.command == "recover-outcome":
            outcome = _load_local_outcome(args.ledger, envelope)
        else:
            outcome = _load_model(args.outcome, GenericProviderOutcome)
            if claim.exists() and outcome != _load_local_outcome(args.ledger, envelope):
                raise ValueError("exported Telegram outcome differs from canonical local outcome")
        entry = apply_provider_outcome(ledger, envelope, outcome)
        save_ledger(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "applied": True,
                    "publication_id": entry.publication_id,
                    "state": entry.state,
                    "provider_effect": entry.provider_effect,
                    "message_url": entry.message_url,
                },
                ensure_ascii=False,
            )
        )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
