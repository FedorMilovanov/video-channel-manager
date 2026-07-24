from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from video_channel_manager.domain.enums import OperationType, PlatformName
from video_channel_manager.domain.models import ChannelRecord, CollectionRecord, VideoRecord


@dataclass(frozen=True, slots=True)
class PlatformCapabilities:
    platform: PlatformName
    readable: bool
    supported_operations: frozenset[OperationType]


@runtime_checkable
class PlatformAdapter(Protocol):
    def capabilities(self) -> PlatformCapabilities: ...

    def list_channels(self) -> list[ChannelRecord]: ...

    def list_videos(self, channel_id: str) -> list[VideoRecord]: ...

    def list_collections(self, channel_id: str) -> list[CollectionRecord]: ...


class PlatformRegistry:
    def __init__(self) -> None:
        self._adapters: dict[PlatformName, PlatformAdapter] = {}

    def register(self, platform: PlatformName, adapter: PlatformAdapter) -> None:
        if platform in self._adapters:
            raise ValueError(f"adapter already registered for {platform}")
        self._adapters[platform] = adapter

    def get(self, platform: PlatformName) -> PlatformAdapter:
        try:
            return self._adapters[platform]
        except KeyError as exc:
            raise KeyError(f"no adapter registered for {platform}") from exc
