from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union


JsonLike = Union[Dict[str, Any], Path, str]


def _load_json(x: JsonLike) -> Dict[str, Any]:
    """Accept dict OR path OR path-string and return dict."""
    if isinstance(x, dict):
        return x
    p = Path(x)  # works for Path and str
    return json.loads(p.read_text(encoding="utf-8"))


def list_matchups_from_matchday_json(matchday: JsonLike) -> List[Dict[str, str]]:
    """
    Returns [{"home": "<slug>", "away": "<slug>"} , ...]
    Works with matchday json that contains either:
      - "results": [{home, away}, ...]  (generator output)
      - OR "nord"/"sued": [{home, away}, ...] (your overview format)
    """
    data = _load_json(matchday)

    out: List[Dict[str, str]] = []

    # generator style
    results = data.get("results")
    if isinstance(results, list):
        for r in results:
            home = (r or {}).get("home")
            away = (r or {}).get("away")
            if home and away:
                out.append({"home": str(home), "away": str(away)})
        return out

    # matchday overview style
    nord = data.get("nord", [])
    sued = data.get("sued", [])
    for r in (nord + sued):
        home = (r or {}).get("home")
        away = (r or {}).get("away")
        if home and away:
            out.append({"home": str(home), "away": str(away)})

    return out


def extract_starting6_for_team(lineups_json: dict, team_name: str) -> dict:
    teams = lineups_json.get("teams", {})
    if team_name not in teams:
        raise KeyError(f"Team '{team_name}' not found in lineups_json['teams'].")

    t = teams[team_name]

    forwards = (((t.get("forwards") or {}).get("line1")) or [])
    defense = (((t.get("defense") or {}).get("pair1")) or [])
    goalie = t.get("goalie") or {}

    # robust: Typen absichern
    if not isinstance(forwards, list):
        forwards = []
    if not isinstance(defense, list):
        defense = []
    if not isinstance(goalie, dict):
        goalie = {}

    # NICHT stringifyen – wir behalten dicts!
    forwards = forwards[:3]
    defense = defense[:2]

    return {"forwards": forwards, "defense": defense, "goalie": goalie}



def extract_starting6_for_matchup(
    lineups_json: JsonLike,
    home_name: str,
    away_name: str,
) -> Dict[str, Any]:
    """
    Returns both teams starting6 in one object.
    """
    home = extract_starting6_for_team(lineups_json, home_name)
    away = extract_starting6_for_team(lineups_json, away_name)

    return {
        "home": {"team": home_name, **home},
        "away": {"team": away_name, **away},
    }
