from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


VK_FLOOD_CONTROL_SCHEMA = "video-manager.vk-flood-control"
VK_FLOOD_CONTROL_VERSION = 1
VK_FLOOD_CONTROL_CODE = 9


@dataclass(frozen=True, slots=True)
class VkFloodControlEntry:
    method: str
    first_observed_at: str
    last_observed_at: str
    occurrences: int

    @classmethod
    def from_mapping(cls, method: str, raw: Mapping[str, Any]) -> "VkFloodControlEntry":
        normalized_method = method.strip()
        if not normalized_method:
            raise ValueError("VK flood-control method cannot be blank")
        first_observed_at = str(raw.get("first_observed_at") or "")
        last_observed_at = str(raw.get("last_observed_at") or "")
        occurrences = raw.get("occurrences")
        for field, value in (
            ("first_observed_at", first_observed_at),
            ("last_observed_at", last_observed_at),
        ):
            try:
                observed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"VK flood-control {field} must be ISO-8601") from exc
            if observed.tzinfo is None or observed.utcoffset() is None:
                raise ValueError(f"VK flood-control {field} must be timezone-aware")
        if type(occurrences) is not int or occurrences <= 0:
            raise ValueError("VK flood-control occurrences must be a positive exact integer")
        return cls(
            method=normalized_method,
            first_observed_at=first_observed_at,
            last_observed_at=last_observed_at,
            occurrences=occurrences,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "first_observed_at": self.first_observed_at,
            "last_observed_at": self.last_observed_at,
            "occurrences": self.occurrences,
        }


class VkFloodControlGate:
    """Durable, method-scoped VK API code-9 circuit.

    VK documents code 9 separately as Flood control but does not publish a
    universal recovery TTL. The gate therefore never invents a timer. The first
    observed code-9 response opens the method circuit durably; later processes
    fail locally until an operator explicitly clears that exact method.
    """

    def __init__(self, data_dir: Path, account_alias: str) -> None:
        normalized_alias = account_alias.strip()
        if not normalized_alias:
            raise ValueError("VK flood-control account alias cannot be blank")
        self.data_dir = data_dir
        self.account_alias = normalized_alias
        self.path = data_dir / "vk" / "flood-control" / f"{normalized_alias}.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _empty(self) -> dict[str, object]:
        return {
            "schema_name": VK_FLOOD_CONTROL_SCHEMA,
            "schema_version": VK_FLOOD_CONTROL_VERSION,
            "account_alias": self.account_alias,
            "methods": {},
        }

    def _load(self) -> dict[str, object]:
        if not self.path.is_file():
            return self._empty()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read VK flood-control state: {self.path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("VK flood-control state must be a JSON object")
        if payload.get("schema_name") != VK_FLOOD_CONTROL_SCHEMA:
            raise ValueError("Unsupported VK flood-control state schema")
        if payload.get("schema_version") != VK_FLOOD_CONTROL_VERSION:
            raise ValueError("Unsupported VK flood-control state version")
        if payload.get("account_alias") != self.account_alias:
            raise ValueError("VK flood-control state belongs to another account alias")
        methods = payload.get("methods")
        if not isinstance(methods, dict):
            raise ValueError("VK flood-control methods must be an object")
        for method, raw in methods.items():
            if not isinstance(method, str) or not isinstance(raw, Mapping):
                raise ValueError("VK flood-control method entry is invalid")
            VkFloodControlEntry.from_mapping(method, raw)
        return payload

    def _save(self, payload: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def get(self, method: str) -> VkFloodControlEntry | None:
        normalized = method.strip()
        if not normalized:
            raise ValueError("VK flood-control method cannot be blank")
        payload = self._load()
        methods = payload["methods"]
        assert isinstance(methods, dict)
        raw = methods.get(normalized)
        if raw is None:
            return None
        assert isinstance(raw, Mapping)
        return VkFloodControlEntry.from_mapping(normalized, raw)

    def list_open(self) -> tuple[VkFloodControlEntry, ...]:
        payload = self._load()
        methods = payload["methods"]
        assert isinstance(methods, dict)
        return tuple(
            VkFloodControlEntry.from_mapping(method, raw)
            for method, raw in sorted(methods.items())
            if isinstance(method, str) and isinstance(raw, Mapping)
        )

    def record(self, method: str) -> VkFloodControlEntry:
        normalized = method.strip()
        if not normalized:
            raise ValueError("VK flood-control method cannot be blank")
        payload = self._load()
        methods = payload["methods"]
        assert isinstance(methods, dict)
        now = self._now()
        raw = methods.get(normalized)
        if raw is None:
            entry = VkFloodControlEntry(
                method=normalized,
                first_observed_at=now,
                last_observed_at=now,
                occurrences=1,
            )
        else:
            if not isinstance(raw, Mapping):
                raise ValueError("VK flood-control method entry is invalid")
            previous = VkFloodControlEntry.from_mapping(normalized, raw)
            entry = VkFloodControlEntry(
                method=normalized,
                first_observed_at=previous.first_observed_at,
                last_observed_at=now,
                occurrences=previous.occurrences + 1,
            )
        methods[normalized] = entry.as_dict()
        self._save(payload)
        return entry

    def clear(self, method: str) -> bool:
        normalized = method.strip()
        if not normalized:
            raise ValueError("VK flood-control method cannot be blank")
        payload = self._load()
        methods = payload["methods"]
        assert isinstance(methods, dict)
        if normalized not in methods:
            return False
        del methods[normalized]
        self._save(payload)
        return True


__all__ = [
    "VK_FLOOD_CONTROL_CODE",
    "VK_FLOOD_CONTROL_SCHEMA",
    "VK_FLOOD_CONTROL_VERSION",
    "VkFloodControlEntry",
    "VkFloodControlGate",
]
