"""Build the nonpublishing LordChrist quote editorial preview from verified evidence.

The output lives only under docs/audits, uses a schema *different* from the
publisher's queue and has no release ID or provider credentials. Never write
to content/, the protected ledger or a provider.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs/audits"
SIGNED_QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
OUTPUT = AUDITS / "2026-11-04-lordchrist-30-card-editorial-preview-inert.json"

CRITICAL_DRAFTS = AUDITS / "2026-11-04-lordchrist-contiguous-quote-redrafts.json"
REMAINING_DRAFTS = AUDITS / "2026-11-04-lordchrist-remaining-10-contiguous-redrafts.json"
INDEX = AUDITS / "2026-11-04-lordchrist-30-quote-editorial-candidate-index.json"
REGISTER = AUDITS / "2026-11-03-lordchrist-v4-quote-editorial-register.json"
REMAINING_AUDIT = AUDITS / "2026-11-04-lordchrist-remaining-20-source-audit.json"
SEMANTIC_REVISIONS = AUDITS / "2026-11-04-lordchrist-quote-semantic-revisions-inert.json"
RETAINED_VERSE_REVIEW = AUDITS / "2026-11-04-lordchrist-retained-verse-and-quotation-review.json"
SPURGEON_OWEN_REVIEW = AUDITS / "2026-11-04-lordchrist-owen-spurgeon-contiguity-inert.json"
BILINGUAL_LINE_EDITS = AUDITS / "2026-11-04-lordchrist-bilingual-line-edits-inert.json"
PROPOSAL_FILES = (
    AUDITS / "2026-11-03-lordchrist-quote-exact-editorial-proposals.json",
    AUDITS / "2026-11-04-lordchrist-retained-quote-field-proposals.json",
)

SCHEMA = "video-channel-manager.lordchrist-nonpublishing-editorial-preview"
STATUS = "editorial_preview_unapproved_no_provider_mutations"


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _replace_exact(source: dict[str, Any], field: str, before: str, after: str) -> None:
    path = field.split(".")
    target = source
    for component in path[:-1]:
        target = target[component]
        if not isinstance(target, dict):
            raise ValueError(f"Unexpected nested field: {field}")
    old = target[path[-1]]
    if not isinstance(old, str) or old.count(before) != 1 or before == after:
        raise ValueError(f"Original field no longer matches exactly: {field}")
    target[path[-1]] = old.replace(before, after, 1)


def _source_hashtags(original_text: str) -> str:
    tags = [line for line in original_text.splitlines() if line.startswith("#")]
    if len(tags) != 1:
        raise ValueError(f"Expected exactly one original tag line, got {len(tags)}")
    return tags[0]


def _nest_original_speech_quotes(body: str) -> str:
    """Add the publication-level quotation without flattening nested Bible speech."""
    depth = 0
    output: list[str] = []
    for char in body:
        if char in (chr(171), chr(8222)):
            depth += 1
            if depth > 2:
                raise ValueError("Unsupported third level of quotes inside draft")
            output.append(chr(8222) if depth == 1 else chr(8216))
        elif char in (chr(187), chr(8220)):
            if depth == 0:
                raise ValueError("Unmatched closing speech quotation inside draft")
            output.append(chr(8220) if depth == 1 else chr(8217))
            depth -= 1
        else:
            output.append(char)
    if depth:
        raise ValueError("Unclosed inner source quotation")
    return "".join(output)


def _normalize_retained_quotation_depth(full_post: str) -> str:
    """Correct inner speech typography; preserve all words, attribution, and tags."""
    separator = "\n\n" + chr(169) + " "
    if full_post.count(separator) != 1:
        raise ValueError("Retained post must contain one unambiguous attribution boundary")
    quoted, rest = full_post.split(separator, 1)
    if not (quoted.startswith(chr(171)) and quoted.endswith(chr(187))):
        raise ValueError("Retained post requires intact top-level speech quotation")
    inner = _nest_original_speech_quotes(quoted[1:-1])
    return chr(171) + inner + chr(187) + separator + rest


def _draft_render(body: str, author: str, work: str, tags: str) -> str:
    if not body or (body.startswith(chr(171)) and body.endswith(chr(187))):
        raise ValueError("Draft translation must be the unwrapped Russian excerpt")
    blocks = [part.strip() for part in body.split("\n\n") if part.strip()]
    if len(blocks) == 4:
        # The actual TelegramPost contract requires 2-3 quote paragraphs.
        # Combine the two contiguous middle paragraphs without dropping words.
        blocks[1:3] = [blocks[1] + " " + blocks[2]]
    if not 2 <= len(blocks) <= 3 or any(len(block) < 80 for block in blocks):
        raise ValueError("Quote preview violates the 2-3 dense paragraph contract")
    nested = _nest_original_speech_quotes("\n\n".join(blocks))
    return f"{chr(171)}{nested}{chr(187)}\n\n{chr(169)} {author}, {chr(171)}{work}{chr(187)}\n\n{tags}"


def _apply_bound_line_edits(preview: list[dict[str, Any]], queue_sha: str) -> int:
    """Apply any number of exact-source, inert bilingual edits without one-off code branches."""
    packet = _load(BILINGUAL_LINE_EDITS)
    if not (
        packet["schema_name"] == "video-channel-manager.lordchrist-source-bound-bilingual-line-edits-inert"
        and packet["schema_version"] == 1
        and packet["original_queue_sha256"] == queue_sha
        and packet["editorial_approval"] is False
        and packet["full_bilingual_review_complete"] is False
        and packet["rights_review_complete"] is False
        and packet["provider_write_authorization"] is False
        and packet["protected_ledger_write_authorization"] is False
        and packet["approved_new_queue"] is False
    ):
        raise ValueError("Line-edit packet missing, stale or unsafe for editorial preview")
    rows = packet["revisions"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Line-edit packet must contain source-grounded revisions")

    seen: set[int] = set()
    for row in rows:
        number = row["sequence"]
        if not isinstance(number, int) or not 1 <= number <= len(preview) or number in seen:
            raise ValueError("Duplicate or invalid sequence in line-edit packet")
        seen.add(number)
        card = preview[number - 1]
        if not (
            card["sequence"] == number
            and card["publication_id"] == row["original_publication_id"]
            and card["original_full_post_sha256"] == row["original_full_post_sha256"]
            and card["candidate_full_post_sha256"] == row["expected_prior_preview_full_post_sha256"]
            and card["source"]["url"] == row["source_url"]
        ):
            raise ValueError(f"Stale or mismatched candidate in line-edit packet: {number}")
        witness = row["source_witness"]
        if not (
            witness["http_status"] == 200
            and witness["source_begin_anchor_exact"]
            and witness["source_end_anchor_exact"]
            and witness["forward_order"]
            and witness["english_source_span_words"] >= 80
            and witness["full_sentence_alignment_certified"] is False
            and len(witness["phrase_checks"]) == len(row["edits"])
            and all(point["exact_tokens_in_original"] is True for point in witness["phrase_checks"])
        ):
            raise ValueError(f"Line-edit packet lacks source evidence: {number}")
        edits = row["edits"]
        if not isinstance(edits, list) or not 1 <= len(edits) <= 5:
            raise ValueError("Line edits must be narrowly scoped")
        for edit in edits:
            if edit["field"] not in ("text", "source.anchor_start", "source.anchor_end"):
                raise ValueError("Cannot change identifiers, permissions or source URL in line edits")
            if not edit["source_phrase"] or not edit["issue"]:
                raise ValueError("Every line edit needs primary-source phrase and rationale")
            if "??" in edit["proposed_after"] or chr(65533) in edit["proposed_after"]:
                raise ValueError("Encoding corruption in source-bound Cyrillic editorial text")
            _replace_exact(card, edit["field"], edit["exact_before"], edit["proposed_after"])
        if not (
            _sha(card["text"]) == row["candidate_full_post_sha256"]
            and _sha(card["source"]["anchor_start"]) == row["candidate_begin_anchor_sha256"]
        ):
            raise ValueError(f"Post-edit exact content SHA failed on {number}")
        if len(card["text"]) > 4096:
            raise ValueError(f"Reviewed card {number} exceeds Telegram text envelope")
        card["candidate_full_post_sha256"] = _sha(card["text"])
        card["source_bound_line_edit_status"] = "unapproved_pending_full_bilingual_and_edition_rights"
        card["source_bound_line_edit_evidence_file"] = BILINGUAL_LINE_EDITS.relative_to(ROOT).as_posix()
        card["source_bound_line_edit_count"] = len(edits)
    return len(seen)


def build() -> dict[str, Any]:
    source_text = SIGNED_QUEUE.read_text(encoding="utf-8")
    queue_sha = _sha(source_text)
    signed = _load(SIGNED_QUEUE)
    original = signed["posts"]
    index = _load(INDEX)
    register = _load(REGISTER)
    remaining_audit = _load(REMAINING_AUDIT)
    revisions = _load(SEMANTIC_REVISIONS)
    critical = _load(CRITICAL_DRAFTS)
    remaining = _load(REMAINING_DRAFTS)
    if (
        len(original) != 30
        or len(index["entries"]) != 30
        or index["original_queue_sha256"] != queue_sha
        or register["queue_text_sha256"] != queue_sha
        or remaining_audit["queue_text_sha256"] != queue_sha
        or len(register["entries"]) != 30
        or len(remaining_audit["entries"]) != 20
        or critical["source_queue_sha256"] != queue_sha
        or remaining["queue_text_sha256"] != queue_sha
    ):
        raise ValueError("Evidence packages no longer bind the exact signed 30-post v4 queue")
    if not (
        index["approved_new_queue"] is False
        and index["provider_write_authorization"] is False
        and critical["editorial_approval"] is False
        and remaining["editorial_approval"] is False
    ):
        raise ValueError("Expected *unapproved* editorial evidence, not a release")
    drafts = {
        row["sequence"]: (row, path)
        for file, path in ((critical, CRITICAL_DRAFTS), (remaining, REMAINING_DRAFTS))
        for row in file["drafts"]
    }
    if len(drafts) != 20:
        raise ValueError("Exactly 20 nonoverlapping contiguous-source drafts are required")

    proposals: dict[int, list[tuple[dict[str, Any], Path]]] = {}
    for file_path in PROPOSAL_FILES:
        file = _load(file_path)
        approval = file.get("editorial_approval", file.get("approval"))
        if approval is not False or file["provider_write_authorization"] is not False:
            raise ValueError(f"Unexpected proposal authorization in {file_path}")
        recorded_digest = file.get("bound_queue_text_sha256", file.get("original_queue_sha256"))
        if recorded_digest != queue_sha:
            raise ValueError(f"Proposal package has a different original queue: {file_path}")
        for proposal in file["edits"]:
            proposals.setdefault(proposal["sequence"], []).append((proposal, file_path))
    if sum(len(items) for items in proposals.values()) != 19:
        raise ValueError("Expected 19 distinct source-bound editorial correction proposals")

    context_rows = {row["sequence"]: row for row in remaining_audit["entries"]}
    if len(context_rows) != 20:
        raise ValueError("Duplicate or missing source context evidence")
    preview: list[dict[str, Any]] = []
    for i, (original_post, idx) in enumerate(zip(original, index["entries"], strict=True)):
        sequence = i + 1
        editorial_review = register["entries"][i]
        if (
            original_post["sequence"] != sequence
            or idx["sequence"] != sequence
            or editorial_review["sequence"] != sequence
            or editorial_review["publication_id"] != original_post["publication_id"]
        ):
            raise ValueError("Sequence/order conflict")
        full_old_sha = _sha(original_post["text"])
        if (
            idx["original_text_sha256"] != full_old_sha
            or idx["original_publication_id"] != original_post["publication_id"]
        ):
            raise ValueError(f"Evidence identity mismatch in item {sequence}")

        changed = copy.deepcopy(original_post)
        applied: list[dict[str, str]] = []
        for edit, path in proposals.get(sequence, []):
            # Redrafted cards use their own fully rewritten source/text evidence.
            # Do not silently apply old-text edits to an unrelated new draft.
            if sequence in drafts:
                continue
            if edit.get("original_publication_id", edit.get("publication_id")) != original_post["publication_id"]:
                raise ValueError("Proposed field edit belongs to a different post")
            _replace_exact(changed, edit["field"], edit["exact_before"], edit["proposed_after"])
            applied.append({"field": edit["field"], "proposal_file": path.relative_to(ROOT).as_posix()})

        if sequence in drafts:
            draft, evidence_file = drafts[sequence]
            if idx["editorial_mode"] != "contiguous_redraft":
                raise ValueError("Draft/index editorial track mismatch")
            identity = draft.get("previous_publication_id", draft.get("original_publication_id"))
            if identity != original_post["publication_id"]:
                raise ValueError("Draft is not source-identity bound")
            old_digest = draft.get("previous_text_sha256", draft.get("original_quote_sha256"))
            if old_digest != full_old_sha:
                raise ValueError("Draft original SHA does not match")
            new_body_sha = draft.get("draft_text_sha256", draft.get("proposed_text_sha256"))
            if new_body_sha != _sha(draft["translation_ru"]):
                raise ValueError("Draft body SHA mismatch")
            new_url = draft["source_url"]
            new_work = draft["work_ru"]
            changed["title"] = f"«{draft['title_ru']}» — {draft['author_ru']}"
            changed["text"] = _draft_render(
                draft["translation_ru"],
                draft["author_ru"],
                new_work,
                _source_hashtags(original_post["text"]),
            )
            changed["preview_paragraph_normalization"] = (
                "joined_adjacent_middle_paragraphs_without_cutting_text"
                if len(draft["translation_ru"].split("\n\n")) == 4
                else None
            )
            changed["source"] = {
                "author": draft["author_ru"],
                "work": new_work,
                "location": draft["source_section"],
                "url": new_url,
                "anchor_start": draft["anchor_start"],
                "anchor_end": draft["anchor_end"],
                "primary_source_type": "historical_primary",
                "edition_rights_status": "requires_edition_specific_review",
                "translation_review_status": "pending_full_bilingual_check",
                "translation_language": "ru",
                "original_language": "la" if sequence == 6 else "en",
            }
            if sequence == 6:
                changed["source"]["latin_original_url"] = draft["original_latin_url"]
                changed["source"]["source_edition"] = draft["source_edition"]
            evidence = evidence_file.relative_to(ROOT).as_posix()
        else:
            changed["preview_paragraph_normalization"] = None
            if idx["editorial_mode"] != "retain_provisionally":
                raise ValueError("Provisional selection/index mismatch")
            # Explicitly revoke acceptance inherited from the signed old manifest.
            changed["source"].pop("verification_status", None)
            changed["source"].pop("verified_on", None)
            changed["source"].pop("copyright_status", None)
            changed["source"]["translation_review_status"] = "pending_full_bilingual_check"
            changed["source"]["edition_rights_status"] = "requires_edition_specific_review"
            before_quote_normalization = changed["text"]
            changed["text"] = _normalize_retained_quotation_depth(before_quote_normalization)
            changed["retained_quote_depth_normalization"] = (
                "typography_only_no_word_changes" if changed["text"] != before_quote_normalization else None
            )
            evidence = SIGNED_QUEUE.relative_to(ROOT).as_posix()

        if len(changed["text"]) > 4096:
            raise ValueError(f"Candidate {sequence} exceeds the Telegram text envelope")
        if idx["candidate_body_sha256"] != (
            _sha(drafts[sequence][0]["translation_ru"])
            if sequence in drafts
            else _sha(original_post["text"].split("\n\n©")[0])
        ):
            raise ValueError(f"Candidate index body SHA mismatch in {sequence}")

        changed["editorial_preview_status"] = STATUS
        changed["original_preliminary_risk"] = editorial_review["preliminary_risk"]
        changed["original_editorial_finding"] = editorial_review["finding"]
        changed["supplementary_context_finding"] = (
            context_rows[sequence]["finding"] if sequence in context_rows else None
        )
        changed["bilingual_alignment_status"] = "pending_complete_sentence_alignment"
        changed["edition_specific_rights_status"] = "pending_independent_review"
        changed["original_full_post_sha256"] = full_old_sha
        changed["candidate_full_post_sha256"] = _sha(changed["text"])
        changed["evidence_file"] = evidence
        changed["applied_original_field_proposals"] = applied
        changed["editorial_approval"] = False
        changed["provider_write_authorization"] = False
        preview.append(changed)

    if [p["sequence"] for p in preview] != list(range(1, 31)):
        raise ValueError("Preview must contain all 30 ordered identities")
    if not (
        revisions["schema_name"] == "video-channel-manager.lordchrist-nonpublishing-semantic-revisions"
        and revisions["schema_version"] == 1
        and revisions["original_queue_sha256"] == queue_sha
        and revisions["editorial_approval"] is False
        and revisions["full_bilingual_review_complete"] is False
        and revisions["rights_review_complete"] is False
        and revisions["provider_write_authorization"] is False
        and revisions["protected_ledger_write_authorization"] is False
    ):
        raise ValueError("Semantic revision package is not safe, versioned, or queue bound")

    adjusted: set[int] = set()
    for revision in revisions["revisions"]:
        n = revision["sequence"]
        if n in adjusted or n not in (7, 25, 29):
            raise ValueError("Unknown or repeated semantic revision")
        adjusted.add(n)
        target = preview[n - 1]
        if (
            target["original_full_post_sha256"] != revision["original_full_post_sha256"]
            or target["publication_id"] != revision["original_publication_id"]
            or target["candidate_full_post_sha256"] != revision["expected_prior_preview_full_post_sha256"]
            or target["source"]["url"] != revision["source_url"]
            or revision["new_russian_body_sha256"] != _sha(revision["new_translation_ru"])
            or revision["final_editorial_approval"] is not False
        ):
            raise ValueError(f"Unsafe or stale source-bound semantic revision {n}")
        proof = revision["source_probe"]
        if not (
            proof["http_status"] == 200
            and proof["source_opening_exact"]
            and proof["source_closing_exact"]
            and proof["forward_order"]
            and proof["english_source_span_words"] > 100
            and proof["source_review_not_full_translation_certification"]
        ):
            raise ValueError(f"Missing source-context witness in semantic revision {n}")
        blocks = revision["new_translation_ru"].split("\n\n")
        if len(blocks) != revision["russian_paragraph_count"]:
            raise ValueError(f"Paragraph count discrepancy in revision {n}")
        target["text"] = _draft_render(
            revision["new_translation_ru"],
            target["source"]["author"],
            target["source"]["work"],
            _source_hashtags(original[n - 1]["text"]),
        )
        target["title"] = (
            chr(171) + revision["new_title_ru"] + chr(187) + " " + chr(8212) + " " + target["source"]["author"]
        )
        target["source"]["anchor_start"] = revision["new_source_anchor_start"]
        target["source"]["anchor_end"] = revision["new_source_anchor_end"]
        target["candidate_full_post_sha256"] = _sha(target["text"])
        target["semantic_revision_evidence_file"] = SEMANTIC_REVISIONS.relative_to(ROOT).as_posix()
        target["semantic_revision_status"] = "pending_independent_bilingual_and_rights_approval"
        target["semantic_revision_issue_resolved_in_draft"] = revision["issue_resolved"]
        if n == 29:
            target["preview_selection_change"] = "retained_source_replaced_by_context_complete_candidate"
            target["source"]["selection_policy"] = "new_source_contiguous_passage_proposed"
            target["source"]["primary_source_type"] = "historical_primary"
        if len(target["text"]) > 4096:
            raise ValueError(f"Revised preview card {n} exceeds Telegram text limit")
    if adjusted != {7, 25, 29}:
        raise ValueError("All three source corrections must be present")

    retained_review = _load(RETAINED_VERSE_REVIEW)
    if not (
        retained_review["schema_name"] == "video-channel-manager.lordchrist-nonpublishing-retained-verse-review"
        and retained_review["schema_version"] == 1
        and retained_review["original_queue_sha256"] == queue_sha
        and retained_review["editorial_approval"] is False
        and retained_review["full_bilingual_review_complete"] is False
        and retained_review["rights_review_complete"] is False
        and retained_review["provider_write_authorization"] is False
        and retained_review["protected_ledger_write_authorization"] is False
        and len(retained_review["revisions"]) == 1
    ):
        raise ValueError("Retained verse review is stale or would grant unsafe authority")

    retained_fix = retained_review["revisions"][0]
    if retained_fix["sequence"] != 30 or retained_fix["review_status"] != "proposed_only_not_source_fidelity_certified":
        raise ValueError("Unexpected or approved retained verse review")
    target = preview[29]
    if (
        retained_fix["original_publication_id"] != target["publication_id"]
        or retained_fix["original_full_post_sha256"] != target["original_full_post_sha256"]
        or retained_fix["expected_prior_preview_full_post_sha256"] != target["candidate_full_post_sha256"]
        or retained_fix["source_url"] != target["source"]["url"]
        or retained_fix["source_anchor_start"] != target["source"]["anchor_start"]
        or retained_fix["source_anchor_end"] != target["source"]["anchor_end"]
    ):
        raise ValueError("Retained verse amendment does not match exact old candidate")
    witness = retained_fix["source_probe"]
    if not (
        witness["http_status"] == 200
        and witness["source_opening_exact"]
        and witness["source_closing_exact"]
        and witness["forward_order"]
        and witness["source_explicit_22nd_verse"]
        and witness["full_translation_certified"] is False
    ):
        raise ValueError("Retained verse amendment lacks precise source witness")
    if len(retained_fix["corrections"]) != 2:
        raise ValueError("Exactly two source-grounded retained verse corrections required")
    for edit in retained_fix["corrections"]:
        if edit["field"] != "text":
            raise ValueError("Retained verse edits must affect the quote text only")
        _replace_exact(target, edit["field"], edit["exact_before"], edit["proposed_after"])
    if _sha(target["text"]) != retained_fix["candidate_full_post_sha256"]:
        raise ValueError("Retained verse amendment digest mismatch")
    target["candidate_full_post_sha256"] = _sha(target["text"])
    target["retained_verse_review_evidence_file"] = RETAINED_VERSE_REVIEW.relative_to(ROOT).as_posix()
    target["retained_verse_review_status"] = "pending_full_bilingual_and_rights_approval"
    if len(target["text"]) > 4096:
        raise ValueError("Retained verse amendment exceeds quote length")

    # Extend exact source boundaries only when the current, previous signed
    # source-bound review is byte-identical. These are not publisher releases.
    additional = _load(SPURGEON_OWEN_REVIEW)
    if not (
        additional["schema_name"] == "video-channel-manager.lordchrist-owen-spurgeon-source-contiguity-inert"
        and additional["schema_version"] == 1
        and additional["original_queue_sha256"] == queue_sha
        and additional["editorial_approval"] is False
        and additional["full_bilingual_review_complete"] is False
        and additional["rights_review_complete"] is False
        and additional["provider_write_authorization"] is False
        and additional["protected_ledger_write_authorization"] is False
        and additional["source_probe_not_full_translation_certification"] is True
    ):
        raise ValueError("Unapproved source-contiguity package missing or unsafe")
    rows = additional["revisions"]
    if not isinstance(rows, list) or [row["sequence"] for row in rows] != [3, 4]:
        raise ValueError("Expected exactly two source-contiguity corrections in order")
    for row in rows:
        sequence = row["sequence"]
        revised = preview[sequence - 1]
        if not (
            row["status"] == "proposal_not_approved"
            and row["original_publication_id"] == revised["publication_id"]
            and row["original_full_post_sha256"] == revised["original_full_post_sha256"]
            and row["expected_prior_preview_full_post_sha256"] == revised["candidate_full_post_sha256"]
            and row["source_url"] == revised["source"]["url"]
            and len(row["corrections"]) == 2
        ):
            raise ValueError(f"Stale, ambiguous or approved contiguity patch for {sequence}")
        witness = row["source_probe"]
        if not (
            witness["http_status"] == 200
            and witness["start_anchor_exact"]
            and witness["new_end_anchor_exact"]
            and witness["prior_end_anchor_exact"]
            and witness["forward_order"]
            and witness["prior_end_before_new_end"]
            and witness["full_bilingual_review_certified"] is False
            and witness["english_span_words"] > 200
        ):
            raise ValueError(f"Insufficient original-language source proof on {sequence}")
        if sequence == 4 and not (witness["owen_reason_intro_in_source"] and witness["owen_five_terms_in_source"]):
            raise ValueError("Missing evidence for Owen's two omitted clauses")
        expected_fields = ["source.anchor_end", "text"] if sequence == 3 else ["text", "text"]
        if [edit["field"] for edit in row["corrections"]] != expected_fields:
            raise ValueError("Unexpected contiguity patch fields")
        for edit in row["corrections"]:
            _replace_exact(revised, edit["field"], edit["exact_before"], edit["proposed_after"])
        if not (
            _sha(revised["text"]) == row["candidate_full_post_sha256"]
            and _sha(revised["source"]["anchor_end"]) == row["candidate_source_end_anchor_sha256"]
        ):
            raise ValueError(f"Post-patch exact SHA verification failed on {sequence}")
        revised["candidate_full_post_sha256"] = _sha(revised["text"])
        revised["source_contiguity_review_status"] = "pending_full_bilingual_rights_and_theological_review"
        revised["source_contiguity_review_evidence_file"] = SPURGEON_OWEN_REVIEW.relative_to(ROOT).as_posix()
        if len(revised["text"]) > 4096:
            raise ValueError(f"Contiguity patch {sequence} exceeds Telegram text envelope")
    line_edits_count = _apply_bound_line_edits(preview, queue_sha)
    return {
        "schema_name": SCHEMA,
        "schema_version": 1,
        "output_role": "editors_only_not_telegram_runtime_input",
        "observed_on": "2026-11-04",
        "original_release_id": "lordchrist-puritan-spurgeon-v4",
        "original_queue_sha256": queue_sha,
        "release_id": None,
        "release_digest": None,
        "editorial_approval": False,
        "provider_write_authorization": False,
        "protected_ledger_write_authorization": False,
        "full_bilingual_review_complete": False,
        "rights_review_complete": False,
        "drafted_count": 20,
        "conditionally_retained_count": 10,
        "semantic_revision_applied_count": 3,
        "retained_verse_amendment_count": 1,
        "source_contiguity_amendment_count": 2,
        "source_bound_line_edit_cards": line_edits_count,
        "effective_contiguous_draft_count": 21,
        "effective_retained_for_context_count": 9,
        "note": (
            "Candidate reading deck ONLY. These excerpts are NOT verified for every "
            "Russian phrase or cleared for publication. No existing queue, receipt "
            "or provider state is modified. This distinct schema is not recognized "
            "by publisher load paths."
        ),
        "posts": preview,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/check inert LordChrist editorial reading deck")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="Update docs/audits output only")
    group.add_argument("--check", action="store_true", help="Check exact tracked output without writing")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.write:
        OUTPUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"CREATED EDITORIAL-ONLY: {OUTPUT}")
        return 0
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
        print("Nonpublishing editorial preview differs; regenerate explicitly with --write")
        return 1
    print("Nonpublishing editorial preview exactly matches the 30-source evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
