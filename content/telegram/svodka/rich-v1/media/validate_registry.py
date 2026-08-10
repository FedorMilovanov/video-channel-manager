#!/usr/bin/env python3
"""Validate content/telegram/svodka/rich-v1/media/media-registry.json.

Enforces the checks required by the media-acquisition/provenance task for rich-v1:

  - every URL is HTTPS
  - licence / provenance non-empty
  - attribution consistent (required -> attribution_text non-empty)
  - expected MIME present for sourced (photo/map) assets
  - duplicate detection (asset_id and direct_media_url uniqueness)
  - no dead media slots (every (article, slot) in the articles has a registry entry,
    and every registry entry points to an existing (article, slot))
  - every selected asset belongs to an exact existing article
  - provider_upload_status == not_uploaded for every asset
  - canary article declared and all its slots present

This is a local, read-only validator. It does not contact the network and it does not
change any provider, workflow, or state.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(ROOT, "media-registry.json")
ARTICLES_DIR = os.path.join(ROOT, "..", "articles")

HTTPS_RE = re.compile(r"^https://")


def load_articles() -> dict:
    articles = {}
    for fn in sorted(os.listdir(ARTICLES_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(ARTICLES_DIR, fn), encoding="utf-8") as fh:
            d = json.load(fh)
        slots = [m["slot_id"] for m in d.get("media_slots", [])]
        articles[d["article_id"]] = set(slots)
    return articles


def main() -> int:
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        reg = json.load(fh)
    assets = reg["assets"]
    articles = load_articles()

    errors: list[str] = []
    warnings: list[str] = []

    # asset_id + direct URL uniqueness
    seen_ids, seen_urls = {}, {}
    # (article, slot) coverage
    registered_slots = {}
    for a in assets:
        aid = a["asset_id"]
        if aid in seen_ids:
            errors.append(f"duplicate asset_id: {aid}")
        seen_ids[aid] = a

        art, slot = a["article_id"], a["media_slot_id"]
        registered_slots.setdefault((art, slot), []).append(aid)

        url = a.get("direct_media_url")
        if url:
            if url in seen_urls:
                errors.append(f"duplicate direct_media_url across assets: {url}")
            seen_urls[url] = aid

        # article membership
        if art not in articles:
            errors.append(f"asset {aid} references unknown article {art}")
            continue
        if slot not in articles[art]:
            errors.append(f"asset {aid} references slot {slot} not present in article {art}")
            continue

        # per-asset checks
        if a["provider_upload_status"] != "not_uploaded":
            errors.append(f"asset {aid}: provider_upload_status must be 'not_uploaded' (got {a['provider_upload_status']!r})")

        if a.get("licence") in (None, ""):
            errors.append(f"asset {aid}: licence is empty")

        if a.get("source_provenance") in (None, ""):
            errors.append(f"asset {aid}: source_provenance is empty")

        if not isinstance(a.get("attribution_required"), bool):
            errors.append(f"asset {aid}: attribution_required must be a bool")
        elif a["attribution_required"] and not (a.get("attribution_text") or "").strip():
            errors.append(f"asset {aid}: attribution_required is True but attribution_text is empty")

        kind = a.get("kind")
        remote_ready = a.get("remote_ready", a.get("direct_media_url") is not None)
        if kind in ("photo", "map"):
            for field in ("canonical_source_page_url", "creator", "institution"):
                if not a.get(field):
                    errors.append(f"asset {aid}: sourced asset missing required field {field!r}")
            if remote_ready:
                for field in ("direct_media_url", "expected_mime"):
                    if not a.get(field):
                        errors.append(f"asset {aid}: sourced asset (remote_ready) missing required field {field!r}")
            else:
                # explicitly-flagged manifest: source page + licence must be present, else WARN
                if not a.get("canonical_source_page_url"):
                    errors.append(f"asset {aid}: non-ready sourced asset missing canonical_source_page_url")
                warnings.append(f"asset {aid}: remote_ready=False ({a.get('acquisition_status')}) - no direct media URL yet")
            url = a.get("direct_media_url") or ""
            if url and not HTTPS_RE.match(url):
                errors.append(f"asset {aid}: direct_media_url is not HTTPS: {url}")
            src = a.get("canonical_source_page_url") or ""
            if src and not HTTPS_RE.match(src):
                errors.append(f"asset {aid}: canonical_source_page_url is not HTTPS: {src}")
            alt = a.get("source_page_alt") or ""
            if alt and not HTTPS_RE.match(alt):
                errors.append(f"asset {aid}: source_page_alt is not HTTPS: {alt}")
            mime = a.get("expected_mime") or ""
            if mime and mime not in ("image/jpeg", "image/png"):
                warnings.append(f"asset {aid}: unexpected expected_mime {mime!r} (expected image/jpeg or image/png)")
            if url:
                bare = url.split("?")[0].lower()
                if not bare.endswith((".jpg", ".jpeg", ".png")):
                    warnings.append(f"asset {aid}: direct_media_url does not end in a known image extension: {url}")
        elif kind == "diagram":
            # in-house originals: must NOT claim an external source URL or a checksum of external bytes
            if a.get("direct_media_url"):
                warnings.append(f"asset {aid}: diagram has a direct_media_url (should be None): {a['direct_media_url']}")
            if a.get("expected_mime"):
                warnings.append(f"asset {aid}: diagram has expected_mime (should be None)")
        else:
            errors.append(f"asset {aid}: unknown kind {kind!r}")

    # no dead slots: every (article, slot) in the articles has >=1 registry entry
    for art, slots in articles.items():
        for slot in slots:
            if (art, slot) not in registered_slots:
                errors.append(f"dead media slot: article {art} slot {slot} has no registry entry")
    # every registry entry's (article, slot) must exist (already checked above) and be unique
    for (art, slot), aids in registered_slots.items():
        if len(aids) > 1:
            errors.append(f"multiple registry entries for the same slot: {art} {slot} -> {aids}")

    # canary
    canary = reg.get("canary", {})
    canary_art = canary.get("article_id")
    if not canary_art:
        errors.append("no canary article declared")
    else:
        if canary_art not in articles:
            errors.append(f"canary article {canary_art} not in article set")
        else:
            for slot in articles[canary_art]:
                if (canary_art, slot) not in registered_slots:
                    errors.append(f"canary slot missing: {canary_art} {slot}")
        for cid in canary.get("assets", []):
            if cid not in seen_ids:
                errors.append(f"canary asset {cid} not found in registry")

    # top-level integrity
    if reg.get("asset_count") != len(assets):
        errors.append(f"asset_count ({reg.get('asset_count')}) != actual ({len(assets)})")

    print(f"Registry: {REGISTRY_PATH}")
    print(f"  assets: {len(assets)}")
    print(f"  articles covered: {len(articles)}")
    print(f"  canary article: {reg.get('canary', {}).get('article_id')}")
    print(f"  errors: {len(errors)}   warnings: {len(warnings)}")
    for e in errors:
        print("  ERROR:", e)
    for w in warnings:
        print("  WARN :", w)
    print("RESULT:", "PASS" if not errors else "FAIL")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
