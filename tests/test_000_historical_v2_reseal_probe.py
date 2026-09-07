from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalSourceRegistry
from video_channel_manager.telegram_research import sha256_json

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "content/telegram/lordchrist/historical-editorial/v1/source-catalog.json"
NEW_JUDSON = ROOT / "content/telegram/lordchrist/historical-editorial/v1/sources/judson-human-v2.json"
JUDSON_POST = ROOT / "content/telegram/lordchrist/historical-editorial/v1/cycles/2026-09-cycle-02/posts/03-judson-burmese-bible.json"


def test_print_exact_v2_reseal_digests() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    new_judson_payload = json.loads(NEW_JUDSON.read_text(encoding="utf-8"))
    new_judson = HistoricalSourceShardV1.model_validate(new_judson_payload)
    new_judson_digest = sha256_json(new_judson.model_dump(mode="json"))

    sources = []
    prospective_refs = []
    for ref in catalog["shards"]:
        current = dict(ref)
        if ref["shard_id"] == "history-sources-judson":
            shard = new_judson
            current.update(
                {
                    "shard_id": new_judson.shard_id,
                    "path": "content/telegram/lordchrist/historical-editorial/v1/sources/judson-human-v2.json",
                    "sha256": new_judson_digest,
                    "source_count": len(new_judson.sources),
                }
            )
        else:
            payload = json.loads((ROOT / ref["path"]).read_text(encoding="utf-8"))
            shard = HistoricalSourceShardV1.model_validate(payload)
        sources.extend(shard.sources)
        prospective_refs.append(current)

    registry = HistoricalSourceRegistry(
        schema_name="video-channel-manager.telegram-historical-source-registry",
        schema_version=1,
        checked_on=catalog["checked_on"],
        sources=tuple(sources),
    )
    prospective_catalog = dict(catalog)
    prospective_catalog["catalog_id"] = "history-source-catalog-lordchrist-human-v2"
    prospective_catalog["total_sources"] = len(registry.sources)
    prospective_catalog["registry_sha256"] = registry.digest
    prospective_catalog["shards"] = prospective_refs

    post_payload = json.loads(JUDSON_POST.read_text(encoding="utf-8"))
    values = {
        "new_judson_shard_sha256": new_judson_digest,
        "new_registry_sha256": registry.digest,
        "new_catalog_sha256": sha256_json(prospective_catalog),
        "new_catalog_total_sources": len(registry.sources),
        "judson_post_sha256": sha256_json(post_payload),
    }
    raise AssertionError(json.dumps(values, sort_keys=True))
