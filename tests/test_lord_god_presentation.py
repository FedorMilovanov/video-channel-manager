"""Project-scoped YouTube styling and retired-payment release policy."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import typer

from video_channel_manager.platforms.youtube.copy_plan import (
    finalize_copy_plan,
    sha256_text,
)
from video_channel_manager.platforms.youtube.lord_god_presentation import (
    LORD_GOD_OWNER_CHANNEL,
    presentation_issues,
    require_lord_god_youtube_presentation,
)

_FIRST = "Алексей Прокопенко — «Семья, угодная Богу». Часть 1: библейские цели брака."
_BODY = (
    "Первое занятие посвящено изучению библейских оснований семьи. "
    "Проповедник последовательно разбирает отношения мужа и жены, "
    "их общение и помощь друг другу, значение совместной молитвы, "
    "церковной жизни и ответственности каждого супруга. "
    "Вопросы слушателей рассматриваются в контексте Священного Писания."
)
_DESCRIPTION = (
    _FIRST
    + "\nНа занятии также обсуждается ответственность супругов перед Богом и церковью."
    + "\n\n"
    + _BODY.replace("их общение и помощь друг другу,", "_их общение и помощь друг другу,_")
    + "\n\n*Все шесть занятий:* https://www.youtube.com/playlist?list=PLu2Bhoh2caiUqCagDLyFH4v40eBSKJCdL"
    + "\n\n*Богословская библиотека:* https://gospod-bog.ru/"
    + "\n*Telegram проекта:* https://t.me/lordchrist"
)


def _plan(after: str = _DESCRIPTION) -> dict:
    plan = {
        "ruleset": "test-lordgod-youtube-style",
        "source_audit_sha256": "sha256:test-audit",
        "target_channel_id": LORD_GOD_OWNER_CHANNEL,
        "project_key": "lord-god-strength",
        "link_profile": "lord-god-strength",
        "videos_checked": 1,
        "operations_count": 1,
        "blocked_operations_count": 0,
        "unresolved_error_videos": 0,
        "operations": [
            {
                "ruleset": "test-lordgod-youtube-style",
                "operation": "replace_video_description",
                "platform": "youtube",
                "video_id": "al2wqoxaAjk",
                "channel_id": LORD_GOD_OWNER_CHANNEL,
                "title": "Семья, угодная Богу — часть 1",
                "expected_revision": "sha256:old",
                "before_description": "Прежнее описание",
                "after_description": after,
                "before_sha256": sha256_text("Прежнее описание"),
                "after_sha256": sha256_text(after),
                "fixes": [{"code": "style", "count": 1}],
            }
        ],
        "unresolved": [],
    }
    finalize_copy_plan(plan, checked_video_ids=["al2wqoxaAjk"])
    return plan


def test_formatted_project_description_is_accepted() -> None:
    assert len(_DESCRIPTION) >= 350
    assert presentation_issues(_DESCRIPTION) == []
    require_lord_god_youtube_presentation(_plan())


@pytest.mark.parametrize(
    "modification,expected",
    [
        (
            lambda x: (
                x.replace("*Все шесть занятий:*", "Все шесть занятий:")
                .replace("*Богословская библиотека:*", "Богословская библиотека:")
                .replace("*Telegram проекта:*", "Telegram проекта:")
            ),
            "missing_youtube_bold",
        ),
        (
            lambda x: x.replace("_их общение и помощь друг другу,_", "их общение и помощь друг другу,"),
            "missing_youtube_italic",
        ),
        (lambda x: x.replace("*Все шесть занятий:*", "**Все шесть занятий:**"), "markdown_double_asterisks"),
        (lambda x: x.replace("*Все шесть занятий:*", "*Все шесть занятий*."), "youtube_punctuation_outside_emphasis"),
        (lambda x: x.replace(_FIRST, "*" + _FIRST + "*"), "youtube_share_preview_emphasis"),
        (lambda x: x + "\n[Наш сайт](https://gospod-bog.ru/)", "youtube_hidden_markdown_link"),
        (
            lambda x: x + "\nhttp://www.youtube.com/channel/UCeSJsC6go2c9pdJCuUI1BYA/playlists?shelf_id=3",
            "obsolete_shelf_navigation",
        ),
        (lambda x: x + "\nTelegram для связи: https://t.me/fedormilovanov", "retired_personal_contact"),
        (
            lambda x: x + "\nПомочь с переводами с английского — пишите в личные сообщения.",
            "retired_translator_recruitment",
        ),
        (lambda x: x + "\nЯндекс кошелек: 12345678901234", "retired_fundraising_or_payment"),
        (lambda x: x + "\nСбербанк: 1234 5678 9012 3456", "retired_fundraising_or_payment"),
        (lambda x: x + "\nhttps://new.donatepay.ru/@old", "retired_fundraising_or_payment"),
        (
            lambda x: x + "\nЕсли кто хочет поддержать служение распространения и переводов, пишите.",
            "retired_fundraising_or_payment",
        ),
        (lambda x: x + "\nhttps://thelegendarypoet.ru/", "cross_project_identity"),
    ],
)
def test_bad_markers_and_old_administrative_info_fail_closed(modification, expected: str) -> None:
    content = modification(_DESCRIPTION)
    issues = presentation_issues(content)
    assert expected in issues, issues
    with pytest.raises(ValueError, match=expected):
        require_lord_god_youtube_presentation(_plan(content))


def test_short_description_may_be_plain_but_not_a_donation_request() -> None:
    short = "Проповедь о смирении и верности Христу. https://gospod-bog.ru/"
    assert presentation_issues(short) == []
    assert "retired_fundraising_or_payment" in presentation_issues(short + "\nСбербанк: 1234 5678 9012 3456")


def test_mismatched_project_or_corrupted_plan_fails_closed() -> None:
    wrong = _plan()
    wrong["project_key"] = "legendary-poet"
    finalize_copy_plan(wrong, checked_video_ids=["al2wqoxaAjk"])
    with pytest.raises(ValueError, match="project identity"):
        require_lord_god_youtube_presentation(wrong)
    altered = _plan()
    altered["operations"][0]["after_description"] += " скрытая правка"
    with pytest.raises(ValueError, match="after_sha256"):
        require_lord_god_youtube_presentation(altered)


def test_foreign_channel_is_not_subject_to_lord_god_specific_content_policy() -> None:
    plan = _plan()
    plan["target_channel_id"] = "UC-other"
    # The generic copy-plan writer has its own identity rules; this narrow
    # formatter must not assert Lord God content policy for unrelated channels.
    require_lord_god_youtube_presentation(plan)


def test_lord_god_does_not_allow_batch_copy_fixes_even_if_formatted() -> None:
    plan = _plan()
    second = deepcopy(plan["operations"][0])
    second["video_id"] = "anotherID"
    plan["operations"].append(second)
    plan["operations_count"] = 2
    plan["videos_checked"] = 2
    finalize_copy_plan(plan, checked_video_ids=["al2wqoxaAjk", "anotherID"])
    with pytest.raises(ValueError, match="multi-video"):
        require_lord_god_youtube_presentation(plan)


def test_cli_blocks_invalid_lord_god_copy_before_oauth_or_provider_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    from video_channel_manager.cli import youtube as cli

    invalid = _plan(_DESCRIPTION.replace("_их общение и помощь друг другу,_", "их общение и помощь друг другу,"))
    monkeypatch.setattr(cli, "_load_copy_fix_plan", lambda _: invalid)
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))

    def no_provider_access(*args, **kwargs):
        raise AssertionError("Provider accessed before format gate")

    monkeypatch.setattr(cli, "_writer_components", no_provider_access)
    with pytest.raises(typer.Exit) as failure:
        cli.apply_copy_fixes(
            plan=tmp_path / "unformatted.json",
            account="fedor-milovanov",
            confirm_channel=LORD_GOD_OWNER_CHANNEL,
            execute=False,
            max_operations=1,
            backup_output=None,
            result_output=None,
            client_secret=None,
        )
    assert failure.value.exit_code == 2


def test_lord_god_cli_rejects_live_title_drift_before_any_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    from video_channel_manager.cli import youtube as cli

    plan = _plan()
    monkeypatch.setattr(cli, "_load_copy_fix_plan", lambda _: plan)
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))

    class ReadOnlyWriter:
        def read_description(self, _video_id: str) -> SimpleNamespace:
            return SimpleNamespace(
                channel_id=LORD_GOD_OWNER_CHANNEL,
                title="A DIFFERENT LIVE TITLE",
                description=plan["operations"][0]["before_description"],
                revision=plan["operations"][0]["expected_revision"],
            )

        def replace_description(self, **_kwargs: object) -> None:
            raise AssertionError("Provider mutation must not occur")

    monkeypatch.setattr(
        cli,
        "_writer_components",
        lambda *_args: (None, None, ReadOnlyWriter()),
    )
    with pytest.raises(typer.Exit) as failure:
        cli.apply_copy_fixes(
            plan=tmp_path / "signed.json",
            account="fedor-milovanov",
            confirm_channel=LORD_GOD_OWNER_CHANNEL,
            execute=False,
            max_operations=1,
            backup_output=None,
            result_output=None,
            client_secret=None,
        )
    assert failure.value.exit_code == 2


def test_sermon_about_offerings_is_not_mistaken_for_personal_payment_request() -> None:
    content = _DESCRIPTION + "\n1:05:00 Пожертвования и воскресное богослужение"
    assert "retired_fundraising_or_payment" not in presentation_issues(content)


@pytest.mark.parametrize(
    "bad_second",
    [
        "*На занятии также обсуждается ответственность супругов перед Богом и церковью.*",
        "_На занятии также обсуждается ответственность супругов перед Богом и церковью._",
        "На занятии *также обсуждается* ответственность супругов перед Богом.",
        "Оригинал на английском: https://example.org/original",
        "- На занятии также обсуждается ответственность супругов перед Богом.",
        "# На занятии также обсуждается ответственность супругов перед Богом.",
        "`На занятии также обсуждается ответственность супругов перед Богом.`",
        "[На занятии также обсуждается ответственность супругов](https://example.org/)",
        "🎙️ На занятии также обсуждается ответственность супругов перед Богом.",
        "На занятии обсуждаются взгляды супругов: www.example.org/library.",
        "На занятии обсуждаются взгляды супругов: t.me/lordchrist.",
        "На занятии обсуждаются взгляды супругов: vk.ru/the_lord_god_is_my_strength.",
    ],
)
def test_two_preview_lines_reject_markup_links_and_lists_before_oauth(bad_second: str) -> None:
    original_second = "На занятии также обсуждается ответственность супругов перед Богом и церковью."
    after = _DESCRIPTION.replace(original_second, bad_second, 1)
    assert "share_preview_first_two_lines_not_plain" in presentation_issues(after)
    with pytest.raises(ValueError, match="share_preview_first_two_lines_not_plain"):
        require_lord_god_youtube_presentation(_plan(after))


def test_one_plain_line_followed_by_formatted_body_does_not_fake_preview_pass() -> None:
    original_second = "На занятии также обсуждается ответственность супругов перед Богом и церковью."
    after = _DESCRIPTION.replace(original_second + "\n\n", "\n\n", 1)
    assert "share_preview_first_two_lines_not_plain" in presentation_issues(after)
    assert "youtube_share_preview_emphasis" not in presentation_issues(after)


def test_two_plain_intro_lines_allow_emphasis_and_urls_in_later_paragraphs() -> None:
    assert presentation_issues(_DESCRIPTION) == []
