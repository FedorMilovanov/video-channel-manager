from __future__ import annotations

import pytest
from pydantic import ValidationError

from video_channel_manager.wave_engine import ProjectBinding


def test_project_binding_rejects_wrong_owner_for_registered_project() -> None:
    with pytest.raises(ValidationError, match="identity is inconsistent"):
        ProjectBinding(
            project_key="legendary-poet",
            community_id=235216998,
            owner_id=-60805374,
        )
