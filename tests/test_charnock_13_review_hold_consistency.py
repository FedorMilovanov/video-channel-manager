"""Prevent a superseded Charnock #13 review from acting as a release grant."""

import json
from hashlib import sha1
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-13-проверка.md"


def test_charnock_13_current_verdict_is_hold_and_old_ready_verdict_retired() -> None:
    text = REVIEW.read_text(encoding="utf-8")
    assert text.startswith("# Проверка Telegraph-издания 13 (2026-10-25)")
    assert "ДЕЙСТВУЮЩИЙ СТАТУС — EDITORIAL/PUBLICATION_HOLD" in text[:750]
    assert "ИСТОРИЧЕСКИЙ ВЕРДИКТ" in text
    assert "SUPERSEDED" in text
    assert "q-3" in text and "q-19" in text
    assert "Вердикт: **готово к Telegraph-публикации" not in text


def test_charnock_13_writer_hold_is_not_only_documentary() -> None:
    source = (ROOT / "src/video_channel_manager/lordchrist_charnock_reschedule.py").read_text(encoding="utf-8")
    assert 'CHARNOCK_EDITORIAL_HOLDS = frozenset({"lordchrist-telegraph-charnock-13"})' in source
    assert 'args.stage in ("prepare", "send")' in source


def test_charnock_13_quotation_omissions_are_visibly_marked() -> None:
    """Two documented jumps must never masquerade as uninterrupted Charnock quotations."""
    candidate_directory = ROOT / "content/research"
    data = json.loads(
        (candidate_directory / "charnock-13-quotation-gap-candidate-20261117.json").read_text(encoding="utf-8")
    )
    markdown = (candidate_directory / "charnock-13-quotation-gap-candidate-20261117.md").read_text(encoding="utf-8")
    # Active canonical article remains byte-for-byte pinned to reviewed SHA.
    current = REVIEW.parent / "lordchrist-telegraph-charnock-13.json"
    payload = current.read_bytes()
    blob = b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    assert sha1(blob).hexdigest() == "cc9b20e98cb88c14b7c3ec739a4c07c4f738cae9"
    joins = {
        "q-3": ("без прикрас. […] Молча подавляйте", "без прикрас. Молча подавляйте"),
        "q-19": ("отражаться обратно к Богу. […] Что за утешение", "душ должна обращаться к Нему. Что за утешение"),
    }
    for block_id, (explicit, naked) in joins.items():
        block = next(block for block in data["blocks"] if block.get("block_id") == block_id)
        text = "".join(part if isinstance(part, str) else part.get("text", "") for part in block["blocks"][0]["text"])
        assert explicit in text and naked not in text
        assert explicit in markdown and naked not in markdown
    assert "EDITORIAL/PUBLICATION_HOLD" in REVIEW.read_text(encoding="utf-8")


def test_charnock_13_candidate_is_exactly_the_reviewed_delta() -> None:
    """The sidecar cannot silently acquire unreviewed text or publication changes."""
    candidate = ROOT / "content/research"
    article = REVIEW.parent
    originals = {
        "json": (article / "lordchrist-telegraph-charnock-13.json").read_text(encoding="utf-8"),
        "md": (article / "lordchrist-telegraph-charnock-13.md").read_text(encoding="utf-8"),
    }
    expected_replacements = [
        ("без прикрас. Молча подавляйте", "без прикрас. […] Молча подавляйте"),
        (
            "Наши умы — луч от Бога; и потому, как лучи солнца, коснувшись земли, "
            "должны отражаться обратно к Богу, так и активность наших душ должна "
            "обращаться к Нему. Что за утешение",
            "Наши умы — луч от Бога; поэтому они, подобно лучам солнца, "
            "коснувшимся земли, должны отражаться обратно к Богу. […] Что за утешение",
        ),
    ]
    for suffix, original in originals.items():
        expected = original
        if suffix == "json":
            expected = expected.replace('"updated_at": "2026-11-04"', '"updated_at": "2026-11-17"')
            expected = expected.replace(
                '"revision": "charnock-13-v1"',
                '"revision": "charnock-13-v2-editorial-candidate"',
            )
        for previous, correction in expected_replacements:
            assert expected.count(previous) == 1
            expected = expected.replace(previous, correction)
        target = candidate / f"charnock-13-quotation-gap-candidate-20261117.{suffix}"
        assert target.read_text(encoding="utf-8") == expected
