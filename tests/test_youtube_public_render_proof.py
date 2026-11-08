from video_channel_manager.youtube_public_render_proof import verify_public_description


PARA = "Эта строка повторяется для проверки смыслового текста на публичной странице YouTube. " * 4
EXPECTED = (
    "Плейлист «Поэты»: https://www.youtube.com/playlist?list=ABC_DEFG\n"
    "*VK:* https://vk.ru/thelegendarypoet\n\n"
    + PARA
    + "\n\n"
    + ("Описан *точный текст.* и отмечен _конкретный контекст._ " * 7)
)
PLAIN = (
    EXPECTED.replace("*VK:*", "VK:")
    .replace("*точный текст.*", "точный текст.")
    .replace("_конкретный контекст._", "конкретный контекст.")
)


def proof(**overrides):
    args = dict(
        studio_expected=EXPECTED,
        studio_observed=EXPECTED,
        public_description_text=PLAIN,
        public_bold_fragments=["VK:", "точный текст."],
        public_italic_fragments=["конкретный контекст."],
    )
    args.update(overrides)
    return verify_public_description(**args)


def test_full_live_render_requires_real_styled_spans_and_full_public_text() -> None:
    result = proof()
    assert result.ok, result
    assert result.bold_expected == result.bold_verified == 8
    assert result.italic_expected == result.italic_verified == 7


def test_raw_markers_in_studio_are_not_public_bold_or_italic_evidence() -> None:
    result = proof(public_bold_fragments=[], public_italic_fragments=[])
    assert not result.ok
    assert "bold_not_publicly_rendered" in result.problems
    assert "italic_not_publicly_rendered" in result.problems


def test_same_first_paragraph_does_not_hide_stale_later_paragraph() -> None:
    result = proof(public_description_text=PARA)
    assert not result.ok
    assert "public_description_stale_or_incomplete" in result.problems


def test_studio_readback_drifts_even_when_public_copy_matches() -> None:
    result = proof(studio_observed=EXPECTED + " ДРУГОЕ")
    assert not result.ok
    assert "studio_text_drift" in result.problems


def test_urls_with_underscores_do_not_become_italic_markers() -> None:
    result = proof()
    assert result.italic_expected == 7
