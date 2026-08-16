from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from video_channel_manager.milovi_telegram_follow_on_readiness import (
    BENTO_INSCRIPTION,
    ORDER_QUICK_CALC,
    ORDER_TIMING,
    SCHOOL_PUBLICATION_IDS,
    build_readiness_result,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import (
    GenericReleaseItem,
    GenericReleaseQueue,
    save_release,
)
from video_channel_manager.telegram_multichannel_state import initialize_ledger, save_ledger
from video_channel_manager.telegram_multichannel_transport import render_message_payload

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
CANDIDATES = ROOT / "content/telegram/milovi-cake/follow-on-wave-candidates-2026-08.json"
TRANSPORT = ROOT / "content/telegram/milovi-cake/follow-on-photo-source-manifest-2026-08.json"
POLICY = ROOT / "content/telegram/milovi-cake/follow-on-release-policy-2026-08.json"
SCHOOL_POOL = ROOT / "content/telegram/milovi-cake/school-interest-reading-candidates-2026-08.json"
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-follow-on-readiness.yml"


def _source_snapshots(tmp_path: Path) -> tuple[Path, Path, Path]:
    order = tmp_path / "order.html"
    bento = tmp_path / "bento.html"
    school = tmp_path / "articles.ts"
    order.write_text(f"<html>{ORDER_QUICK_CALC}\n{ORDER_TIMING}</html>", encoding="utf-8")
    bento.write_text(f"<html>{BENTO_INSCRIPTION}</html>", encoding="utf-8")

    pool = json.loads(SCHOOL_POOL.read_text(encoding="utf-8"))
    by_slug = {item["source_slug"]: item for item in pool["candidates"]}
    lines = []
    for slug in SCHOOL_PUBLICATION_IDS.values():
        lines.append(f"{{ id: '{slug}', title: '{by_slug[slug]['source_title']}' }}")
    school.write_text("\n".join(lines), encoding="utf-8")
    return order, bento, school


def _authorized_bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    profile = load_channel_profile(PROFILE)
    start = datetime(2026, 8, 12, 7, 30, tzinfo=UTC)
    items = []
    for index in range(1, 11):
        publication_id = f"milovi-bootstrap-{index:03d}"
        payload = render_message_payload(profile, publication_id=publication_id, html_text=f"bootstrap {index}")
        items.append(
            GenericReleaseItem(
                sequence=index,
                publication_id=publication_id,
                scheduled_at=start + timedelta(days=index - 1),
                source_sha256="sha256:" + f"{index:064x}",
                payload=payload,
            )
        )
    candidate = GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id="milovi-bootstrap-test-release",
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        timezone=profile.timezone,
        daily_verified_limit=profile.daily_verified_limit,
        target_binding_sha256="sha256:" + "1" * 64,
        chat_id=-1002215328390,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        release_authorized=False,
        items=tuple(items),
    )
    authorized = candidate.model_copy(
        update={
            "release_authorized": True,
            "reviewed_candidate_sha256": candidate.candidate_digest(),
            "reviewed_by": "readiness-test",
            "reviewed_at": datetime(2026, 8, 12, 7, 0, tzinfo=UTC),
        }
    )
    release_path = tmp_path / "bootstrap-release.json"
    save_release(release_path, authorized)

    ledger = initialize_ledger(authorized)
    for index in range(1, 10):
        entry = ledger.entries[f"milovi-bootstrap-{index:03d}"]
        entry.state = "skipped"
        entry.provider_effect = "impossible"
    final = ledger.entries["milovi-bootstrap-010"]
    final.state = "published"
    final.provider_effect = "verified"
    final.intent_id = "intent-readiness-0001"
    final.dispatch_mode = "manual"
    final.workflow_run_id = "12345"
    final.workflow_run_attempt = "1"
    final.github_sha = "a" * 40
    final.github_workflow_sha = "b" * 40
    final.attempted_at_utc = datetime(2026, 8, 16, 17, 59, tzinfo=UTC)
    final.published_at_utc = datetime(2026, 8, 16, 18, 0, tzinfo=UTC)
    final.message_id = 99
    final.message_url = "https://t.me/MiloviCake/99"
    final.actual_chat_id = -1002215328390
    final.actual_chat_username = "MiloviCake"
    final.bot_id = 8716602202
    final.bot_username = "preaching_mp3_bot"
    ledger_path = tmp_path / "publication-ledger.json"
    save_ledger(ledger_path, ledger)
    return release_path, ledger_path


