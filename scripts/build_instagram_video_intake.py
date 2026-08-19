from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_channel_manager.editorial.instagram_video_intake import build_instagram_video_intake
from video_channel_manager.exchange.audit_package import AuditPackage


def _load_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a provider-inert Instagram Reel intake from a read-only YouTube AuditPackage."
    )
    parser.add_argument("audit_package", type=Path)
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("content/mappings/youtube-vk-reviewed-20260727.json"),
    )
    parser.add_argument(
        "--comments-dir",
        type=Path,
        default=Path("content/youtube-comments"),
    )
    parser.add_argument("--expected-channel", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    audit = AuditPackage.model_validate_json(args.audit_package.read_text(encoding="utf-8"))
    mapping_payload = _load_json_object(args.mapping)
    mapping = {str(key): str(value) for key, value in mapping_payload.items()}
    reviewed_ids = {path.stem for path in args.comments_dir.glob("*.json")}

    result = build_instagram_video_intake(
        audit,
        frozen_youtube_vk_mapping=mapping,
        reviewed_video_ids=reviewed_ids,
        expected_channel_id=args.expected_channel,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Instagram intake built: "
        f"current={result['counts']['current_videos']} "
        f"new={result['counts']['new_current_vs_frozen_mapping']} "
        f"historical_missing={result['counts']['historical_mapped_missing_from_current_snapshot']} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
