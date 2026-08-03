#!/usr/bin/env python3
"""Audit and schedule the guarded theological article photo wave."""

from typing import TYPE_CHECKING

import lord_god_article_wave_v3.common as common_module  # noqa: F401
import lord_god_article_wave_v3.mutations as mutations_module  # noqa: F401
import lord_god_article_wave_v3.photo_wave_v5 as photo_wave_module
import lord_god_article_wave_v3.sources as sources_module  # noqa: F401
import lord_god_article_wave_v3.wall as wall_module  # noqa: F401
import lord_god_article_wave_v3.workflow as workflow_module  # noqa: F401
from lord_god_article_wave_v3.common import *  # noqa: F403
from lord_god_article_wave_v3.mutations import *  # noqa: F403
from lord_god_article_wave_v3.photo_wave_v5 import *  # noqa: F403
from lord_god_article_wave_v3.sources import *  # noqa: F403
from lord_god_article_wave_v3.wall import *  # noqa: F403

if TYPE_CHECKING:
    # Retired runtime markers retained only for migration regression tests:
    # photo_wave_v4 as photo_wave_module
    # link_cards_module.guarded_main()
    from lord_god_article_wave_v3 import (  # noqa: F401
        link_cards_parsed as link_cards_module,
    )


if __name__ == "__main__":
    photo_wave_module.guarded_main()
