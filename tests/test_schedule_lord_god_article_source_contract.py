from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "schedule_lord_god_article_wave_v3.py"


def load_module() -> Any:
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(
        "lord_god_article_source_contract_test",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(
        self,
        *,
        content: bytes,
        content_type: str,
        status_code: int = 200,
    ) -> None:
        self.content = content
        self.headers = {"content-type": content_type}
        self.status_code = status_code

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, responses: dict[str, FakeResponse], **_: object) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __enter__(self) -> FakeHttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str) -> FakeResponse:
        self.calls.append(url)
        return self.responses[url]


def metadata_html(
    article_url: str,
    image_url: str,
    *,
    title: str = "Проверенный заголовок публикации",
    description: str | None = None,
) -> str:
    usable_description = description or (
        "Проверенное описание публикации и её содержания. " * 3
    )
    return (
        '<link rel="canonical" href="'
        + article_url
        + '">'
        + '<meta property="og:url" content="'
        + article_url
        + '">'
        + '<meta property="og:title" content="'
        + title
        + '">'
        + '<meta property="og:description" content="'
        + usable_description
        + '">'
        + '<meta property="og:image" content="'
        + image_url
        + '">'
        + '<meta name="robots" content="index, follow">'
    )


def test_load_policy_materializes_native_source_contract() -> None:
    module = load_module()

    policy = module.load_policy(ROOT)
    gill = next(item for item in policy["operations"] if item["id"] == "gill-part1")

    assert (
        gill["image_url"]
        == "https://gospod-bog.ru/images/og-dzhon-gill-chast-1-chelovek.webp"
    )
    assert (
        gill["legacy_policy_image_url"]
        == "https://gospod-bog.ru/images/og-gill-authentic-study-cover.webp"
    )
    assert gill["metadata_source_path"].endswith("GillPart1PageHead.astro")
    assert gill["source_path"].endswith("GillPart1HeaderHero.astro")
    assert gill["source_markers"] == [
        "Джон Гилл (1697–1771). Часть I: Человек",
        "самостоятельно освоивший иврит",
    ]
    assert gill["legacy_policy_source_path"].endswith(
        "dzhon-gill-chast-1-chelovek.mdx"
    )
    assert policy["source_contract_sha256"] == module.EXPECTED_SOURCE_CONTRACT_SHA
    assert module.contract_identity(policy).startswith("sha256:")
    assert module.contract_identity(policy) != policy["policy_sha256"]


def test_source_contract_covers_forty_unique_resources() -> None:
    module = load_module()
    policy = module.load_policy(ROOT)

    urls = {
        url
        for operation in policy["operations"]
        for url in (
            module.normalize_url(operation["url"]),
            module.normalize_url(operation["image_url"]),
            module.source_raw_url(policy, operation),
            module.metadata_raw_url(policy, operation),
        )
    }

    assert len(urls) == 40
    assert len({item["source_path"] for item in policy["operations"]}) == 10
    assert len({item["metadata_source_path"] for item in policy["operations"]}) == 10
    assert all("/src/content/articles/" not in url for url in urls)


