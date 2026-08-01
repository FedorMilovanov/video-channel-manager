from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V3_SCRIPT = Path(__file__).with_name("vk_shorts_reset_20260801_v3.py")
SPEC = importlib.util.spec_from_file_location("vk_shorts_reset_v3", V3_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load V3 executor: {V3_SCRIPT}")
v3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v3
SPEC.loader.exec_module(v3)
base = v3.base
ORIGINAL_VIDEO_STATE = base.video_state


def video_state(raw: dict[str, Any]) -> dict[str, Any]:
    """Ignore VK's stale processing flag after the ordinary 16:9 object is usable."""
    state = ORIGINAL_VIDEO_STATE(raw)
    state["processing_api"] = state["processing"]
    state["converting_api"] = state["converting"]
    ready = (
        state["type"] == "video"
        and state["width"] == 1280
        and state["height"] == 720
        and isinstance(state["duration"], int)
        and state["duration"] > 0
        and not state["converting"]
    )
    if ready:
        state["processing"] = False
        state["readiness"] = "ordinary_video_1280x720"
    return state


base.video_state = video_state
v3.v2.base.video_state = video_state


if __name__ == "__main__":
    try:
        raise SystemExit(base.main())
    except (base.OperationError, base.UnknownOutcome) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
