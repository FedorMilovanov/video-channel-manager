#!/usr/bin/env python3
"""Audit and schedule the guarded theological article wave."""

import lord_god_article_wave_v3.common as common_module  # noqa: F401
import lord_god_article_wave_v3.link_cards_parsed as link_cards_module
import lord_god_article_wave_v3.mutations as mutations_module  # noqa: F401
import lord_god_article_wave_v3.sources as sources_module  # noqa: F401
import lord_god_article_wave_v3.wall as wall_module  # noqa: F401
import lord_god_article_wave_v3.workflow as workflow_module  # noqa: F401
from lord_god_article_wave_v3.common import *  # noqa: F403
from lord_god_article_wave_v3.mutations import *  # noqa: F403
from lord_god_article_wave_v3.sources import *  # noqa: F403
from lord_god_article_wave_v3.wall import *  # noqa: F403
from lord_god_article_wave_v3.workflow import *  # noqa: F403

# Historical audit lineage retained in parsed-link v3:
# link_cards_hardened_entry as link_cards_module

if __name__ == "__main__":
    link_cards_module.guarded_main()
