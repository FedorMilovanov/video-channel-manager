"""Synthetic duration-only routing regressions. No video bytes or provider writes."""

from __future__ import annotations

import json

import pytest

from video_channel_manager.shortorez_routing import ClipInterval, main, plan_routes, validate_render_handoff


def _clip(duration_ms: int = 210_000) -> ClipInterval:
    return ClipInterval(
        project_key="lord-god-strength",
        source_channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
        source_video_id="5nKCs4bkoxE",
        start_ms=60_000,
        end_ms=60_000 + duration_ms,
    )


def _route(duration_ms: int, surface: str, *, speedup: bool = True):
    return next(route for route in plan_routes(_clip(duration_ms), allow_speedup=speedup) if route.surface == surface)


def test_macarthur_source_identity_and_link_are_exact() -> None:
    clip = _clip()
    assert clip.full_video_url == "https://www.youtube.com/watch?v=5nKCs4bkoxE"
    assert clip.duration_ms == 210_000
    with pytest.raises(ValueError, match="source project"):
        ClipInterval("legendary-poet", clip.source_channel_id, clip.source_video_id, 0, 10_000)
    with pytest.raises(ValueError, match="exact eleven"):
        ClipInterval(clip.project_key, clip.source_channel_id, "not-an-id", 0, 10_000)


@pytest.mark.parametrize("start,end", [(5_000, 5_000), (-1, 5_000), (6_000, 5_000), (True, 10_000)])
def test_invalid_cut_ranges_fail_closed(start, end) -> None:
    with pytest.raises(ValueError):
        ClipInterval("lord-god-strength", "UCeSJsC6go2c9pdJCuUI1BYA", "5nKCs4bkoxE", start, end)


def test_platforms_keep_long_normal_speed_and_vk_uses_optional_speedup() -> None:
    routes = plan_routes(_clip(), allow_speedup=True)
    assert [route.surface for route in routes] == ["vk_native_clip", "telegram_native_video", "instagram_reel_api"]
    vk, tg, instagram = routes
    assert vk.speed_percent == 120
    assert vk.projected_duration_ms == 175_000
    assert vk.status == "speed_listening_required"
    assert vk.audio_listening_required
    assert tg.speed_percent == instagram.speed_percent == 100
    assert tg.projected_duration_ms == instagram.projected_duration_ms == 210_000
    assert tg.status == instagram.status == "render_qc_required"
    assert len({r.key for r in routes}) == 3


def test_speedup_not_automatic_or_beyond_120_percent() -> None:
    assert _route(210_000, "vk_native_clip", speedup=False).status == "duration_ineligible"
    assert _route(216_000, "vk_native_clip").speed_percent == 120
    assert _route(216_001, "vk_native_clip").status == "duration_ineligible"
    assert _route(180_000, "vk_native_clip").speed_percent == 100
    assert _route(180_001, "vk_native_clip").speed_percent == 105


def test_instagram_api_15_minutes_is_not_a_telegram_or_vk_limit() -> None:
    assert _route(900_000, "instagram_reel_api").status == "render_qc_required"
    assert _route(900_001, "instagram_reel_api").status == "duration_ineligible"
    assert _route(1_200_000, "telegram_native_video").status == "render_qc_required"
    assert _route(300_000, "vk_native_clip").status == "duration_ineligible"


def test_handoff_requires_actual_media_review_and_exact_full_link() -> None:
    route = _route(210_000, "vk_native_clip")
    base = dict(
        actual_duration_ms=175_100,
        media_sha256="sha256:" + "a" * 64,
        caption="Полная проповедь: https://www.youtube.com/watch?v=5nKCs4bkoxE",
        source_rights_reviewed=True,
        editorial_reviewed=True,
        audible_result_reviewed=True,
    )
    assert validate_render_handoff(route, **base) == ()
    missing = dict(base, caption="Полная проповедь — смотрите в профиле", audible_result_reviewed=False)
    assert set(validate_render_handoff(route, **missing)) == {
        "missing_exact_full_video_link",
        "encoded_audio_not_listened",
    }
    invalid = dict(base, actual_duration_ms=180_001, media_sha256="x", source_rights_reviewed=False)
    assert set(validate_render_handoff(route, **invalid)) == {
        "actual_duration_exceeds_surface",
        "actual_duration_differs_from_reviewed_interval",
        "invalid_media_fingerprint",
        "source_rights_not_reviewed",
    }


def test_ineligible_route_cannot_be_approved_with_fake_handoff() -> None:
    route = _route(250_000, "vk_native_clip")
    issues = validate_render_handoff(
        route,
        actual_duration_ms=160_000,
        media_sha256="sha256:" + "1" * 64,
        caption=f"Полная проповедь: {route.clip.full_video_url}",
        source_rights_reviewed=True,
        editorial_reviewed=True,
        audible_result_reviewed=True,
    )
    assert "duration_ineligible" in issues


def test_caption_surface_limits_do_not_silently_truncate_text() -> None:
    tg = _route(210_000, "telegram_native_video")
    link = tg.clip.full_video_url
    errors = validate_render_handoff(
        tg,
        actual_duration_ms=210_000,
        media_sha256="sha256:" + "f" * 64,
        caption=link + "а" * 1100,
        source_rights_reviewed=True,
        editorial_reviewed=True,
        audible_result_reviewed=True,
    )
    assert "telegram_video_caption_over_limit" in errors


def test_cli_preview_is_json_provider_inert(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(
        [
            "--youtube-id",
            "5nKCs4bkoxE",
            "--start-ms",
            "10000",
            "--end-ms",
            "220000",
            "--allow-speedup",
        ]
    )
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["release_authorized"] is False
    assert payload["provider_write_performed"] is False
    assert payload["full_video_url"] == "https://www.youtube.com/watch?v=5nKCs4bkoxE"
    assert payload["routes"][0]["speed_percent"] == 120
    assert payload["routes"][1]["speed_percent"] == 100


def test_cli_refuses_invalid_source_with_no_preview(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--youtube-id", "5nKCs4bkoxE", "--start-ms", "80000", "--end-ms", "80000"])
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""


def test_three_second_minimum_is_a_planning_gate() -> None:
    assert _route(2_999, "vk_native_clip").status == "duration_ineligible"
    assert _route(2_999, "instagram_reel_api").status == "duration_ineligible"
    assert _route(3_000, "vk_native_clip").status == "render_qc_required"
    assert _route(3_000, "instagram_reel_api").status == "render_qc_required"
    assert _route(2_999, "telegram_native_video").status == "render_qc_required"


def test_rendered_media_must_retain_reviewed_interval_duration() -> None:
    route = _route(210_000, "vk_native_clip")
    base = dict(
        media_sha256="sha256:" + "a" * 64,
        caption=f"Полная проповедь: {route.clip.full_video_url}",
        source_rights_reviewed=True,
        editorial_reviewed=True,
        audible_result_reviewed=True,
    )
    assert validate_render_handoff(route, actual_duration_ms=174_100, **base) == ()
    assert "actual_duration_differs_from_reviewed_interval" in validate_render_handoff(
        route, actual_duration_ms=171_000, **base
    )
    # Meeting the VK maximum by silently deleting a sentence is not valid.
    assert "actual_duration_differs_from_reviewed_interval" in validate_render_handoff(
        route, actual_duration_ms=160_000, **base
    )
