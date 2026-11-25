from __future__ import annotations

import copy
import random
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from video_channel_manager.platforms.http import RequestRateLimiter, RetryPolicy
from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.store import TokenStore, reserve_shared_quota
from video_channel_manager.platforms.youtube.writer import (
    VideoDescriptionSnapshot,
    YouTubeDescriptionWriter as BaseYouTubeDescriptionWriter,
    YouTubeRevisionConflictError,
    YouTubeWriteError,
    _postwrite_metadata_drift,
    descriptions_equivalent,
    localization_postflight_drift,
)

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeDescriptionWriter(BaseYouTubeDescriptionWriter):
    """Description writer with bounded post-write consistency retries.

    YouTube can briefly return the pre-update snippet immediately after a
    successful ``videos.update`` call. The base writer still performs the first
    immediate verification; this subclass retries only that narrow verification
    failure and never retries a rejected or ambiguous write.
    """

    def __init__(
        self,
        *,
        client_config: InstalledClientConfig,
        token_store: TokenStore,
        account_alias: str,
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
        verification_delays: Sequence[float] = (0.25, 0.5, 1.0, 2.0),
        retry_policy: RetryPolicy | None = None,
        request_limiter: RequestRateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        super().__init__(
            client_config=client_config,
            token_store=token_store,
            account_alias=account_alias,
            http_client=http_client,
            api_base_url=api_base_url,
            retry_policy=retry_policy,
            request_limiter=request_limiter,
            sleep=sleep,
            jitter=jitter,
        )
        self._verification_delays = tuple(max(0.0, float(delay)) for delay in verification_delays)
        self._sleep = sleep

    def _write_description(
        self,
        *,
        current: VideoDescriptionSnapshot,
        new_description: str,
        require_exact_state: bool = False,
    ) -> VideoDescriptionSnapshot:
        if require_exact_state:
            # The strict base path verifies exact metadata and performs only one
            # dispatch. Do not fall back to the relaxed consistency verifier.
            # Any unresolved result requires independent owner reconciliation.
            return super()._write_description(
                current=current, new_description=new_description, require_exact_state=True
            )
        with reserve_shared_quota(
            self._quota_guard,
            50 + (1 + len(self._verification_delays)) * self.retry_policy.max_attempts,
            YouTubeWriteError,
        ):
            try:
                return super()._write_description(current=current, new_description=new_description)
            except YouTubeWriteError as exc:
                expected_message = f"Verification failed after updating description for {current.video_id}."
                drift_prefix = f"Postflight metadata drift after updating description for {current.video_id}:"
                if str(exc) != expected_message and not str(exc).startswith(drift_prefix):
                    raise
                if not self._verification_delays:
                    raise

            last_snapshot: VideoDescriptionSnapshot | None = None
            last_drift: list[str] = []
            for delay in self._verification_delays:
                if delay:
                    self._sleep(delay)
                last_snapshot = self.read_description(current.video_id)
                if not descriptions_equivalent(last_snapshot.description, new_description):
                    continue
                last_drift = _postwrite_metadata_drift(current, last_snapshot, new_description)
                if not last_drift:
                    return last_snapshot

            observed = "unavailable" if last_snapshot is None else last_snapshot.revision
            extra = f"; metadata drift: {', '.join(last_drift)}" if last_drift else ""
            raise YouTubeWriteError(
                f"Verification failed after updating description for {current.video_id} "
                f"after {1 + len(self._verification_delays)} reads; last revision: {observed}{extra}."
            )

    def replace_localized_description(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        expected_title: str,
        expected_primary_description: str,
        expected_snippet_fields: dict[str, Any],
        expected_privacy: str,
        expected_duration: str,
        expected_localizations: dict[str, dict[str, str]],
        language: str,
        expected_localized_description: str,
        new_description: str,
    ) -> VideoDescriptionSnapshot:
        """Retry only safe GET verification after a completed one-shot locale PUT.

        A videos.update may succeed while the first owner GET still returns the
        old localized text. Only the base writer can issue a PUT; this recovery
        path never calls it again and requires exact locale + metadata equality.
        """
        with reserve_shared_quota(
            self._quota_guard,
            50 + (2 + len(self._verification_delays)) * self.retry_policy.max_attempts,
            YouTubeWriteError,
        ):
            try:
                return super().replace_localized_description(
                    video_id=video_id,
                    expected_channel_id=expected_channel_id,
                    expected_title=expected_title,
                    expected_primary_description=expected_primary_description,
                    expected_snippet_fields=expected_snippet_fields,
                    expected_privacy=expected_privacy,
                    expected_duration=expected_duration,
                    expected_localizations=expected_localizations,
                    language=language,
                    expected_localized_description=expected_localized_description,
                    new_description=new_description,
                )
            except YouTubeWriteError as exc:
                # Preflight conflicts, HTTP failures, quota and ambiguous PUT
                # responses never enter this read-only consistency path.
                if not str(exc).startswith(f"Localized postflight drift for {video_id}:"):
                    raise
                if not self._verification_delays:
                    raise

            expected_map = copy.deepcopy(expected_localizations)
            expected_map[language]["description"] = new_description
            last_failed: list[str] = []
            for delay in self._verification_delays:
                if delay:
                    self._sleep(delay)
                observed = self.read_description(video_id)
                failures = localization_postflight_drift(
                    observed,
                    video_id=video_id,
                    channel_id=expected_channel_id,
                    title=expected_title,
                    primary_description=expected_primary_description,
                    snippet_fields=expected_snippet_fields,
                    privacy=expected_privacy,
                    duration=expected_duration,
                    localizations=expected_map,
                )
                if not failures:
                    return observed
                last_failed = failures

            raise YouTubeWriteError(
                f"Localized postflight still mismatched after {1 + len(self._verification_delays)} "
                f"safe GET reads for {video_id}: {', '.join(last_failed)}. "
                "The PUT must not be retried; reconcile against the owner API."
            )

    def restore_description_if_current(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        expected_current_description: str,
        restore_description: str,
    ) -> VideoDescriptionSnapshot:
        """Reassert the backup when live text is one of the two known states.

        Even when a read already shows the original text, an earlier successful
        update may still be propagating. Writing the original state again makes
        the rollback the newest mutation and prevents a delayed after-state from
        resurfacing later.
        """

        current = self.read_description(video_id)
        if current.channel_id != expected_channel_id:
            raise YouTubeRevisionConflictError(
                f"Channel mismatch for {video_id}: expected {expected_channel_id}, got {current.channel_id}."
            )
        known_after = descriptions_equivalent(current.description, expected_current_description)
        known_original = descriptions_equivalent(current.description, restore_description)
        if not known_after and not known_original:
            raise YouTubeRevisionConflictError(
                f"Description mismatch for {video_id}; refusing recovery because live text is neither the "
                "planned after-state nor the original backup."
            )
        return self._write_description(current=current, new_description=restore_description)
