"""Single-purpose read-only audit of Milovi Cake's public VK wall via service key.

Usage (locally): python scripts/audit_milovi_school_vk_public_wall.py
    --env-file <ignored local .env containing VK_MILOVI_CAKE_SERVICE_KEY>
    --output <untracked local operator-output path>

No wall writes, login flows, generic VK_API_TOKEN fallbacks, or secret output.
"""

from __future__ import annotations

import argparse
import json
import re
from hmac import compare_digest
from pathlib import Path

from dotenv import dotenv_values

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.client import VkApiClient, VkApiError
from video_channel_manager.platforms.vk.milovi_school_public_wall_audit import (
    MILOVI_SERVICE_ALIAS,
    classify_editorial_wall_posts,
    collect_exact_public_wall,
    source_ids_from_editorial,
)
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore


def run(*, env_file: Path, output: Path, editorial_path: Path) -> int:
    source_ids = source_ids_from_editorial(editorial_path.read_text(encoding="utf-8"))
    env = dotenv_values(env_file)
    key = env.get("VK_MILOVI_CAKE_SERVICE_KEY")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{30,2048}", key.strip()):
        print("SERVICE_WALL_READ=BLOCKED_MISSING_OR_MALFORMED_SERVICE_KEY; provider_calls=0; writes=0")
        return 2
    key = key.strip()

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    for token_path in store.token_dir.glob("*.json"):
        stored_alias = store.validate_alias(token_path.stem)
        if stored_alias == MILOVI_SERVICE_ALIAS:
            continue
        if compare_digest(key, store.load_token(stored_alias).access_token):
            print("SERVICE_WALL_READ=BLOCKED_REUSED_OR_QUARANTINED_CREDENTIAL; provider_calls=0; writes=0")
            return 3

    if store.token_exists(MILOVI_SERVICE_ALIAS):
        installed = store.load_token(MILOVI_SERVICE_ALIAS)
        if installed.token_type != "service" or not compare_digest(installed.access_token, key):
            print("SERVICE_WALL_READ=BLOCKED_EXISTING_ALIAS_DIFFERS; provider_calls=0; writes=0")
            return 4
    else:
        store.save_token(MILOVI_SERVICE_ALIAS, VkAccessToken(access_token=key, token_type="service"))

    client = VkApiClient(
        token_store=store,
        account_alias=MILOVI_SERVICE_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=1,
    )
    try:
        posts = collect_exact_public_wall(client)
    except (VkApiError, ValueError) as exc:
        if isinstance(exc, VkApiError):
            reason = f"API_ERROR_{exc.code}" if exc.code is not None else "API_TRANSPORT_OR_SCHEMA_ERROR"
        else:
            reason = "INCOMPLETE_OR_INVALID_WALL"
        print("SERVICE_WALL_READ=BLOCKED_" + reason + "; writes=0; no automatic retry")
        return 5
    finally:
        client.close()

    result = classify_editorial_wall_posts(posts, source_ids)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        print("SERVICE_WALL_READ=BLOCKED_OUTPUT_EXISTS; writes=0")
        return 6
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    found = sum(p["public_wall_presence"] == "found" for p in result["source_classification"])
    print(f"SERVICE_WALL_READ=COMPLETED; public_posts={len(posts)}; sources_found={found}/10")
    print("POSTPONED_AND_NATIVE_ARTICLES=UNVERIFIED; provider_writes=0; publication_authorized=false")
    print("RESULT_WRITTEN=True")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--editorial-path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "content/editorial/milovi-cake/vk-school-wave-20261105.md",
    )
    args = parser.parse_args()
    raise SystemExit(run(env_file=args.env_file, output=args.output, editorial_path=args.editorial_path))
