#!/usr/bin/env python3
"""Generate a self-contained Windows handoff for one DASH/Resi source."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from video_channel_manager.cli.resi import resi_app  # noqa: E402


if __name__ == "__main__":
    resi_app()
