from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from video_channel_manager.telegram_multichannel_release import load_release, save_release
from video_channel_manager.telegram_release_review import authorize_release_candidate


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Authorize one exact immutable generic Telegram release candidate")
    root.add_argument("--candidate", type=Path, required=True)
    root.add_argument("--expected-candidate-sha256", required=True)
    root.add_argument("--reviewed-by", required=True)
    root.add_argument("--reviewed-at", required=True, help="Timezone-aware ISO-8601 timestamp")
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    candidate = load_release(args.candidate)
    approved = authorize_release_candidate(
        candidate,
        expected_candidate_sha256=args.expected_candidate_sha256,
        reviewed_by=args.reviewed_by,
        reviewed_at=datetime.fromisoformat(args.reviewed_at),
    )
    save_release(args.output, approved)
    print(
        json.dumps(
            {
                "authorized": approved.release_authorized,
                "release_id": approved.release_id,
                "reviewed_candidate_sha256": approved.reviewed_candidate_sha256,
                "reviewed_by": approved.reviewed_by,
                "reviewed_at": approved.reviewed_at.isoformat() if approved.reviewed_at else None,
                "approved_release_sha256": approved.digest,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
