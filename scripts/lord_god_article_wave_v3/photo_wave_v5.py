from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

from . import mutations
from . import photo_wave_v4 as base
from .common import canonical_sha, canonical_text, normalize_url
from .wall import post_reference

PHOTO_DECISION_SET_ID = "lord-god-article-photo-wave-v5-202608"
PHOTO_SCHEMA_VERSION = 5

_original_build_photo_policy = base.build_photo_policy
_original_preflight = base.preflight
_original_submit_wall_post = base.submit_wall_post


class _PinnedUserMutationClient:
    """Use a preflighted current user without another API call after photo save."""

    def __init__(self, client: Any, current_user: Any) -> None:
        self._client = client
        self._current_user = current_user

    def _call(self, method: str, *, params: dict[str, object] | None = None) -> object:
        return self._client._call(method, params=params)

    def get_current_user(self) -> Any:
        return self._current_user


def build_photo_policy(repo: Path) -> dict[str, Any]:
    policy = _original_build_photo_policy(repo)
    base_policy_sha = str(policy["base_policy_sha256"])
    source_contract_sha = str(policy["source_contract_sha256"])
    guid_seed = base_policy_sha.removeprefix("sha256:")[:16]

    policy["schema_version"] = PHOTO_SCHEMA_VERSION
    policy["decision_set_id"] = PHOTO_DECISION_SET_ID
    for operation in policy["operations"]:
        ordinal = int(operation["ordinal"])
        operation["guid"] = f"lgp5-{ordinal:02d}-{guid_seed}"

    identity = {
        "schema_version": PHOTO_SCHEMA_VERSION,
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "base_policy_sha256": base_policy_sha,
        "source_contract_sha256": source_contract_sha,
        "attachment_mode": policy["attachment_mode"],
        "asset_mode": policy["asset_mode"],
        "operations": [
            {
                "operation_id": item["operation_id"],
                "source_operation_id": item["source_operation_id"],
                "guid": item["guid"],
                "article_url": item["url"],
                "image_url": item["image_url"],
                "message_sha256": item["message_sha256"],
                "publish_date": item["publish_date"],
            }
            for item in policy["operations"]
        ],
    }
    execution_sha = canonical_sha(identity)
    policy["policy_sha256"] = execution_sha
    policy["execution_contract_sha256"] = execution_sha
    return policy


def fresh_photo_journal(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": base.PHOTO_JOURNAL_SCHEMA,
        "schema_version": PHOTO_SCHEMA_VERSION,
        "decision_set_id": PHOTO_DECISION_SET_ID,
        "policy_sha256": policy["policy_sha256"],
        "execution_contract_sha256": policy["execution_contract_sha256"],
        "operations": {},
    }


def prepare_photo_token(
    *,
    operation: dict[str, Any],
    jpeg: bytes,
    read_client: Any,
    mutation_client: Any,
    journal: dict[str, Any],
    journal_path: Path,
) -> str:
    kwargs = {
        "operation": operation,
        "jpeg": jpeg,
        "read_client": read_client,
        "journal": journal,
        "journal_path": journal_path,
    }
    get_current_user = getattr(read_client, "get_current_user", None)
    if not callable(get_current_user):
        return mutations.prepare_photo_token(
            **kwargs,
            mutation_client=mutation_client,
        )

    # Resolve token ownership before any photos.saveWallPhoto mutation. The
    # returned user object is then served locally if the save response is
    # user-owned, eliminating a fallible API request after a successful save.
    current_user = get_current_user()
    pinned_mutation_client = _PinnedUserMutationClient(
        mutation_client,
        current_user,
    )
    return mutations.prepare_photo_token(
        **kwargs,
        mutation_client=pinned_mutation_client,
    )


def group_wall_photo_identity(reference: dict[str, Any]) -> str | None:
    """Return the single VK group-owned photo identity attached to a wall post."""

    identities = reference.get("photo_identities")
    if not isinstance(identities, list) or len(identities) != 1:
        return None
    identity = str(identities[0] or "").strip()
    expected_prefix = f"photo{base.OWNER_ID}_"
    return identity if identity.startswith(expected_prefix) else None


def reference_matches_group_rehost(
    operation: dict[str, Any],
    reference: dict[str, Any],
) -> bool:
    """Verify the exact post while allowing VK's user-to-group photo rehost."""

    if reference.get("queue") != "postponed":
        return False
    if reference.get("message") != canonical_text(operation["message"]):
        return False
    if reference.get("date") != operation["publish_date"]:
        return False
    if normalize_url(operation["url"]) not in reference.get("text_urls", []):
        return False
    return group_wall_photo_identity(reference) is not None


