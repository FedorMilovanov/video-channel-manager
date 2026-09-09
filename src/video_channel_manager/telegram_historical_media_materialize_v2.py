from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from video_channel_manager.telegram_historical_archival_revision import (
    HistoricalRevisionPackageV2,
    _probe_image,
    preflight_historical_archival_revision,
)
from video_channel_manager.telegram_historical_media_v2 import acquire_historical_media_v2

_RENDER_DATE = "2026-09-09"


@dataclass(frozen=True)
class RenderPlan:
    asset_id: str
    output_file_name: str
    transform: Literal["identity_copy", "pdf_page", "json_record_card", "epub_html_card"]
    exhibit_kind: Literal[
        "archival_portrait",
        "primary_document_facsimile",
        "critical_edition_facsimile",
        "contextual_historical_map",
        "institutional_catalog_record",
        "official_document_excerpt",
    ]
    page: int | None = None
    rotation_clockwise: int = 0
    archive_member: str | None = None
    title: str | None = None


_PLANS = (
    RenderPlan(
        "img-bunyan-v3-hero-archive",
        "bunyan-v3-hero-nlw-4672796.jpg",
        "identity_copy",
        "archival_portrait",
    ),
    RenderPlan(
        "img-bunyan-v3-gaol-list-1667",
        "bunyan-v3-bedford-hsa1667-w58.jpg",
        "identity_copy",
        "primary_document_facsimile",
    ),
    RenderPlan(
        "img-judson-v3-hero-archive",
        "judson-v3-hero-brown-healy-1846.jpg",
        "identity_copy",
        "archival_portrait",
    ),
    RenderPlan(
        "img-judson-v3-wayland-source-pdf",
        "judson-v3-wayland-burmese-bible-completion-page-85.png",
        "pdf_page",
        "primary_document_facsimile",
        page=85,
    ),
    RenderPlan(
        "img-spurgeon-cholera-v3-hero-archive",
        "spurgeon-cholera-v3-hero-nlw-4671161.jpg",
        "identity_copy",
        "archival_portrait",
    ),
    RenderPlan(
        "img-spurgeon-cholera-v3-snow-map-archive",
        "spurgeon-cholera-v3-snow-map-wellcome-l0072142.jpg",
        "identity_copy",
        "contextual_historical_map",
    ),
    RenderPlan(
        "img-carey-v3-enquiry-source-pdf",
        "carey-v3-enquiry-title-page-1.png",
        "pdf_page",
        "primary_document_facsimile",
        page=1,
    ),
    RenderPlan(
        "img-carey-v3-bms-minute-source-pdf",
        "carey-v3-bms-minute-page-85.png",
        "pdf_page",
        "primary_document_facsimile",
        page=85,
    ),
    RenderPlan(
        "img-fuller-v3-gospel-worthy-1785-pr1",
        "fuller-v3-gospel-worthy-1785-pr1.png",
        "identity_copy",
        "primary_document_facsimile",
    ),
    RenderPlan(
        "img-fuller-v3-taylor-wellcome-catalog",
        "fuller-v3-taylor-wellcome-catalog-record.png",
        "json_record_card",
        "institutional_catalog_record",
        title="Wellcome Collection — Dan Taylor, 1786",
    ),
    RenderPlan(
        "img-tyndale-v3-worms-source-pdf",
        "tyndale-v3-worms-1526-page-44.png",
        "pdf_page",
        "critical_edition_facsimile",
        page=44,
    ),
    RenderPlan(
        "img-tyndale-v3-prison-letter-demaus-pdf",
        "tyndale-v3-prison-letter-1535-page-462.png",
        "pdf_page",
        "critical_edition_facsimile",
        page=462,
        rotation_clockwise=90,
    ),
    RenderPlan(
        "img-stam-v3-wheaton-telegram",
        "stam-v3-wheaton-telegram.jpg",
        "identity_copy",
        "primary_document_facsimile",
    ),
    RenderPlan(
        "img-stam-v3-frus-1934-epub",
        "stam-v3-frus-d381-excerpt.png",
        "epub_html_card",
        "official_document_excerpt",
        archive_member="OEBPS/d381.html",
        title="U.S. Department of State FRUS 1934 — Document 381",
    ),
    RenderPlan(
        "img-sattler-v3-schleitheim-bsb-00001",
        "sattler-v3-schleitheim-bsb-00001.jpg",
        "identity_copy",
        "primary_document_facsimile",
    ),
    RenderPlan(
        "img-sattler-v3-letter316-source-pdf",
        "sattler-v3-letter-316-page-1.png",
        "pdf_page",
        "critical_edition_facsimile",
        page=1,
    ),
)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _repo_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _render_pdf_page(source: Path, target: Path, *, page: int, rotation_clockwise: int) -> None:
    if page < 1:
        raise ValueError("PDF render page must be 1-based")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = target if rotation_clockwise == 0 else target.with_name(target.stem + "-raw.png")
    prefix = raw.with_suffix("")
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page),
            "-l",
            str(page),
            "-png",
            "-r",
            "180",
            "-singlefile",
            str(source),
            str(prefix),
        ],
        check=True,
    )
    if rotation_clockwise:
        from PIL import Image

        with Image.open(raw) as image:
            image.rotate(-rotation_clockwise, expand=True).save(target, format="PNG")
        raw.unlink()


