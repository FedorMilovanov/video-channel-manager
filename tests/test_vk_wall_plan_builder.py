from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_builder() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_vk_wall_post_plan.py"
    spec = importlib.util.spec_from_file_location("build_vk_wall_post_plan", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_visible_link_validation_accepts_exact_sources_and_route() -> None:
    builder = _load_builder()
    sources = [
        {"label": "Первый", "url": "https://example.org/one", "kind": "primary"},
        {"label": "Второй", "url": "https://example.org/two", "kind": "primary"},
    ]
    message = (
        "Пост\n\n"
        "https://thelegendarypoet.ru/\n\n"
        "https://example.org/one\n"
        "https://example.org/two"
    )

    builder._validate_visible_links(message, sources=sources, article_url=None)


def test_visible_link_validation_rejects_missing_source() -> None:
    builder = _load_builder()
    sources = [{"label": "Источник", "url": "https://example.org/source", "kind": "primary"}]

    with pytest.raises(ValueError, match="source URL exactly once"):
        builder._validate_visible_links(
            "Пост\n\nhttps://thelegendarypoet.ru/",
            sources=sources,
            article_url=None,
        )


def test_visible_link_validation_rejects_duplicate_source() -> None:
    builder = _load_builder()
    url = "https://example.org/source"
    sources = [{"label": "Источник", "url": url, "kind": "primary"}]

    with pytest.raises(ValueError, match="found 2"):
        builder._validate_visible_links(
            f"Пост\n\nhttps://thelegendarypoet.ru/\n\n{url}\n{url}",
            sources=sources,
            article_url=None,
        )


def test_visible_link_validation_requires_exact_article_route() -> None:
    builder = _load_builder()
    article_url = "https://thelegendarypoet.ru/articles/blok"
    sources = [{"label": "Источник", "url": "https://example.org/source", "kind": "primary"}]

    with pytest.raises(ValueError, match="exact site/article route once"):
        builder._validate_visible_links(
            "Пост\n\nhttps://thelegendarypoet.ru/\n\nhttps://example.org/source",
            sources=sources,
            article_url=article_url,
        )
