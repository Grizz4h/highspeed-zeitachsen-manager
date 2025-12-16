# tools/puls_renderer/__init__.py

# Public API: Matchday
from .renderer import (
    render_from_json_file,
    render_matchday_overview,
)

# Public API: Starting 6
from .starting6_renderer import (
    render_starting6_from_files,
)

# Public API: League table
from .league_table_renderer import (
    render_table_from_matchday_json,          # preferred public name
    render_league_table_from_matchday_json,   # keep for backwards compatibility / internal use
)

# Layout / helpers you actually reuse from pages/tools
from .layout_config import (
    MatchdayLayoutV1,
)

from .lineup_adapter import (
    extract_starting6_for_matchup,
)

from .tools_starting6 import (
    list_matchups_from_matchday_json,
)

__all__ = [
    # Matchday
    "render_from_json_file",
    "render_matchday_overview",

    # Starting 6
    "render_starting6_from_files",

    # League table
    "render_table_from_matchday_json",
    "render_league_table_from_matchday_json",

    # Layout / helpers
    "MatchdayLayoutV1",
    "extract_starting6_for_matchup",
    "list_matchups_from_matchday_json",
]
