from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.live_description_audit import build_live_description_cleanup_plan


def _video(remote_id: str, title: str, description: str) -> VideoRecord:
    return VideoRecord(
        ref=RemoteRef(platform=PlatformName.VK, channel_id="235216998", remote_id=remote_id),
        title=title,
        description=description,
        duration_seconds=240,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _audit(videos: list[VideoRecord]) -> AuditPackage:
    return AuditPackage(
        channel=ChannelRecord(
            ref=RemoteRef(platform=PlatformName.VK, channel_id="235216998", remote_id="235216998"),
            title="The Legendary Poet",
            kind=ChannelKind.COMMUNITY,
        ),
        videos=videos,
    )


def test_full_live_plan_cleans_current_vk_text_without_rebuilding_wording() -> None:
    live = _audit(
        [
            _video(
                "-235216998_1",
                "Фет",
                "Стихотворение написано в *1850 году*.\n\n_Осенью того же года_ история изменилась.",
            )
        ]
    )

    plan = build_live_description_cleanup_plan(live, community_id=235216998)

    assert plan["videos_checked"] == 1
    assert plan["operations_count"] == 1
    operation = plan["operations"][0]
    assert operation["before_description"].startswith("Стихотворение написано в *1850 году*")
    assert operation["after_description"].startswith("Стихотворение написано в 1850 году")
    assert "Осенью того же года история изменилась." in operation["after_description"]
    assert operation["removed_emphasis_pairs"] == 2
    assert operation["footer_added"] is True


def test_full_live_plan_checks_old_safe_review_and_foreign_videos() -> None:
    footer = (
        "Обычное описание без разметки.\n\n"
        "🎧 The Legendary Poet — русская поэзия, музыка и литературные материалы.\n"
        "🌐 https://thelegendarypoet.ru/"
    )
    live = _audit(
        [
            _video("-235216998_1", "Уже безопасно", footer),
            _video("-235216998_2", "Требует проверки", "Текст с <b>HTML</b>."),
            _video("-999_3", "Чужой владелец", "*Не трогать автоматически*"),
            _video("-235216998_4", "К ***", "Название К *** сохраняется."),
        ]
    )

    plan = build_live_description_cleanup_plan(live, community_id=235216998)

    assert plan["videos_checked"] == 4
    assert plan["already_safe_count"] == 1
    assert plan["review_only_count"] == 2
    assert plan["operations_count"] == 1
    assert plan["operations"][0]["title"] == "К ***"
    assert "К ***" in plan["operations"][0]["after_description"]
    reasons = {item["reason"] for item in plan["review_only"]}
    assert any("warning or error" in reason for reason in reasons)
    assert any("differs from community owner" in reason for reason in reasons)
