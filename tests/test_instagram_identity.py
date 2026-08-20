from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from video_channel_manager.editorial.instagram_identity import (
    InstagramIdentityBindingError,
    build_instagram_project_binding,
)
from video_channel_manager.exchange.instagram_identity import (
    InstagramAccountObservation,
    InstagramProjectBindingRegistry,
)


DIGEST = "sha256:" + "a" * 64
NOW = datetime(2026, 8, 20, 0, 30, tzinfo=UTC)


def _instagram_login_observation(*, account_id: str = "123456789012345", username: str = "TheLegendaryPoOet"):
    return InstagramAccountObservation(
        login_mode="instagram_login",
        provider_host="graph.instagram.com",
        api_version="v23.0",
        instagram_professional_account_id=account_id,
        username_observed=username,
        account_type_observed="CREATOR",
        facebook_page_id=None,
        granted_scopes=("instagram_business_basic",),
        observed_at=NOW,
        raw_response_sha256=DIGEST,
    )


def test_instagram_login_identity_proof_does_not_require_facebook_page_or_publish_scope() -> None:
    observation = _instagram_login_observation()

    assert observation.instagram_professional_account_id == "123456789012345"
    assert observation.facebook_page_id is None
    assert observation.granted_scopes == ("instagram_business_basic",)
    assert observation.provider_writes_authorized is False


def test_instagram_login_rejects_wrong_host_or_missing_basic_scope() -> None:
    with pytest.raises(ValidationError, match="graph.instagram.com"):
        InstagramAccountObservation(
            login_mode="instagram_login",
            provider_host="graph.facebook.com",
            api_version="v23.0",
            instagram_professional_account_id="123456789012345",
            granted_scopes=("instagram_business_basic",),
            observed_at=NOW,
            raw_response_sha256=DIGEST,
        )

    with pytest.raises(ValidationError, match="instagram_business_basic"):
        InstagramAccountObservation(
            login_mode="instagram_login",
            provider_host="graph.instagram.com",
            api_version="v23.0",
            instagram_professional_account_id="123456789012345",
            granted_scopes=("instagram_business_content_publish",),
            observed_at=NOW,
            raw_response_sha256=DIGEST,
        )


def test_facebook_login_identity_proof_requires_linked_page_and_page_discovery_scope() -> None:
    observation = InstagramAccountObservation(
        login_mode="facebook_login",
        provider_host="graph.facebook.com",
        api_version="v23.0",
        instagram_professional_account_id="987654321098765",
        username_observed="lordgodstrength",
        account_type_observed="CREATOR",
        facebook_page_id="112233445566778",
        granted_scopes=("instagram_basic", "pages_show_list"),
        observed_at=NOW,
        raw_response_sha256=DIGEST,
    )

    assert observation.facebook_page_id == "112233445566778"

    with pytest.raises(ValidationError, match="linked Facebook Page ID"):
        InstagramAccountObservation(
            login_mode="facebook_login",
            provider_host="graph.facebook.com",
            api_version="v23.0",
            instagram_professional_account_id="987654321098765",
            facebook_page_id=None,
            granted_scopes=("instagram_basic", "pages_show_list"),
            observed_at=NOW,
            raw_response_sha256=DIGEST,
        )


def test_human_binding_uses_numeric_provider_id_not_username_as_identity() -> None:
    observation = _instagram_login_observation(username="TheLegendaryPoOet")
    binding = build_instagram_project_binding(
        observation,
        project_key="legendary-poet",
        observation_sha256=DIGEST,
        approved_at=NOW,
        approved_by="Fedor Milovanov",
    )

    assert binding.project_key == "legendary-poet"
    assert binding.instagram_professional_account_id == observation.instagram_professional_account_id
    assert binding.username_observed == "TheLegendaryPoOet"
    assert binding.provider_writes_authorized is False


def test_binding_rejects_unknown_project_and_registry_rejects_cross_project_provider_reuse() -> None:
    observation = _instagram_login_observation()
    with pytest.raises(InstagramIdentityBindingError, match="unknown canonical project_key"):
        build_instagram_project_binding(
            observation,
            project_key="legendary-poet-typo",
            observation_sha256=DIGEST,
            approved_at=NOW,
            approved_by="reviewer",
        )

    first = build_instagram_project_binding(
        observation,
        project_key="legendary-poet",
        observation_sha256=DIGEST,
        approved_at=NOW,
        approved_by="reviewer",
    )
    second = build_instagram_project_binding(
        observation,
        project_key="lord-god-strength",
        observation_sha256=DIGEST,
        approved_at=NOW,
        approved_by="reviewer",
    )
    with pytest.raises(ValidationError, match="cannot bind to multiple projects"):
        InstagramProjectBindingRegistry(bindings=(first, second))
