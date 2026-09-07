from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_quote_successor import (
    SuccessorSourceProof,
    git_blob_sha1,
    load_raw_successor_corpus,
    load_successor_corpus,
    load_successor_release,
    sha256_bytes,
    word_count,
)

ROOT = Path(__file__).resolve().parents[1]
LORDCHRIST = ROOT / "content" / "telegram" / "lordchrist"
CANDIDATES = LORDCHRIST / "successor-quotes-v1.json"
TRANSLATIONS = LORDCHRIST / "successor-translation-ledger-v1.json"
RELEASE = LORDCHRIST / "successor-release-v1.json"


def test_reviewed_successor_normalizes_exact_60_card_corpus() -> None:
    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS)

    assert len(corpus.posts) == 60
    assert [post.sequence for post in corpus.posts] == list(range(1, 61))
    assert len({post.publication_id for post in corpus.posts}) == 60
    assert len({post.semantic_key for post in corpus.posts}) == 60
    assert len({post.source.fragment_sha256 for post in corpus.posts}) == 60

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


def test_candidate_mixed_prose_cannot_leak_into_visible_quote() -> None:
    raw = load_raw_successor_corpus(CANDIDATES)
    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS)

    raw_augustine = raw.posts[0]
    raw_owen = raw.posts[2]
    augustine = corpus.posts[0]
    owen = corpus.posts[2]

    assert "Различие Лиц не превращает Троицу" in raw_augustine.candidate_quote_ru
    assert "Для Оуэна борьба с грехом" in raw_owen.candidate_quote_ru
    assert augustine.quote_ru == (
        "Отец, Сын и Святой Дух являют Божественное единство одной и той же сущности в нераздельном равенстве."
    )
    assert owen.quote_ru == "Умерщвляй грех, иначе он будет умерщвлять тебя."
    assert augustine.quote_ru != raw_augustine.candidate_quote_ru
    assert owen.quote_ru != raw_owen.candidate_quote_ru


def test_every_visible_quote_has_reviewed_source_translation_binding() -> None:
    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS)

    for post in corpus.posts:
        assert post.translation.scope == "exact_fragment_only"
        assert post.translation.review_state == "reviewed"
        assert post.translation.source_fragment_sha256 == post.source.fragment_sha256
        assert post.translation.binding_sha256.startswith("sha256:")

        if post.source.rights_class == "modern_short_quote_editorial_context":
            assert word_count(post.source.exact_fragment) <= 25
            assert word_count(post.quote_ru) <= 25
            assert post.editorial_context_ru is not None
            assert len(post.editorial_context_ru.strip()) >= 80
        else:
            assert post.editorial_context_ru is None


def test_unrelated_or_changed_visible_quote_breaks_reviewed_binding(tmp_path: Path) -> None:
    ledger = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    ledger["entries"][42]["quote_ru"] = "Это совершенно другой короткий текст."
    changed = tmp_path / "ledger.json"
    changed.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="visible translation does not match"):
        load_successor_corpus(CANDIDATES, changed)


def test_translation_cannot_bind_to_a_different_source_fragment(tmp_path: Path) -> None:
    ledger = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    ledger["entries"][0]["source_fragment_sha256"] = "sha256:" + ("0" * 64)
    changed = tmp_path / "ledger.json"
    changed.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="not bound to this exact source fragment"):
        load_successor_corpus(CANDIDATES, changed)


def test_modern_visible_quote_cannot_expand_beyond_25_words(tmp_path: Path) -> None:
    ledger = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    ledger["entries"][42]["quote_ru"] = " ".join(["слово"] * 26)
    changed = tmp_path / "ledger.json"
    changed.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_successor_corpus(CANDIDATES, changed)


def test_reviewed_piper_sequence_51_fragment_correction_is_amendment_bound() -> None:
    raw = load_raw_successor_corpus(CANDIDATES)
    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS)
    raw_post = raw.posts[50]
    post = corpus.posts[50]

    assert raw_post.publication_id == "lordchrist-successor-piper-father-spirit-authority"
    assert raw_post.source.exact_fragment.endswith("by the authority")
    assert post.source.exact_fragment == (
        "Pray to the Father in the power of the Spirit, in the name or by the authority and the merit of the Son."
    )
    assert word_count(post.source.exact_fragment) <= 25
    assert post.translation.source_fragment_sha256 == post.source.fragment_sha256


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.com/source",
        "https://127.0.0.1/source",
        "https://10.0.0.1/source",
        "https://169.254.1.1/source",
        "https://192.0.2.1/source",
        "https://[::1]/source",
    ],
)
def test_source_evidence_rejects_non_public_or_credential_urls(url: str) -> None:
    corpus = load_successor_corpus(CANDIDATES, TRANSLATIONS)
    payload = corpus.posts[0].source.model_dump(mode="json")
    payload["url"] = url

    with pytest.raises(ValidationError):
        SuccessorSourceProof.model_validate(payload)


def test_legacy_release_v1_remains_reproducible_but_is_not_effective_source_authority() -> None:
    release = load_successor_release(RELEASE, CANDIDATES, TRANSLATIONS)
    effective = load_successor_corpus(CANDIDATES, TRANSLATIONS)

    assert release.schema_version == 1
    assert release.release_id == "lordchrist-successor-quotes-v1"
    assert release.base_candidate_git_blob_sha1 == git_blob_sha1(CANDIDATES.read_bytes())
    assert release.translation_ledger_digest == sha256_bytes(TRANSLATIONS.read_bytes())
    assert release.normalized_corpus_digest == "sha256:2cda3946e4cf0e34ac476b668271e90d66cb1adb6528db6adc8c0cc6f86bf677"
    assert release.normalized_corpus_digest != effective.digest
    assert release.activation_policy == "after_predecessor_queue_complete"
    assert release.release_state == "staged_provider_inert"
    assert release.provider_writes_authorized is False
