from __future__ import annotations
from typing import Any, Dict, List, Tuple


def list_matchups_from_matchday_json(matchday: Dict[str, Any]) -> List[Tuple[str, str]]:
    results = matchday.get("results", [])
    out: List[Tuple[str, str]] = []
    for r in results:
        home = r.get("home")
        away = r.get("away")
        if home and away:
            out.append((home, away))
    return out
