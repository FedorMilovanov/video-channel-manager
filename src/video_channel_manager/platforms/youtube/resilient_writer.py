from __future__ import annotations

import random
import time
from collections.abc import Callable, Sequence

import httpx

from video_channel_manager.platforms.http import RequestRateLimiter, RetryPolicy
from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.store import TokenStore
from video_channel_manager.platforms.youtube.writer import (
    VideoDescriptionSnapshot,
    YouTubeDescriptionWriter as BaseYouTubeDescriptionWriter,
    YouTubeRevisionConflictError,
    YouTubeWriteError,
    descriptions_equivalent,
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
    ) -> VideoDescriptionSnapshot:
        try:
            return super()._write_description(current=current, new_description=new_description)
        except YouTubeWriteError as exc:
            expected_message = f"Verification failed after updating description for {current.video_id}."
            if str(exc) != expected_message:
                raise

        last_snapshot: VideoDescriptionSnapshot | None = None
        for delay in self._verification_delays:
            if delay:
                self._sleep(delay)
            last_snapshot = self.read_description(current.video_id)
            if descriptions_equivalent(last_snapshot.description, new_description):
                return last_snapshot

        observed = "unavailable" if last_snapshot is None else last_snapshot.revision
        raise YouTubeWriteError(
            f"Verification failed after updating description for {current.video_id} "
            f"after {1 + len(self._verification_delays)} reads; last revision: {observed}."
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
