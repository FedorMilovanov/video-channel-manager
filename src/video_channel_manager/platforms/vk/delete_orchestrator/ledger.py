from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk.delete_orchestrator.ledger_base import LedgerBase
from video_channel_manager.platforms.vk.delete_orchestrator.ledger_operations import OperationLedgerMixin
from video_channel_manager.platforms.vk.delete_orchestrator.ledger_run import RunLedgerMixin
from video_channel_manager.platforms.vk.delete_orchestrator.ledger_schema import iso, parse_time, utc_now


class DeleteLedger(OperationLedgerMixin, RunLedgerMixin, LedgerBase):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.create_schema()


__all__ = ["DeleteLedger", "iso", "parse_time", "utc_now"]
