"""Adversarial, provider-inert tests for exact LordGod owned Reel HTTPS handoff."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_lord_god_instagram_https_handoff.py"
_SPEC = importlib.util.spec_from_file_location("lord_god_https_handoff", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
handoff = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(handoff)


@pytest.fixture()
def case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    video = tmp_path / "owned.mp4"
    video.write_bytes(b"owned-original-reel-test-bytes")
    caption = tmp_path / "caption.txt"
    caption.write_text("Библейское сердце — исследование.\n", encoding="utf-8")
    media_hash = hashlib.sha256(video.read_bytes()).hexdigest()
    caption_hash = hashlib.sha256(caption.read_bytes()).hexdigest()
    evidence = {
        "schema": "lord-god-owned-site-reel-pilot-v1",
        "project_key": handoff.PROJECT,
        "instagram_account_id": handoff.ACCOUNT,
        "source_url": handoff.SOURCE_URL,
        "source_repo": handoff.SOURCE_REPO,
        "source_commit": "a" * 40,
        "source_article_author": "fedor-milovanov",
        "original_media_only": True,
        "borrowed_footage_or_audio": False,
        "visual_qa": "all_7_storyboard_screens_previewed_no_clipping",
        "auditory_qa": "human_listened_pass",
        "publication_authorized": True,
        "public_hosting_authorized": True,
        "approved_release_slot": "2026-11-22T19:00:00+03:00",
        "video_path": str(video),
        "video_sha256": "sha256:" + media_hash,
        "caption_path": str(caption),
        "caption_sha256": "sha256:" + caption_hash,
        "ffprobe": {"format": {"size": str(video.stat().st_size)}},
    }
    evidence_path = tmp_path / "pilot.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    db_path = tmp_path / "ledger.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE instagram_publications (account_id TEXT, publication_key TEXT)")
    verify_calls: list[str] = []
    monkeypatch.setattr(
        handoff,
        "verify_local_reel",
        lambda *args, **kwargs: verify_calls.append("local"),
    )
    monkeypatch.setattr(
        handoff,
        "verify_instagram_public_object",
        lambda *args, **kwargs: verify_calls.append("hosted"),
    )
    return {
        "video": video,
        "caption": caption,
        "evidence": evidence,
        "evidence_path": evidence_path,
        "db_path": db_path,
        "media_hash": media_hash,
        "verify_calls": verify_calls,
    }


def prepare(case: dict[str, Any], **changes: Any) -> Any:
    kwargs: dict[str, Any] = {
        "evidence_path": case["evidence_path"],
        "db_path": case["db_path"],
        "day": "2026-11-22",
        "video_url": f"https://cdn.example.net/reels/{case['media_hash']}.mp4",
        "allowed_host": "cdn.example.net",
        "public_hosting_authorized": True,
        "media_client": cast(httpx.Client, None),
    }
    kwargs.update(changes)
    return handoff.prepare_verified_handoff(**kwargs)


def edit_evidence(case: dict[str, Any], **changes: Any) -> None:
    case["evidence"].update(changes)
    case["evidence_path"].write_text(json.dumps(case["evidence"]), encoding="utf-8")


def test_approved_owned_media_yields_new_distinct_key_without_graph(
    case: dict[str, Any],
) -> None:
    manifest = prepare(case)
    assert manifest.publication_key == ("lord-god-strength.2026-11-22.article-heart.public-https-v1")
    assert manifest.account_id == handoff.ACCOUNT
    assert manifest.media_sha256 == "sha256:" + case["media_hash"]
    assert case["verify_calls"] == ["local", "hosted"]


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("auditory_qa", "not_human_listened"),
        ("publication_authorized", False),
        ("public_hosting_authorized", False),
        ("instagram_account_id", "17841407843933779"),
        ("source_repo", "FedorMilovanov/other"),
        ("original_media_only", False),
        ("borrowed_footage_or_audio", True),
        ("approved_release_slot", "2026-11-23T19:00:00+03:00"),
        ("source_commit", "unverified"),
    ],
)
def test_any_missing_identity_or_approval_fails_closed(case: dict[str, Any], field: str, invalid: Any) -> None:
    edit_evidence(case, **{field: invalid})
    with pytest.raises(handoff.HandoffHold):
        prepare(case)
    assert case["verify_calls"] == []


def test_public_hosting_authorization_must_be_explicit(case: dict[str, Any]) -> None:
    with pytest.raises(handoff.HandoffHold, match="hosting"):
        prepare(case, public_hosting_authorized=False)


def test_local_video_digest_and_caption_are_immutable(case: dict[str, Any]) -> None:
    case["video"].write_bytes(b"changed")
    with pytest.raises(handoff.HandoffHold, match="reviewed bytes"):
        prepare(case)
    case["video"].write_bytes(b"owned-original-reel-test-bytes")
    case["caption"].write_text("changed caption", encoding="utf-8")
    with pytest.raises(handoff.HandoffHold, match="reviewed bytes"):
        prepare(case)


def test_any_previous_source_attempt_blocks_rekey(case: dict[str, Any]) -> None:
    with sqlite3.connect(case["db_path"]) as db:
        db.execute(
            "INSERT INTO instagram_publications VALUES (?, ?)",
            (handoff.ACCOUNT, "lord-god-strength.2026-11-22.article-heart.local-v1"),
        )
    with pytest.raises(handoff.HandoffHold, match="previous Instagram attempt"):
        prepare(case)
    assert case["verify_calls"] == ["local"]


def test_previous_other_account_does_not_block(case: dict[str, Any]) -> None:
    with sqlite3.connect(case["db_path"]) as db:
        db.execute(
            "INSERT INTO instagram_publications VALUES (?, ?)",
            ("17841407843933779", "milovi-cake.2026-11-22.article-heart.local-v1"),
        )
    assert prepare(case).account_id == handoff.ACCOUNT


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.example.net/reels/invalid.mp4",
        "https://cdn.example.net.evil.test/reel/invalid.mp4",
        "https://cdn.example.net:444/reels/invalid.mp4",
        "https://user:pass@cdn.example.net/reels/invalid.mp4",
        "https://cdn.example.net/reels/invalid.mp4?download=1",
        "https://cdn.example.net/reels/invalid.mp4#fragment",
    ],
)
def test_untrusted_public_url_is_rejected(case: dict[str, Any], url: str) -> None:
    url = url.replace("invalid", case["media_hash"])
    with pytest.raises(handoff.HandoffHold, match="HTTPS"):
        prepare(case, video_url=url)
    assert case["verify_calls"] == ["local"]


@pytest.mark.parametrize("day", ["2026-11-21", "2027-01-01", "not-a-day"])
def test_future_slot_is_bounded(case: dict[str, Any], day: str) -> None:
    with pytest.raises(handoff.HandoffHold):
        prepare(case, day=day)


def test_ledger_unavailable_fails_closed(case: dict[str, Any]) -> None:
    # SQLite may retain a handle on Windows; test an absent path instead of unlink.
    with pytest.raises(handoff.HandoffHold, match="SQLite"):
        prepare(case, db_path=case["db_path"].parent / "missing.sqlite")


def test_hosted_object_verification_failure_propagates(case: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_hosted(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("remote SHA mismatch")

    monkeypatch.setattr(handoff, "verify_instagram_public_object", reject_hosted)
    with pytest.raises(RuntimeError, match="SHA mismatch"):
        prepare(case)