def find_exact_post(
    client: Any,
    operation: dict[str, Any],
    *,
    expected_photo_token: str | None,
    expected_post_id: int | None = None,
) -> dict[str, Any] | None:
    """Reconcile an unknown wall.post by exact content and one group photo."""

    del expected_photo_token
    _, postponed = mutations.wall_snapshot(client)
    matches: list[dict[str, Any]] = []
    for raw_post in postponed:
        if expected_post_id is not None and raw_post.get("id") != expected_post_id:
            continue
        reference = post_reference(raw_post, "postponed")
        if reference_matches_group_rehost(operation, reference):
            matches.append(reference)
    return matches[0] if len(matches) == 1 else None


def wait_for_exact_post(
    client: Any,
    operation: dict[str, Any],
    *,
    post_id: int,
    photo_token_value: str,
) -> dict[str, Any]:
    """Wait for the accepted post and verify VK's group-owned photo copy."""

    del photo_token_value
    deadline = time.monotonic() + mutations.POST_WAIT_SECONDS
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        _, postponed = mutations.wall_snapshot(client)
        for raw_post in postponed:
            if raw_post.get("owner_id") != base.OWNER_ID or raw_post.get("id") != post_id:
                continue
            reference = post_reference(raw_post, "postponed")
            last = reference
            if reference.get("message") != canonical_text(operation["message"]):
                raise RuntimeError(f"Accepted post text differs: {operation['operation_id']}")
            if reference.get("date") != operation["publish_date"]:
                raise RuntimeError(f"Accepted post time differs: {operation['operation_id']}")
            if normalize_url(operation["url"]) not in reference.get("text_urls", []):
                raise RuntimeError(
                    f"Accepted post text lacks article URL: {operation['operation_id']}"
                )
            if group_wall_photo_identity(reference) is None:
                raise RuntimeError(
                    "Accepted post does not have exactly one group-owned wall photo: "
                    f"{operation['operation_id']}"
                )
            return reference
        time.sleep(3)
    if last is None:
        raise RuntimeError(
            f"Accepted postponed post is not visible after {mutations.POST_WAIT_SECONDS}s"
        )
    raise RuntimeError(f"Accepted postponed post is not exact after {mutations.POST_WAIT_SECONDS}s")


def preflight(
    policy: dict[str, Any],
    published: list[dict[str, Any]],
    postponed: list[dict[str, Any]],
    journal: dict[str, Any],
    *,
    minimum_future_seconds: int = base.MIN_FUTURE_SECONDS,
) -> dict[str, Any]:
    """Use the posted group photo identity after VK rehosts an uploaded photo."""

    checked_journal = copy.deepcopy(journal)
    operations = checked_journal.get("operations")
    if isinstance(operations, dict):
        for entry in operations.values():
            if not isinstance(entry, dict):
                continue
            posted_identity = str(entry.get("posted_photo_identity") or "").strip()
            if posted_identity:
                entry["photo_token"] = posted_identity
    return _original_preflight(
        policy,
        published,
        postponed,
        checked_journal,
        minimum_future_seconds=minimum_future_seconds,
    )


def submit_wall_post(
    *,
    operation: dict[str, Any],
    photo_token_value: str,
    read_client: Any,
    mutation_client: Any,
    journal: dict[str, Any],
    journal_path: Path,
) -> tuple[int, dict[str, Any]]:
    """Submit once, then pin the group-owned photo identity in the journal."""

    post_id, reference = _original_submit_wall_post(
        operation=operation,
        photo_token_value=photo_token_value,
        read_client=read_client,
        mutation_client=mutation_client,
        journal=journal,
        journal_path=journal_path,
    )
    posted_identity = group_wall_photo_identity(reference)
    if posted_identity is None:
        raise RuntimeError(
            f"Verified post lacks one group-owned wall photo: {operation['operation_id']}"
        )
    mutations.set_journal_stage(
        journal,
        journal_path,
        operation,
        "verified",
        photo_token=photo_token_value,
        posted_photo_identity=posted_identity,
        guid=str(operation.get("guid") or operation["operation_id"]),
        post_id=post_id,
        verification="vk-group-photo-rehost",
        error=None,
    )
    return post_id, reference


# Reuse the already-tested photo executor while replacing every execution identity
# before its first runtime call. The abandoned v4 directory and journal are never read.
mutations.find_exact_post = find_exact_post
mutations.wait_for_exact_post = wait_for_exact_post
base.PHOTO_DECISION_SET_ID = PHOTO_DECISION_SET_ID
base.build_photo_policy = build_photo_policy
base.fresh_photo_journal = fresh_photo_journal
base.prepare_photo_token = prepare_photo_token
base.preflight = preflight
base.submit_wall_post = submit_wall_post

execute_scope = base.execute_scope
load_photo_journal = base.load_photo_journal
run = base.run
main = base.main
guarded_main = base.guarded_main
