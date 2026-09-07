from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_quote_successor import (
    CANONICAL_RELEASE_FILENAME,
    IntegrityAmendmentEntry,
    TranslationLedgerEntry,
    load_integrity_amendments,
    load_raw_successor_corpus,
    load_successor_corpus,
    load_successor_release,
    sha256_text,
    word_count,
)

ROOT = Path(__file__).resolve().parents[1]
LORDCHRIST = ROOT / "content" / "telegram" / "lordchrist"
CANDIDATES = LORDCHRIST / "successor-quotes-v1.json"
TRANSLATIONS = LORDCHRIST / "successor-translation-ledger-v1.json"
AMENDMENTS = LORDCHRIST / "successor-integrity-amendments-v1.json"
RELEASE = LORDCHRIST / CANONICAL_RELEASE_FILENAME
PUBLICATION_ID = "lordchrist-successor-piper-father-spirit-authority"
CORRECTED_FRAGMENT = (
    "Pray to the Father in the power of the Spirit, in the name or by the authority and the merit of the Son."
)
CORRECTED_QUOTE_RU = "Молитесь Отцу силой Духа, во имя Сына или на основании власти и заслуги Сына."


def test_integrity_amendment_is_generic_and_sealed() -> None:
    amendments = load_integrity_amendments(AMENDMENTS)
    assert len(amendments.entries) == 1
    amendment = amendments.entries[0]
    assert amendment.publication_id == PUBLICATION_ID
    assert amendment.corrected_exact_fragment == CORRECTED_FRAGMENT
    assert amendment.corrected_quote_ru == CORRECTED_QUOTE_RU
    assert amendment.source_fragment_sha256 == sha256_text(CORRECTED_FRAGMENT)
    assert word_count(amendment.corrected_exact_fragment) <= 25
    assert word_count(amendment.corrected_quote_ru) <= 25


def test_legacy_translation_override_is_readable_but_not_source_authority() -> None:
    payload = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    legacy = payload["entries"][50]
    assert legacy["publication_id"] == PUBLICATION_ID
    assert "exact_fragment_override" in legacy

    entry = TranslationLedgerEntry.model_validate(legacy)
    assert entry.legacy_exact_fragment_override == legacy["exact_fragment_override"]
    assert "exact_fragment_override" not in entry.model_dump(mode="json")
    assert "legacy_exact_fragment_override" not in entry.model_dump(mode="json")

    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS, AMENDMENTS)
    post = corpus.posts[50]
    assert post.publication_id == PUBLICATION_ID
    assert post.source.exact_fragment == CORRECTED_FRAGMENT
    assert post.source.exact_fragment != legacy["exact_fragment_override"]
    assert post.quote_ru == CORRECTED_QUOTE_RU


def test_candidate_fragment_precondition_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(AMENDMENTS.read_text(encoding="utf-8"))
    payload["entries"][0]["candidate_source_fragment_sha256"] = "sha256:" + "0" * 64
    changed = tmp_path / "amendments.json"
    changed.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate source precondition mismatch"):
        load_successor_corpus(CANDIDATES, TRANSLATIONS, changed)


def test_legacy_translation_preconditions_fail_closed(tmp_path: Path) -> None:
    payload = json.loads(AMENDMENTS.read_text(encoding="utf-8"))
    payload["entries"][0]["legacy_translation_source_fragment_sha256"] = "sha256:" + "0" * 64
    changed_source = tmp_path / "amendments-source.json"
    changed_source.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(ValueError, match="legacy source binding precondition mismatch"):
        load_successor_corpus(CANDIDATES, TRANSLATIONS, changed_source)

    payload = json.loads(AMENDMENTS.read_text(encoding="utf-8"))
    payload["entries"][0]["legacy_translation_binding_sha256"] = "sha256:" + "0" * 64
    changed_binding = tmp_path / "amendments-binding.json"
    changed_binding.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(ValueError, match="legacy translation binding precondition mismatch"):
        load_successor_corpus(CANDIDATES, TRANSLATIONS, changed_binding)


def test_amendment_source_and_translation_are_cryptographically_bound() -> None:
    payload = json.loads(AMENDMENTS.read_text(encoding="utf-8"))["entries"][0]

    changed_fragment = dict(payload)
    changed_fragment["corrected_exact_fragment"] = CORRECTED_FRAGMENT + " Extra."
    with pytest.raises(ValidationError, match="source fragment digest mismatch"):
        IntegrityAmendmentEntry.model_validate(changed_fragment)

    changed_translation = dict(payload)
    changed_translation["corrected_quote_ru"] = CORRECTED_QUOTE_RU + " Дополнение."
    with pytest.raises(ValidationError, match="translation binding mismatch"):
        IntegrityAmendmentEntry.model_validate(changed_translation)


def test_translation_data_cannot_replace_primary_source_evidence(tmp_path: Path) -> None:
    ledger = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    ledger["entries"][50]["exact_fragment_override"] = (
        "This legacy value may remain readable but must never become primary source evidence."
    )
    changed = tmp_path / "ledger.json"
    changed.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    corpus = load_successor_corpus(CANDIDATES, changed, AMENDMENTS)
    assert corpus.posts[50].source.exact_fragment == CORRECTED_FRAGMENT


def test_legacy_override_requires_a_sealed_integrity_amendment(tmp_path: Path) -> None:
    empty = {
        "schema_name": "video-channel-manager.telegram-quote-successor-integrity-amendments",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "corpus_id": "lordchrist-successor-quotes-v1",
        "review_state": "reviewed",
        "entries": [],
    }
    changed = tmp_path / "amendments.json"
    changed.write_text(json.dumps(empty, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(ValueError):
        load_successor_corpus(CANDIDATES, TRANSLATIONS, changed)


def test_amended_corpus_preserves_reviewed_inventory_contract() -> None:
    raw = load_raw_successor_corpus(CANDIDATES)
    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS, AMENDMENTS)

    assert len(raw.posts) == len(corpus.posts) == 60
    assert [post.publication_id for post in corpus.posts] == [post.publication_id for post in raw.posts]
    assert [post.sequence for post in corpus.posts] == list(range(1, 61))

    authors = Counter(post.source.author for post in corpus.posts)
    rights = Counter(post.source.rights_class for post in corpus.posts)
    themes = Counter(post.theme for post in corpus.posts)
    assert len(authors) == 12
    assert max(authors.values()) == 7
    assert rights == {
        "public_domain_contiguous_excerpt": 42,
        "modern_short_quote_editorial_context": 18,
    }
    assert len(themes) == 12


def test_release_v2_reseals_candidate_ledger_amendment_and_effective_corpus() -> None:
    release = load_successor_release(RELEASE, CANDIDATES, TRANSLATIONS, AMENDMENTS)
    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS, AMENDMENTS)

    assert release.schema_version == 2
    assert release.release_id == "lordchrist-successor-quotes-v1-integrity-v2"
    assert release.normalized_corpus_digest == corpus.digest
    assert release.activation_policy == "after_predecessor_queue_complete"
    assert release.release_state == "staged_provider_inert"
    assert release.provider_writes_authorized is False