def _plain_html(value: str) -> str:
    without_script = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", without_script)
    return " ".join(html.unescape(without_tags).split())


def _write_text_card(target: Path, *, title: str, body: str, footer: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 1000), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=38)
    body_font = ImageFont.load_default(size=25)
    footer_font = ImageFont.load_default(size=20)
    draw.text((80, 70), title, fill=(0, 0, 0), font=title_font)
    y = 155
    for paragraph in body.split("\n"):
        for line in textwrap.wrap(paragraph, width=92, break_long_words=False, break_on_hyphens=False):
            draw.text((80, y), line, fill=(0, 0, 0), font=body_font)
            y += 34
            if y > 860:
                break
        if y > 860:
            break
        y += 14
    draw.text((80, 940), footer, fill=(0, 0, 0), font=footer_font)
    image.save(target, format="PNG", optimize=False)


def _render_json_record(source: Path, target: Path, *, title: str) -> dict[str, object]:
    value = _read_json(source)
    if not isinstance(value, dict):
        raise ValueError("institutional catalogue source must be a JSON object")
    if value.get("id") != "d2cy4t36":
        raise ValueError("Wellcome catalogue record identity differs")
    record_title = str(value.get("title") or "").strip()
    if not record_title:
        raise ValueError("Wellcome catalogue record has no title")
    _write_text_card(
        target,
        title=title,
        body=f"Record ID: d2cy4t36\n\n{record_title}",
        footer="Institutional catalogue record — not a facsimile of the 1786 title page.",
    )
    return {"kind": "institutional_catalog_record", "record_id": "d2cy4t36"}


def _render_epub_excerpt(source: Path, target: Path, *, member: str, title: str) -> dict[str, object]:
    with zipfile.ZipFile(source) as archive:
        if member not in archive.namelist():
            raise ValueError(f"FRUS EPUB member missing: {member}")
        text = _plain_html(archive.read(member).decode("utf-8", errors="strict"))
    lowered = text.casefold()
    if "stam" not in lowered or "baby" not in lowered:
        raise ValueError("FRUS document 381 does not contain the expected Stam/baby anchors")
    anchor = lowered.find("stam")
    start = max(0, anchor - 400)
    excerpt = text[start : start + 2200]
    _write_text_card(
        target,
        title=title,
        body=excerpt,
        footer="Official-document excerpt rendered from exact pinned FRUS EPUB member OEBPS/d381.html.",
    )
    return {"kind": "official_document_excerpt", "epub_member": member}


