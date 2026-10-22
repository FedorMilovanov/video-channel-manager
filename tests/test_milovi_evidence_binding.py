from __future__ import annotations

import json
import re
from pathlib import Path

from video_channel_manager import milovi_telegram_feed as feed
from video_channel_manager.milovi_telegram_video_artifacts import _evidence_identity

ROOT = Path(__file__).resolve().parents[1]
RESERVOIR = ROOT / "content" / "telegram" / "milovi-cake" / "accepted-video-reservoir-2026-08.json"
PROTECTED = ROOT / "docs" / "operations" / "protected-evidence-refs.json"
HYGIENE_LEDGER = ROOT / "docs" / "operations" / "branch-hygiene-2026-10-21-deletion-ledger.md"
ARTIFACT_WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-video-artifacts.yml"


def _reservoir() -> dict[str, object]:
    return json.loads(RESERVOIR.read_text(encoding="utf-8"))


def _protected() -> dict[str, object]:
    return json.loads(PROTECTED.read_text(encoding="utf-8"))


def test_accepted_evidence_file_exists_and_its_identity_is_the_published_digest() -> None:
    """The reservoir's evidence pointer must resolve inside the repository.

    Until this test existed, `evidence_path` named a file that was only ever on an
    artefact branch: the digest in the reservoir and in the runtime binding could not be
    re-verified offline, and the file itself was unreachable from `main`.
    """

    reservoir = _reservoir()
    evidence_path = ROOT / str(reservoir["evidence_path"])
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    identity = _evidence_identity(evidence)

    assert evidence["evidence_sha256"] == identity
    assert reservoir["evidence_sha256"] == identity == feed.VIDEO_EVIDENCE_SHA256
    assert evidence["accepted_output_count"] == 16
    assert evidence["declared_video_count"] == 16
    assert evidence["provider_access_performed"] is False
    assert evidence["provider_write_performed"] is False


def test_reservoir_artifacts_are_the_exact_outputs_of_the_accepted_evidence() -> None:
    """Binding by media_id alone is not enough: every digest must agree."""

    reservoir = _reservoir()
    evidence = json.loads((ROOT / str(reservoir["evidence_path"])).read_text(encoding="utf-8"))
    outputs = {output["media_id"]: output for output in evidence["outputs"]}

    assert len(outputs) == len(evidence["outputs"]) == 16

    for artifact in reservoir["artifacts"]:  # type: ignore[union-attr]
        output = outputs[artifact["media_id"]]
        assert output["output_path"] == artifact["artifact_path"]
        assert output["output_sha256"] == artifact["sha256"]
        assert output["output_byte_size"] == artifact["byte_size"]
        assert artifact["sha256"].startswith("sha256:")
        assert re.fullmatch(r"[0-9a-f]{40}", str(artifact["git_blob_sha1"]))


def test_reservoir_points_at_the_ref_and_commit_the_runtime_binds() -> None:
    reservoir = _reservoir()

    assert reservoir["artifact_repository"] == feed.VIDEO_ARTIFACT_REPOSITORY
    assert reservoir["artifact_ref"] == feed.VIDEO_ARTIFACT_REF
    assert reservoir["evidence_sha256"] == feed.VIDEO_EVIDENCE_SHA256

    # A locator without an exact commit cannot be restored once the ref is gone.
    assert re.fullmatch(r"[0-9a-f]{40}", str(reservoir["artifact_commit"]))
    assert str(reservoir["artifact_commit"]) in str(reservoir["artifact_restore"])
    assert str(reservoir["artifact_ref"]) in str(reservoir["artifact_restore"]) or "refs/heads/" in str(
        reservoir["artifact_restore"]
    )


def test_every_ref_the_repository_references_is_protected_from_hygiene() -> None:
    """Hygiene deletes refs; bindings name them. The two must not collide silently."""

    refs = {entry["ref"]: entry for entry in _protected()["refs"]}  # type: ignore[union-attr]

    assert feed.VIDEO_ARTIFACT_REF in refs, feed.VIDEO_ARTIFACT_REF
    for state_ref in ("state/lordchrist-telegram", "state/milovi-cake-telegram", "state/svodka-telegram"):
        assert state_ref in refs

    bound = refs[feed.VIDEO_ARTIFACT_REF]
    assert bound["role"] == "content_addressed_evidence"
    assert bound["tip_is_stable"] is True
    assert bound["tip_commit"] == _reservoir()["artifact_commit"]


