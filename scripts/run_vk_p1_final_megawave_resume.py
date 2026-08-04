#!/usr/bin/env python3
"""Run the final VK P1 megawave with exact retired-wave resume guards."""

from __future__ import annotations

import run_vk_p1_final_megawave as base_runner

from video_channel_manager.platforms.vk.editorial_final_megawave_resume import (
    rebuild_legacy_intermediate_guards,
)

_WAVE6_RETIRED_EXECUTOR = True
if __name__ == "__main__":
    raise SystemExit(
        "This historical executor is retired by Wave 6. "
        "Use the versioned `video-manager wave` engine through the reviewed operator contract."
    )

_original_build_final_megawave_plan = base_runner.build_final_megawave_plan


def _build_resumable_plan(snapshot: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    plan = _original_build_final_megawave_plan(snapshot, policy)
    corrected = rebuild_legacy_intermediate_guards(plan, policy)
    base_runner.verify_final_megawave_plan(snapshot, policy, corrected)
    return corrected


def main() -> int:
    base_runner.build_final_megawave_plan = _build_resumable_plan
    return base_runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