def test_source_audit_aggregates_all_findings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = module.load_policy(ROOT)
    responses: dict[str, FakeResponse] = {}

    for operation in policy["operations"]:
        article_url = module.normalize_url(operation["url"])
        image_url = module.normalize_url(operation["image_url"])
        content_url = module.source_raw_url(policy, operation)
        metadata_url = module.metadata_raw_url(policy, operation)
        markers = [str(value) for value in operation["source_markers"]]
        metadata_source = metadata_html(article_url, image_url)
        page_html = metadata_source + "\n" + "\n".join(markers)
        source_text = "\n".join(markers)

        responses[article_url] = FakeResponse(
            content=page_html.encode(),
            content_type="text/html; charset=utf-8",
        )
        responses[image_url] = FakeResponse(
            content=b"synthetic-webp",
            content_type="image/webp",
        )
        responses[content_url] = FakeResponse(
            content=source_text.encode(),
            content_type="text/plain; charset=utf-8",
        )
        responses[metadata_url] = FakeResponse(
            content=metadata_source.encode(),
            content_type="text/plain; charset=utf-8",
        )

    first = policy["operations"][0]
    first_url = module.normalize_url(first["url"])
    responses[first_url] = FakeResponse(
        content=(
            metadata_html(
                first_url,
                "https://gospod-bog.ru/images/wrong-first.webp",
            )
            + "\n"
            + "\n".join(str(value) for value in first["source_markers"])
        ).encode(),
        content_type="text/html; charset=utf-8",
    )

    second = policy["operations"][1]
    second_metadata_url = module.metadata_raw_url(policy, second)
    responses[second_metadata_url] = FakeResponse(
        content=metadata_html(
            "https://gospod-bog.ru/articles/wrong-second/",
            module.normalize_url(second["image_url"]),
        ).encode(),
        content_type="text/plain; charset=utf-8",
    )

    fake_client = FakeHttpClient(responses)
    monkeypatch.setattr(module.sources_module, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        module.sources_module,
        "convert_webp_to_jpeg",
        lambda payload, *, ffmpeg: b"\xff\xd8" + b"x" * 20_000 + b"\xff\xd9",
    )

    rows, manifest = module.materialize_and_verify_sources(
        policy,
        assets_dir=tmp_path / "assets",
        client_factory=lambda **kwargs: fake_client,
    )

    assert len(fake_client.calls) == 40
    assert len(set(fake_client.calls)) == 40
    assert len(rows) == 10
    assert manifest["external_urls_checked"] == 40
    assert manifest["article_pages_verified"] == 9
    assert manifest["live_content_markers_verified"] == 10
    assert manifest["pinned_metadata_files_verified"] == 9
    assert manifest["live_metadata_matches_pinned_source"] == 10
    assert manifest["source_images_verified"] == 10
    assert manifest["pinned_source_files_verified"] == 10
    assert manifest["prepared_jpeg_assets"] == 10
    assert manifest["conflicting_operations"] == 2
    assert manifest["conflicts"] == 3
    assert manifest["status"] == "blocked"
    assert rows[0]["status"] == "conflict"
    assert rows[1]["status"] == "conflict"
    assert rows[9]["status"] == "verified"


def test_live_title_drift_is_blocking() -> None:
    module = load_module()
    article_url = "https://gospod-bog.ru/articles/example/"
    image_url = "https://gospod-bog.ru/images/example.webp"
    live = module.PageMetadata()
    live.feed(metadata_html(article_url, image_url, title="Живой заголовок статьи"))
    pinned = module.PageMetadata()
    pinned.feed(
        metadata_html(article_url, image_url, title="Закреплённый заголовок статьи")
    )
    row: dict[str, Any] = {"conflicts": []}

    assert not module.sources_module._compare_live_and_pinned_metadata(
        live,
        pinned,
        row=row,
    )
    assert row["conflicts"] == [
        {
            "code": "live_metadata_og_title_differs_from_pinned_source",
            "detail": (
                "live='Живой заголовок статьи'; "
                "pinned='Закреплённый заголовок статьи'"
            ),
        }
    ]


def test_blocked_source_audit_is_written_before_vk_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    policy = module.load_policy(ROOT)
    manifest = {
        "schema_name": "video-manager.vk-lord-god-article-assets",
        "schema_version": 4,
        "status": "blocked",
        "expected_external_resources": 40,
        "external_urls_checked": 40,
        "article_pages_verified": 9,
        "live_content_markers_verified": 10,
        "source_images_verified": 10,
        "pinned_source_files_verified": 10,
        "pinned_metadata_files_verified": 9,
        "live_metadata_matches_pinned_source": 9,
        "prepared_jpeg_assets": 10,
        "conflicts": 2,
        "items": [],
        "manifest_sha256": "sha256:test",
    }

    monkeypatch.setattr(module.workflow_module, "load_policy", lambda repo: policy)
    monkeypatch.setattr(
        module.workflow_module,
        "materialize_and_verify_sources",
        lambda *args, **kwargs: ([], manifest),
    )

    def unexpected_settings() -> object:
        raise AssertionError("VK/settings preflight must not run")

    monkeypatch.setattr(module.workflow_module, "get_settings", unexpected_settings)

    with pytest.raises(RuntimeError, match="source audit blocked"):
        module.workflow_module.run(tmp_path, mode="plan")

    report_path = (
        tmp_path
        / "data"
        / "vk-wall"
        / module.DECISION_SET_ID
        / "source-audit.json"
    )
    assert report_path.is_file()
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["conflicts"] == 2
    assert written["status"] == "blocked"