def _materialize_one(
    plan: RenderPlan,
    *,
    source: Path,
    target: Path,
) -> dict[str, object]:
    if plan.transform == "identity_copy":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return {"kind": "identity_copy"}
    if plan.transform == "pdf_page":
        if plan.page is None:
            raise ValueError(f"PDF plan has no page: {plan.asset_id}")
        _render_pdf_page(source, target, page=plan.page, rotation_clockwise=plan.rotation_clockwise)
        return {
            "kind": "pdf_page_render",
            "pdf_page_1_based": plan.page,
            "dpi": 180,
            "rotation_degrees_clockwise": plan.rotation_clockwise,
        }
    if plan.transform == "json_record_card":
        if plan.title is None:
            raise ValueError(f"JSON card plan has no title: {plan.asset_id}")
        return _render_json_record(source, target, title=plan.title)
    if plan.transform == "epub_html_card":
        if plan.title is None or plan.archive_member is None:
            raise ValueError(f"EPUB card plan is incomplete: {plan.asset_id}")
        return _render_epub_excerpt(source, target, member=plan.archive_member, title=plan.title)
    raise AssertionError(plan.transform)


def _binary_identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    mime, width, height = _probe_image(data)
    return {
        "sha256": _sha256(data),
        "byte_length": len(data),
        "mime": mime,
        "width": width,
        "height": height,
        "git_blob_sha": _git_blob(data),
    }


def _purpose_for(kind: str) -> tuple[str, str]:
    if kind == "archival_portrait":
        return (
            "Identify the historical person using an attributed archival portrait.",
            "The portrait identifies the subject only and is not evidence for the narrative event itself.",
        )
    if kind == "contextual_historical_map":
        return (
            "Show the documented historical geographic context without reconstructing an unstated scene.",
            "The map supplies geographic context only and does not depict the sermon or pastoral actions described in the post.",
        )
    if kind == "institutional_catalog_record":
        return (
            "Show the exact institutional catalogue record for the opposing 1786 work.",
            "This is a rendered catalogue record, explicitly not a facsimile or reconstruction of the 1786 title page.",
        )
    if kind == "official_document_excerpt":
        return (
            "Show a bounded excerpt of the exact official diplomatic document tied to the historical chronology.",
            "The excerpt evidences only the text present in the pinned official document and does not upgrade later biographical details.",
        )
    return (
        "Show the exact bound historical document or a deterministic page rendering of that source.",
        "The exhibit evidences only the bound source page and is not a reconstruction of events outside that document.",
    )


