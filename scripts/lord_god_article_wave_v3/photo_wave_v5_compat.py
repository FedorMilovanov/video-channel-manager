from __future__ import annotations

from pathlib import Path
from typing import Any

from . import mutations
from . import photo_wave_v5 as v5


def submit_wall_post(
    *,
    operation: dict[str, Any],
    photo_token_value: str,
    read_client: Any,
    mutation_client: Any,
    journal: dict[str, Any],
    journal_path: Path,
) -> tuple[int, dict[str, Any]]:
    """Preserve legacy contracts and pin VK's group photo only for v5."""

    post_id, reference = v5._original_submit_wall_post(
        operation=operation,
        photo_token_value=photo_token_value,
        read_client=read_client,
        mutation_client=mutation_client,
        journal=journal,
        journal_path=journal_path,
    )
    operation_id = str(operation["operation_id"])
    if not operation_id.startswith(f"{v5.PHOTO_DECISION_SET_ID}-"):
        return post_id, reference

    posted_identity = v5.group_wall_photo_identity(reference)
    if posted_identity is None:
        raise RuntimeError(
            f"Verified post lacks one group-owned wall photo: {operation_id}"
        )
    mutations.set_journal_stage(
        journal,
        journal_path,
        operation,
        "verified",
        photo_token=photo_token_value,
        posted_photo_identity=posted_identity,
        guid=str(operation.get("guid") or operation_id),
        post_id=post_id,
        verification="vk-group-photo-rehost",
        error=None,
    )
    return post_id, reference


v5.base.submit_wall_post = submit_wall_post