def _run(
    tmp_path: Path,
    *,
    release_path: Path,
    ledger_path: Path,
    order: Path,
    bento: Path,
    school: Path,
):
    return build_readiness_result(
        profile_path=PROFILE,
        candidates_path=CANDIDATES,
        transport_manifest_path=TRANSPORT,
        policy_path=POLICY,
        bootstrap_release_path=release_path,
        bootstrap_ledger_path=ledger_path,
        order_snapshot_path=order,
        bento_snapshot_path=bento,
        school_articles_snapshot_path=school,
        cake_source_commit="c" * 40,
        school_source_commit="d" * 40,
        checked_at=datetime(2026, 8, 16, 18, 30, tzinfo=UTC),
    )


def test_missing_bootstrap_state_is_blocked_and_never_emits_receipt(tmp_path: Path) -> None:
    order, bento, school = _source_snapshots(tmp_path)
    report, receipt = _run(
        tmp_path,
        release_path=tmp_path / "missing-release.json",
        ledger_path=tmp_path / "missing-ledger.json",
        order=order,
        bento=bento,
        school=school,
    )
    assert report["ready"] is False
    assert "bootstrap_authorized_release_missing" in report["blockers"]
    assert "bootstrap_state_ledger_missing" in report["blockers"]
    assert report["provider_write_performed"] is False
    assert report["telegram_provider_accessed"] is False
    assert report["state_branch_write_performed"] is False
    assert receipt is None


def test_verified_terminal_bootstrap_and_current_sources_emit_short_lived_receipt(tmp_path: Path) -> None:
    order, bento, school = _source_snapshots(tmp_path)
    release_path, ledger_path = _authorized_bootstrap(tmp_path)
    report, receipt = _run(
        tmp_path,
        release_path=release_path,
        ledger_path=ledger_path,
        order=order,
        bento=bento,
        school=school,
    )
    assert report["ready"] is True
    assert report["blockers"] == []
    assert report["bootstrap_final_publication_id"] == "milovi-bootstrap-010"
    assert report["bootstrap_final_verified_at"] == "2026-08-16T18:00:00+00:00"
    assert receipt is not None
    assert receipt["status"] == "verified_current_sources"
    assert receipt["bootstrap_terminal_status"] == "verified"
    assert receipt["source_revalidated_at"] == "2026-08-16T18:30:00+00:00"
    assert receipt["cake_source_commit"] == "c" * 40
    assert receipt["school_source_commit"] == "d" * 40
    assert receipt["provider_write_performed"] is False
    assert receipt["telegram_provider_accessed"] is False
    assert receipt["execution_authorized"] is False
    assert receipt["provider_mutation_allowed"] is False


def test_current_order_source_drift_blocks_receipt(tmp_path: Path) -> None:
    order, bento, school = _source_snapshots(tmp_path)
    order.write_text(ORDER_QUICK_CALC, encoding="utf-8")
    release_path, ledger_path = _authorized_bootstrap(tmp_path)
    report, receipt = _run(
        tmp_path,
        release_path=release_path,
        ledger_path=ledger_path,
        order=order,
        bento=bento,
        school=school,
    )
    assert report["ready"] is False
    assert "cake_order_timing_source_drift" in report["blockers"]
    assert receipt is None


def test_current_school_title_drift_blocks_receipt(tmp_path: Path) -> None:
    order, bento, school = _source_snapshots(tmp_path)
    school.write_text(
        school.read_text(encoding="utf-8").replace("Ladurée 1862", "Ladurée changed", 1), encoding="utf-8"
    )
    release_path, ledger_path = _authorized_bootstrap(tmp_path)
    report, receipt = _run(
        tmp_path,
        release_path=release_path,
        ledger_path=ledger_path,
        order=order,
        bento=bento,
        school=school,
    )
    assert report["ready"] is False
    assert any(str(blocker).startswith("school_article_title_drift:laduree-1862") for blocker in report["blockers"])
    assert receipt is None


def test_final_bootstrap_target_identity_drift_blocks_receipt(tmp_path: Path) -> None:
    order, bento, school = _source_snapshots(tmp_path)
    release_path, ledger_path = _authorized_bootstrap(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["entries"]["milovi-bootstrap-010"]["bot_id"] = 123
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report, receipt = _run(
        tmp_path,
        release_path=release_path,
        ledger_path=ledger_path,
        order=order,
        bento=bento,
        school=school,
    )
    assert report["ready"] is False
    assert "bootstrap_final_target_identity_drift" in report["blockers"]
    assert receipt is None


def test_workflow_is_read_only_and_contains_no_telegram_provider_mutation_path() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in text
    assert "persist-credentials: false" in text
    assert "TELEGRAM_BOT_TOKEN" not in text
    assert "api.telegram.org" not in text
    assert "sendPhoto" not in text
    assert "sendMessage" not in text
    assert "git push" not in text
    assert "contents: write" not in text
    assert "state_branch_write_performed" in text
