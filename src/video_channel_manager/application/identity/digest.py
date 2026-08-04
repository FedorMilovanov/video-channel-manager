from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence


_JSON_SCALARS = (str, int, float, bool, type(None))


def _assert_json_value(value: object) -> None:
    if isinstance(value, _JSON_SCALARS):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("identity evidence contains a non-string object key")
            _assert_json_value(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _assert_json_value(item)
        return
    raise ValueError(f"identity evidence contains a non-JSON value: {type(value).__name__}")


def evidence_digest(value: object) -> str:
    _assert_json_value(value)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