def test_deletion_ledger_never_lists_a_protected_ref_as_deleted() -> None:
    """Regression guard for the 2026-10-21 mistake.

    The accepted Milovi evidence ref was deleted as a byte-identical duplicate and had to
    be restored by SHA. Duplication is not a reason to delete a ref that a binding names,
    so a deletion ledger row for a protected ref is now a test failure.
    """

    ledger = HYGIENE_LEDGER.read_text(encoding="utf-8")
    deleted = set(re.findall(r"^\|\s*`([^`]+)`\s*\|", ledger, re.MULTILINE))

    protected = {entry["ref"] for entry in _protected()["refs"]}  # type: ignore[union-attr]

    assert deleted, "the ledger should still record what was deleted"
    assert deleted & protected == set()

    # The restore instruction must be present for every ref with a stable tip.
    for entry in _protected()["refs"]:  # type: ignore[union-attr]
        if entry["tip_is_stable"]:
            assert entry["restore"], entry["ref"]
            assert entry["tip_commit"] in entry["restore"], entry["ref"]


def test_artifact_workflow_can_only_reproduce_the_accepted_evidence_ref() -> None:
    """A regenerated digest must fail the build, not spawn an untracked evidence ref.

    The workflow derives its branch name from the evidence digest. Before this gate, a
    regeneration would create `agent/milovi-video-accepted-<new12>` — a ref that no binding
    names, that is absent from the protected inventory, and that the next hygiene pass would
    treat as a disposable work branch. That is the same failure mode as the deletion this
    file already guards against, one step earlier in the pipeline.
    """

    workflow = ARTIFACT_WORKFLOW.read_text(encoding="utf-8")

    # The name is still derived from the digest...
    assert 'branch="agent/milovi-video-accepted-${evidence_sha:0:12}"' in workflow
    # ...but it must equal the accepted ref before anything is pushed.
    assert "accepted_branch=" in workflow
    assert 'if [[ "$branch" != "$accepted_branch" ]]' in workflow
    assert "protected-evidence-refs.json entry" in workflow
    assert workflow.index("accepted_branch=") < workflow.index("git push origin")


def test_artifact_workflow_rerun_is_verified_not_refused() -> None:
    """An identical rebuild is not an error; drift is.

    The accepted artifacts are immutable, so the workflow could not simply overwrite them.
    It used to exit 3 whenever the ref existed, which made every later run on `main` fail
    for a state that was in fact correct. A re-run now proves the rebuild reproduced the
    accepted blobs byte-for-byte and succeeds, and only genuine drift stays fatal.
    """

    workflow = ARTIFACT_WORKFLOW.read_text(encoding="utf-8")

    existing = workflow.index('if git ls-remote --exit-code origin "refs/heads/$branch"')
    push = workflow.index("git push origin")
    existing_block = workflow[existing:push]

    assert "git hash-object" in existing_block
    assert "git rev-parse" in existing_block
    assert "artifact drift on" in existing_block
    assert "exit 3" in existing_block  # drift stays fatal
    assert "exit 0" in existing_block  # identical rebuild succeeds
    # The no-op path must still surface the ref and digest for later steps.
    assert 'echo "branch=$branch" >> "$GITHUB_OUTPUT"' in existing_block
    assert 'echo "evidence_sha256=sha256:$evidence_sha" >> "$GITHUB_OUTPUT"' in existing_block


def test_derived_artifact_ref_equals_the_accepted_binding_for_current_evidence() -> None:
    """The 12-character derivation must actually land on the accepted ref today."""

    evidence = json.loads((ROOT / str(_reservoir()["evidence_path"])).read_text(encoding="utf-8"))
    digest = str(evidence["evidence_sha256"]).split(":", 1)[1]

    derived = f"agent/milovi-video-accepted-{digest[:12]}"

    assert derived == _reservoir()["artifact_ref"] == feed.VIDEO_ARTIFACT_REF
