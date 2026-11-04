"""One-operation canary for the Lord God community access key.

Builds exactly one postponed *text* wall operation and executes it through
the reviewed ``LordGodPostponedWallAdapter`` (policy
``vk-lord-god-postponed-wall-v4``). This proves end-to-end that the community
key of community 60805374 can create a postponed post before the full wave
is applied. The script refuses to run without the exact confirmation
string, a safely future publish_date and the bound account alias; it never
prints the token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.wave_engine.models import (
    MutationClass,
    ProjectBinding,
    WaveOperation,
    WaveOperationSpec,
)
from video_channel_manager.wave_engine.vk_lord_god_wall_provider import (
    LORD_GOD_ACCOUNT_ALIAS,
    LORD_GOD_COMMUNITY_ID,
    LORD_GOD_OWNER_ID,
    LORD_GOD_PROJECT_KEY,
    LORD_GOD_WALL_OPERATION_KIND,
    LORD_GOD_WALL_POLICY_VERSION,
    LordGodPostponedWallAdapter,
    parse_lord_god_wall_operation,
)


CONFIRMATION = "CANARY-LORD-GOD-COMMUNITY-KEY"
CANARY_SOURCE_ID = "community-key-canary-v1"
DEFAULT_MESSAGE = "«Господь — крепость моя и щит мой; на Него уповало сердце моё, и Он помог мне» (Пс. 27:7)."


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_canary_operation(*, publish_date: int, message: str = DEFAULT_MESSAGE) -> WaveOperation:
    """Build the single deterministic canary operation (provider-inert)."""

    normalized = canonical_vk_text(message)
    if message != normalized or not message:
        raise ValueError("canary message must be canonical VK plain text")
    now = int(datetime.now(UTC).timestamp())
    if publish_date <= now + 3600:
        raise ValueError("canary publish_date must be more than one hour in the future")
    if publish_date > now + 7 * 24 * 3600:
        raise ValueError("canary publish_date must be within the next 7 days")
    message_sha = _sha256_text(message)
    guid_material = f"{CANARY_SOURCE_ID}:{publish_date}:{message_sha}".encode()
    guid = "vcm-lgw-" + hashlib.sha256(guid_material).hexdigest()[:24]
    payload = {
        "content_kind": "text",
        "account_alias": LORD_GOD_ACCOUNT_ALIAS,
        "message": message,
        "message_sha256": message_sha,
        "publish_date": publish_date,
        "guid": guid,
        "source_id": CANARY_SOURCE_ID,
    }
    spec = WaveOperationSpec(
        order_key=f"{publish_date:010d}-text-{CANARY_SOURCE_ID}",
        operation_kind=LORD_GOD_WALL_OPERATION_KIND,
        mutation_class=MutationClass.AMBIGUOUS_MUTATION,
        payload=payload,
    )
    operation = WaveOperation.build(
        sequence=0,
        project=ProjectBinding(
            project_key=LORD_GOD_PROJECT_KEY,
            community_id=LORD_GOD_COMMUNITY_ID,
            owner_id=LORD_GOD_OWNER_ID,
        ),
        source_snapshot_id=hashlib.sha256(b"lord-god-community-key-canary-v1").hexdigest(),
        policy_version=LORD_GOD_WALL_POLICY_VERSION,
        spec=spec,
    )
    # Fail closed locally if the provider parser would reject the operation.
    parse_lord_god_wall_operation(operation)
    return operation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-date", type=int, required=True, help="Unix epoch seconds (UTC)")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--account", default=LORD_GOD_ACCOUNT_ALIAS)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)

    if args.confirm != CONFIRMATION:
        raise SystemExit(f"--confirm must be exactly {CONFIRMATION}")
    if args.account != LORD_GOD_ACCOUNT_ALIAS:
        raise SystemExit(f"--account must be exactly {LORD_GOD_ACCOUNT_ALIAS}")

    operation = build_canary_operation(publish_date=args.publish_date, message=args.message)
    adapter = LordGodPostponedWallAdapter(account_alias=args.account)
    try:
        result = adapter.execute(operation)
    finally:
        adapter.close()
    print(
        json.dumps(
            {"canary": CANARY_SOURCE_ID, "operation_id": operation.operation_id, "result": result}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
