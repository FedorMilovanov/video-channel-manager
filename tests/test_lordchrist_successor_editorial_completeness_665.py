from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_runtime import build_successor_runtime_queue
from video_channel_manager.telegram_quote_successor import load_successor_corpus
from video_channel_manager.telegram_successor_editorial import (
    load_successor_editorial_layer,
    resolve_successor_editorial_contexts,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
CANDIDATE = CONTENT / "successor-quotes-v1.json"
TRANSLATION = CONTENT / "successor-translation-ledger-v1.json"
AMENDMENTS = CONTENT / "successor-integrity-amendments-v1.json"
RELEASE = CONTENT / "successor-release-v2.json"
ACTIVATION = CONTENT / "successor-activation-v1.json"
EDITORIAL = CONTENT / "successor-runtime-editorial-v1.json"
POLICY = CONTENT / "presentation-policy.json"
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
SUCCESSOR_DIGEST = "sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"


def _corpus():
    return load_successor_corpus(CANDIDATE, TRANSLATION, AMENDMENTS)


def _runtime():
    policy = load_presentation_policy(POLICY)
    return build_successor_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
        release_path=RELEASE,
        activation_path=ACTIVATION,
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
    )


def test_editorial_layer_fills_only_the_42_public_domain_context_gaps() -> None:
    corpus = _corpus()
    source_context = {
        card.publication_id: card.editorial_context_ru.strip()
        for card in corpus.posts
        if card.editorial_context_ru is not None and card.editorial_context_ru.strip()
    }
    layer = load_successor_editorial_layer(EDITORIAL)
    layer_ids = {entry.publication_id for entry in layer.entries}
    resolved = resolve_successor_editorial_contexts(corpus, EDITORIAL)

    assert corpus.digest == SUCCESSOR_DIGEST
    assert len(corpus.posts) == 60
    assert len(source_context) == 18
    assert len(layer.entries) == 42
    assert layer_ids.isdisjoint(source_context)
    assert len(resolved) == 60
    assert all(len(context) >= 80 for context in resolved.values())
    assert all(resolved[publication_id] == context for publication_id, context in source_context.items())
    assert "английский пуританин XVII века" in resolved["lordchrist-successor-gurnall-arms-dependence"]


def test_every_successor_runtime_post_labels_explanation_before_attribution() -> None:
    queue = _runtime()

    assert queue.digest == SUCCESSOR_DIGEST
    assert len(queue.posts) == 60
    for post in queue.posts:
        assert post.text.count("\n\nПояснение: ") == 1
        assert post.text.count("\n\n© ") == 1
        assert post.text.index("\n\nПояснение: ") < post.text.index("\n\n© ")
        explanation = post.text.split("\n\nПояснение: ", 1)[1].split("\n\n© ", 1)[0]
        assert len(explanation) >= 80


def test_missing_editorial_fallback_fails_closed(tmp_path: Path) -> None:
    corpus = _corpus()
    payload = json.loads(EDITORIAL.read_text(encoding="utf-8"))
    removed = payload["entries"].pop()
    broken = tmp_path / "editorial-missing.json"
    broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="editorial coverage differs") as excinfo:
        resolve_successor_editorial_contexts(corpus, broken)
    assert removed["publication_id"] in str(excinfo.value)


def test_editorial_layer_cannot_shadow_modern_source_context(tmp_path: Path) -> None:
    corpus = _corpus()
    modern = next(
        card for card in corpus.posts if card.editorial_context_ru is not None and card.editorial_context_ru.strip()
    )
    payload = json.loads(EDITORIAL.read_text(encoding="utf-8"))
    payload["entries"].append(
        {
            "publication_id": modern.publication_id,
            "editorial_context_ru": "Этот текст намеренно достаточно длинный для схемы, но он не должен иметь права подменить уже проверенное исходное редакционное пояснение современной цитаты.",
        }
    )
    broken = tmp_path / "editorial-shadow.json"
    broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="editorial coverage differs"):
        resolve_successor_editorial_contexts(corpus, broken)


def test_editorial_layer_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    corpus = _corpus()
    payload = json.loads(EDITORIAL.read_text(encoding="utf-8"))
    payload["normalized_corpus_digest"] = "sha256:" + "0" * 64
    broken = tmp_path / "editorial-wrong-digest.json"
    broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="digest differs"):
        resolve_successor_editorial_contexts(corpus, broken)
