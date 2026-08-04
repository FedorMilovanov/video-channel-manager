from __future__ import annotations

import httpx
import pytest

from video_channel_manager.wave_engine.article_prepare import (
    ArticlePreparationError,
    _verify_pinned_source,
)


class _Http:
    def __init__(self, text: str) -> None:
        self.text = text

    def get(self, url: str) -> httpx.Response:
        return httpx.Response(
            200,
            content=self.text.encode("utf-8"),
            request=httpx.Request("GET", url),
        )


def _policy() -> dict[str, object]:
    return {
        "source_repository": "FedorMilovanov/TheLegendaryPoet",
        "source_repository_commit": "85c4303dc683abc6e201ea707a0b4d6f5f19f82c",
    }


def _operation(operation_id: str) -> dict[str, object]:
    return {
        "operation_id": operation_id,
        "source_path": "src/data/essays/mayakovskyGromovoy.ts",
        "source_markers": ["горло собственной песни", "Окнами сатиры РОСТА", "ЛЕФ"],
    }


def test_reviewed_rosta_alias_accepts_the_pinned_source_without_policy_drift() -> None:
    source = "горло собственной песни. Он писал для РОСТА, рисовал плакаты, организовал ЛЕФ."
    evidence = _verify_pinned_source(
        _Http(source),
        policy=_policy(),
        operation=_operation("legendary-poet-article-wave-202608-04-mayakovsky-part-two-work-and-crisis"),
    )
    assert evidence["markers"] == [
        "горло собственной песни",
        "Окнами сатиры РОСТА",
        "ЛЕФ",
    ]


def test_rosta_alias_is_rejected_for_every_other_operation() -> None:
    source = "горло собственной песни. Он писал для РОСТА, рисовал плакаты, организовал ЛЕФ."
    with pytest.raises(ArticlePreparationError, match="missing markers"):
        _verify_pinned_source(
            _Http(source),
            policy=_policy(),
            operation=_operation("another-operation"),
        )
