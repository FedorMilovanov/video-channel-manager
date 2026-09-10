from __future__ import annotations

from video_channel_manager.telegram_historical_media_materialize_v2 import _PLANS, _plain_html, _purpose_for


def test_complete_v2_render_plan_is_exactly_sixteen_unique_assets() -> None:
    assert len(_PLANS) == 16
    assert len({plan.asset_id for plan in _PLANS}) == 16
    assert len({plan.output_file_name for plan in _PLANS}) == 16
    assert sum(plan.transform == "pdf_page" for plan in _PLANS) == 6
    assert sum(plan.transform == "identity_copy" for plan in _PLANS) == 8
    assert sum(plan.transform == "json_record_card" for plan in _PLANS) == 1
    assert sum(plan.transform == "epub_html_card" for plan in _PLANS) == 1


def test_complete_v2_render_plan_keeps_catalog_and_frus_semantically_distinct() -> None:
    by_id = {plan.asset_id: plan for plan in _PLANS}
    assert by_id["img-fuller-v3-taylor-wellcome-catalog"].exhibit_kind == "institutional_catalog_record"
    assert by_id["img-stam-v3-frus-1934-epub"].exhibit_kind == "official_document_excerpt"
    assert by_id["img-stam-v3-frus-1934-epub"].archive_member == "OEBPS/d381.html"


def test_plain_html_removes_markup_and_decodes_entities() -> None:
    assert _plain_html("<p>John &amp; Betty <strong>Stam</strong></p>") == "John & Betty Stam"


def test_catalog_and_official_excerpt_boundaries_are_not_facsimile_claims() -> None:
    catalog_purpose, catalog_boundary = _purpose_for("institutional_catalog_record")
    frus_purpose, frus_boundary = _purpose_for("official_document_excerpt")
    assert "catalogue record" in catalog_purpose
    assert "not a facsimile" in catalog_boundary
    assert "official diplomatic document" in frus_purpose
    assert "later biographical details" in frus_boundary
