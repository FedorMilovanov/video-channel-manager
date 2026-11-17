"""Charnock history-01: source candidate cannot impersonate the published edition."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock"
ORIGINAL = BASE / "lordchrist-telegraph-charnock-history-01.json"
CANDIDATE = ROOT / "content/research/charnock-history01-birth-evidence-candidate-20261117.json"
QUEUE = ROOT / "content/telegram/lordchrist/telegraph-v1/article-queue.json"
RECEIPTS = ROOT / "docs/audits/2026-11-04-charnock-publication-link-replacement-map.json"
PUBLICATION_ID = "lordchrist-telegraph-charnock-history-01"


def _blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def test_current_public_source_is_still_immutable() -> None:
    assert _blob(ORIGINAL) == "a288b15d403fe2e261c1409c1f424a66c5d82548"
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    item = next(x for x in queue["items"] if x["publication_id"] == PUBLICATION_ID)
    assert item["article"]["git_blob_sha"] == _blob(ORIGINAL)
    receipts = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    verified = next(x for x in receipts["targets"] if x["publication_id"] == PUBLICATION_ID)
    assert verified["corrected_document_git_blob_sha"] == _blob(ORIGINAL)
    assert verified["provider_writes_authorized"] is False
    # The original 15-Nov receipt is historical and cannot approve an unseen 17-Nov revision.
    assert verified["editorial_revision_status"] == "verified_in_place"


def test_candidate_json_has_only_approved_attribution_changes() -> None:
    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    expected = copy.deepcopy(original)
    expected["metadata"]["updated_at"] = "2026-11-17"
    blocks = {block["block_id"]: block for block in expected["blocks"]}
    intro = blocks["p-2"]["text"]
    assert intro[0].count("(1628–1680)") == 1
    intro[0] = intro[0].replace("(1628–1680)", "(ок. 1628–1680)")
    birth = blocks["p-4"]["text"]
    previous = "Чарнок родился в Лондоне в 1628 году."
    corrected = (
        "Энтони Вуд в биографическом свидетельстве 1691 года сообщает, "
        "что Чарнок родился в Лондоне. Часто указываемый 1628 год является "
        "приблизительной датой, выведенной из сведений о возрасте; "
        "запись о рождении или крещении пока не установлена."
    )
    assert birth[0].count(previous) == 1
    birth[0] = birth[0].replace(previous, corrected)
    footnote = blocks["p-43"]["text"]
    # The relevant long paragraph contains an italic text fragment.
    assert isinstance(footnote, list)
    before, after = (
        " и статьёй W. G. Blaikie в ",
        ', свидетельством Энтони Вуда в «Athenæ Oxonienses» (1691, т. II, '
        "вход [429], с. 491–492) и статьёй W. G. Blaikie в ",
    )
    slots = [i for i, x in enumerate(footnote) if isinstance(x, str) and before in x]
    assert len(slots) == 1
    footnote[slots[0]] = footnote[slots[0]].replace(before, after)
    extra = [source for source in candidate["sources"] if source["source_id"] == "src-wood-1691-birth"]
    assert len(extra) == 1
    assert "A71277" in extra[0]["url"]
    assert "pp. 491–492" in extra[0]["label"]
    insert_at = next(i for i, x in enumerate(expected["sources"]) if x["source_id"] == "src-scripture-synodal")
    expected["sources"].insert(insert_at, extra[0])
    assert candidate == expected, "Unexpected Charnock history-01 changes outside the approved evidence delta"


def test_candidate_markdown_is_exactly_corresponding_source_delta() -> None:
    original = (BASE / "lordchrist-telegraph-charnock-history-01.md").read_text(encoding="utf-8")
    candidate = (ROOT / "content/research/charnock-history01-birth-evidence-candidate-20261117.md").read_text(
        encoding="utf-8"
    )
    changes = [
        ("(1628–1680)", "(ок. 1628–1680)"),
        (
            "Чарнок родился в Лондоне в 1628 году.",
            "Энтони Вуд в биографическом свидетельстве 1691 года сообщает, "
            "что Чарнок родился в Лондоне. Часто указываемый 1628 год является "
            "приблизительной датой, выведенной из сведений о возрасте; "
            "запись о рождении или крещении пока не установлена.",
        ),
        (
            " и статьёй W. G. Blaikie в ",
            ', свидетельством Энтони Вуда в «Athenæ Oxonienses» '
            "(1691, т. II, вход [429], с. 491–492) и статьёй W. G. Blaikie в ",
        ),
    ]
    expected = original
    for old, new in changes:
        assert expected.count(old) == 1
        expected = expected.replace(old, new)
    assert candidate == expected
