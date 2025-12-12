import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
STATE_PATH = BASE_DIR / "ui_state.json"

@dataclass
class UIState:
    season: int = 1
    matchday: int = 1
    content_type: str = "news"
    offset: int = 0
    allow_future: bool = False

def load_state() -> UIState:
    if not STATE_PATH.exists():
        return UIState()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return UIState(
            season=int(data.get("season", 1)),
            matchday=int(data.get("matchday", 1)),
            content_type=str(data.get("content_type", "news")),
            offset=int(data.get("offset", 0)),
            allow_future=bool(data.get("allow_future", False)),
        )
    except Exception:
        # Wenn die Datei kaputt ist: nicht sterben, einfach Defaults
        return UIState()

def save_state(state: UIState) -> None:
    STATE_PATH.write_text(
        json.dumps(asdict(state), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def delete_state() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()
