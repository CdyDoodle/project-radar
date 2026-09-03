"""Source registry. Importing the modules registers them."""
from radar.sources.base import all_source_names, enabled_sources, register  # noqa: F401
from radar.sources import github, community  # noqa: F401,E402

__all__ = ["enabled_sources", "all_source_names", "register"]