def materialize_complete_v2(
    manifest_path: Path,
    *,
    repo_root: Path = Path("."),
    acquisition_dir: Path = Path(".runtime/lordchrist-historical-media-v2"),
) -> dict[str, object]:
    root = repo_root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    batch_path = root / "content/telegram/lordchrist/historical-editorial/v1/v3/batch-manifest-2026-09-08.json"
    manifest_value = _read_json(manifest_path)
    batch_value = _read_json(batch_path)
    if not isinstance(manifest_value, dict) or not isinstance(batch_value, dict):
        raise ValueError("historical materialization inputs must be JSON objects")
    manifest_assets = manifest_value.get("assets")
    topics = batch_value.get("topics")
    if not isinstance(manifest_assets, list) or not isinstance(topics, list):
        raise ValueError("historical materialization input universes are invalid")
    asset_by_id = {item.get("asset_id"): item for item in manifest_assets if isinstance(item, dict)}
    plan_by_id = {plan.asset_id: plan for plan in _PLANS}
    if len(plan_by_id) != 16 or set(plan_by_id) != set(asset_by_id):
        raise ValueError("historical materialization plans do not exactly match the 16-asset manifest")
    topic_by_publication = {
        item.get("publication_id"): item
        for item in topics
        if isinstance(item, dict) and isinstance(item.get("publication_id"), str)
    }
    if len(topic_by_publication) != 8:
        raise ValueError("historical materialization requires exactly eight batch topics")

    acquisition_dir = acquisition_dir if acquisition_dir.is_absolute() else root / acquisition_dir
    shutil.rmtree(acquisition_dir, ignore_errors=True)
    receipt = acquire_historical_media_v2(manifest_path, output_dir=acquisition_dir, repo_root=root)
    receipt_value = receipt.model_dump(mode="json")
    acquired_by_id = {item["asset_id"]: item for item in receipt_value["results"]}
    if set(acquired_by_id) != set(plan_by_id):
        raise ValueError("historical acquisition receipt differs from the complete render plan")

    render_outputs: list[dict[str, object]] = []
    for plan in _PLANS:
        asset = asset_by_id[plan.asset_id]
        if not isinstance(asset, dict):
            raise ValueError(f"historical manifest asset is invalid: {plan.asset_id}")
        publication_id = str(asset["publication_id"])
        topic = topic_by_publication.get(publication_id)
        if not isinstance(topic, dict):
            raise ValueError(f"historical batch topic missing: {publication_id}")
        post_ref = topic.get("post")
        if not isinstance(post_ref, dict) or not isinstance(post_ref.get("path"), str):
            raise ValueError(f"historical batch post ref missing: {publication_id}")
        topic_dir = (root / str(post_ref["path"])).parent
        source = acquisition_dir / str(acquired_by_id[plan.asset_id]["output_file_name"])
        target = topic_dir / "media" / plan.output_file_name
        transform = _materialize_one(plan, source=source, target=target)
        identity = _binary_identity(target)
        render_outputs.append(
            {
                "publication_id": publication_id,
                "slot": asset["slot"],
                "source_asset_id": plan.asset_id,
                "source_sha256": acquired_by_id[plan.asset_id]["source_sha256"],
                "path": _repo_relative(target, root),
                "transform": transform,
                "sha256": identity["sha256"],
                "byte_length": identity["byte_length"],
                "mime": identity["mime"],
                "width": identity["width"],
                "height": identity["height"],
            }
        )

    render_receipt = {
        "schema_name": "video-channel-manager.telegram-historical-media-render-receipt",
        "schema_version": 2,
        "owning_issue": 561,
        "state": "provider_inert",
        "provider_writes_authorized": False,
        "live_eligible": False,
        "provider_write_performed": False,
        "manifest_id": manifest_value.get("manifest_id"),
        "asset_count": 16,
        "outputs": render_outputs,
    }
    render_path = root / (
        "content/telegram/lordchrist/historical-editorial/v1/v3/media-render-receipt-v2-2026-09-09.json"
    )
    render_bytes = _json_bytes(render_receipt)
    render_path.write_bytes(render_bytes)
    render_ref = {"path": _repo_relative(render_path, root), "git_blob_sha": _git_blob(render_bytes)}
    manifest_bytes = manifest_path.read_bytes()
    acquisition_ref = {"path": _repo_relative(manifest_path, root), "git_blob_sha": _git_blob(manifest_bytes)}

    outputs_by_publication: dict[str, list[dict[str, object]]] = {}
    for item in render_outputs:
        outputs_by_publication.setdefault(str(item["publication_id"]), []).append(item)

    package_paths: list[str] = []
    preflight_paths: list[str] = []
    for publication_id, topic in topic_by_publication.items():
        post_ref = topic.get("post")
        verification_ref = topic.get("verification")
        source_shards = topic.get("source_shards")
        theology_ref = batch_value.get("theology_profile")
        if not all(isinstance(value, dict) for value in (post_ref, verification_ref, theology_ref)):
            raise ValueError(f"historical batch refs invalid: {publication_id}")
        if not isinstance(source_shards, list) or not all(isinstance(value, dict) for value in source_shards):
            raise ValueError(f"historical source-shard refs invalid: {publication_id}")
        assert isinstance(post_ref, dict)
        topic_dir = (root / str(post_ref["path"])).parent
        media_values: list[dict[str, object]] = []
        for rendered in outputs_by_publication.get(publication_id, []):
            source_asset_id = str(rendered["source_asset_id"])
            plan = plan_by_id[source_asset_id]
            asset = asset_by_id[source_asset_id]
            assert isinstance(asset, dict)
            accepted_path = root / str(rendered["path"])
            accepted_data = accepted_path.read_bytes()
            purpose, boundary = _purpose_for(plan.exhibit_kind)
            media_values.append(
                {
                    "asset_id": f"{source_asset_id}-exhibit",
                    "slot": asset["slot"],
                    "source_id": asset["source_id"],
                    "acquisition_asset_id": source_asset_id,
                    "exhibit_kind": plan.exhibit_kind,
                    "accepted_file": {
                        "path": str(rendered["path"]),
                        "git_blob_sha": _git_blob(accepted_data),
                    },
                    "accepted_mime": rendered["mime"],
                    "accepted_byte_length": rendered["byte_length"],
                    "accepted_width": rendered["width"],
                    "accepted_height": rendered["height"],
                    "accepted_sha256": rendered["sha256"],
                    "placement_after": "title" if asset["slot"] == "hero" else "evidence",
                    "depicts": f"Archival exhibit for {asset['source_id']} derived from the exact pinned acquisition source.",
                    "purpose": purpose,
                    "claim_boundary": boundary,
                    "rights_basis": asset["rights_basis"],
                    "attribution_text": asset["attribution_text"],
                    "transport_ready": False,
                    "provider_write_performed": False,
                }
            )
        if len(media_values) != 2:
            raise ValueError(f"historical topic does not have exactly two rendered exhibits: {publication_id}")
        package_value = {
            "schema_name": "video-channel-manager.telegram-historical-revision-package",
            "schema_version": 2,
            "revision_id": f"historical-revision-{topic_dir.name}-archival-v2-{_RENDER_DATE}",
            "owning_issue": 561,
            "checked_on": _RENDER_DATE,
            "project_key": "lord-god-strength",
            "channel_username": "@lordchrist",
            "publication_id": publication_id,
            "state": "provider_inert",
            "provider_writes_authorized": False,
            "live_eligible": False,
            "post": post_ref,
            "verification": verification_ref,
            "theology_profile": theology_ref,
            "source_shards": source_shards,
            "acquisition_manifest": acquisition_ref,
            "render_receipt": render_ref,
            "archival_media": media_values,
        }
        package = HistoricalRevisionPackageV2.model_validate(package_value)
        package_path = topic_dir / "revision-package-v2-2026-09-09.json"
        package_path.write_bytes(_json_bytes(package.model_dump(mode="json")))
        report = preflight_historical_archival_revision(package_path, repo_root=root)
        preflight_path = topic_dir / "revision-preflight-v2-2026-09-09.json"
        preflight_path.write_bytes(_json_bytes(report.model_dump(mode="json")))
        package_paths.append(_repo_relative(package_path, root))
        preflight_paths.append(_repo_relative(preflight_path, root))

    summary = {
        "status": "PASS",
        "asset_count": 16,
        "publication_count": 8,
        "render_receipt": _repo_relative(render_path, root),
        "revision_packages": package_paths,
        "preflights": preflight_paths,
        "provider_writes_authorized": False,
        "live_eligible": False,
        "provider_write_performed": False,
    }
    return summary


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Materialize all 16 provider-inert LordChrist archival exhibits")
    root.add_argument("manifest", type=Path)
    root.add_argument("--repo-root", type=Path, default=Path("."))
    root.add_argument(
        "--acquisition-dir",
        type=Path,
        default=Path(".runtime/lordchrist-historical-media-v2"),
    )
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = materialize_complete_v2(
        args.manifest,
        repo_root=args.repo_root,
        acquisition_dir=args.acquisition_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
