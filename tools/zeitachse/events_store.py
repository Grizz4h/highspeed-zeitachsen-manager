import json
import uuid
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
EVENTS_PATH = BASE_DIR / "events.json"

@dataclass
class CalendarEvent:
    id: str
    date: str            # ISO yyyy-mm-dd
    title: str
    notes: str = ""
    kind: str = "free"   # "free" | "content"
    meta: Optional[Dict[str, Any]] = None

def load_events() -> List[CalendarEvent]:
    if not EVENTS_PATH.exists():
        return []
    try:
        raw = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
        out: List[CalendarEvent] = []
        for r in raw:
            out.append(CalendarEvent(
                id=str(r.get("id") or uuid.uuid4().hex),
                date=str(r["date"]),
                title=str(r["title"]),
                notes=str(r.get("notes", "")),
                kind=str(r.get("kind", "free")),
                meta=r.get("meta"),
            ))
        return out
    except Exception:
        return []

def save_events(events: List[CalendarEvent]) -> None:
    EVENTS_PATH.write_text(
        json.dumps([asdict(e) for e in events], indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def add_event(events: List[CalendarEvent], *, d: date, title: str, notes: str, kind: str, meta=None) -> CalendarEvent:
    ev = CalendarEvent(
        id=uuid.uuid4().hex,
        date=d.isoformat(),
        title=title.strip(),
        notes=notes.strip(),
        kind=kind,
        meta=meta,
    )
    events.append(ev)
    return ev

def delete_event(events: List[CalendarEvent], event_id: str) -> None:
    events[:] = [e for e in events if e.id != event_id]

def events_on(events: List[CalendarEvent], d: date) -> List[CalendarEvent]:
    iso = d.isoformat()
    return [e for e in events if e.date == iso]

def has_event_on(events: List[CalendarEvent], d: date) -> bool:
    iso = d.isoformat()
    return any(e.date == iso for e in events)
