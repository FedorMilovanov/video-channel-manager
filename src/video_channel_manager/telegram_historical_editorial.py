"""Public historical-editorial facade with human reader-facing rendering.

The validation/data model remains byte-for-byte compatible in
``telegram_historical_editorial_core``. Reader-facing rendering intentionally
omits internal evidence-boundary and theology-review memo blocks; those fields
remain mandatory in the sealed data and claim bindings. The public article
contains the historical essay itself and a compact source drawer.
"""

from __future__ import annotations

from video_channel_manager import telegram_historical_editorial_core as _core
from video_channel_manager.telegram_historical_editorial_core import (
    HistoricalClaim as HistoricalClaim,
    HistoricalEditorialQueueV1 as HistoricalEditorialQueueV1,
    HistoricalImagePlan as HistoricalImagePlan,
    HistoricalPost as HistoricalPost,
    HistoricalProseClaimBindings as HistoricalProseClaimBindings,
    HistoricalSchedule as HistoricalSchedule,
    HistoricalSectionClaimBinding as HistoricalSectionClaimBinding,
    HistoricalSource as HistoricalSource,
    HistoricalSourceRegistry as HistoricalSourceRegistry,
    HistoricalVerification as HistoricalVerification,
    REQUIRED_THEOLOGY_COMMITMENTS as REQUIRED_THEOLOGY_COMMITMENTS,
    SourceBindingKind as SourceBindingKind,
    TheologyProfile as TheologyProfile,
    TheologyReview as TheologyReview,
    load_historical_editorial_queue as load_historical_editorial_queue,
    load_historical_source_registry as load_historical_source_registry,
    load_theology_profile as load_theology_profile,
)
from video_channel_manager.telegram_rich_models import RichArticleDocument, RichBlockDetails

# Compatibility for the bundle validator, which intentionally imports this
# private validator from the historical editorial module.
_validate_post_evidence = _core._validate_post_evidence

_INTERNAL_READER_BLOCK_IDS = frozenset({"h-evidence", "p-evidence", "h-theology", "p-theology"})


def build_historical_rich_document(
    queue: HistoricalEditorialQueueV1,
    post: HistoricalPost,
    registry: HistoricalSourceRegistry,
) -> RichArticleDocument:
    """Build a human-facing historical essay without internal audit prose."""

    article = _core.build_historical_rich_document(queue, post, registry)
    reader_blocks: list[object] = []
    for block in article.blocks:
        if getattr(block, "block_id", None) in _INTERNAL_READER_BLOCK_IDS:
            continue
        if isinstance(block, RichBlockDetails) and block.block_id == "d-sources":
            block = block.model_copy(update={"summary": "Источники"})
        reader_blocks.append(block)

    return article.model_copy(
        update={
            "blocks": tuple(reader_blocks),
            "revision": "historical-human-v2",
        }
    )


def __getattr__(name: str) -> object:
    """Forward legacy/public attributes to the frozen core module."""

    return getattr(_core, name)


__all__ = [
    *_core.__all__,
    "build_historical_rich_document",
]
