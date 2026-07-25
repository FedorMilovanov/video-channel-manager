from __future__ import annotations

import time
from collections.abc import Callable, Sequence

import httpx

from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.store import TokenStore
from video_channel_manager.platforms.youtube.writer import (
    VideoDescriptionSnapshot,
    YouTubeDescriptionWriter as BaseYouTubeDescriptionWriter,
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
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            client_config=client_config,
            token_store=token_store,
            account_alias=account_alias,
            http_client=http_client,
            api_base_url=api_base_url,
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
