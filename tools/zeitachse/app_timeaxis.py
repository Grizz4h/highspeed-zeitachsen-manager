import streamlit as st
import calendar
import json
from datetime import date, timedelta
from pathlib import Path

from .canon_time import load_config, allocate_inworld_date
from .state_store import load_state, save_state, delete_state, UIState
from .events_store import (
    load_events, save_events, add_event, delete_event,
    events_on, has_event_on
)


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "canon_time_config.json"


# -------------------------
# Helpers
# -------------------------
def write_season_start_into_config(config_path: Path, season: int, start_date: date) -> None:
    d = json.loads(config_path.read_text(encoding="utf-8"))
    if "season_start" not in d or not isinstance(d["season_start"], dict):
        d["season_start"] = {}
    d["season_start"][str(season)] = start_date.isoformat()
    config_path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def matchday_date(cfg, season: int, matchday: int) -> date:
    start = cfg.season_start.get(season)
    if not start:
        raise ValueError(f"Missing season_start for season {season}.")
    if matchday < 1:
        raise ValueError("matchday must be >= 1")
    return start + timedelta(days=(matchday - 1) * cfg.matchday_interval_days)


def md_for_date(cfg, season: int, d: date):
    start = cfg.season_start.get(season)
    if not start:
        return None
    diff = (d - start).days
    if diff < 0:
        return None
    if diff % cfg.matchday_interval_days != 0:
        return None
    return diff // cfg.matchday_interval_days + 1


def month_shift(y: int, m: int, delta: int):
    m2 = m + delta
    y2 = y
    while m2 < 1:
        m2 += 12
        y2 -= 1
    while m2 > 12:
        m2 -= 12
        y2 += 1
    return y2, m2


def ensure_calendar_matches_picked():
    d = st.session_state["picked_date"]
    st.session_state["cal_year"] = d.year
    st.session_state["cal_month"] = d.month


def render_clickable_month(cfg, season: int, year: int, month: int, events):
    """Clickable month grid: clicking a day sets session_state['picked_date']."""  # noqa
    cal = calendar.Calendar(firstweekday=0)  # Monday
    weeks = cal.monthdayscalendar(year, month)

    headers = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    hcols = st.columns(7)
    for i, h in enumerate(headers):
        hcols[i].markdown(f"**{h}**")

    picked = st.session_state["picked_date"]

    for w in weeks:
        cols = st.columns(7)
        for i, day in enumerate(w):
            if day == 0:
                cols[i].markdown("&nbsp;", unsafe_allow_html=True)
                continue

            d = date(year, month, day)
            md = md_for_date(cfg, season, d)
            dot = "•" if has_event_on(events, d) else ""

            if md is None:
                label = f"{day}{dot}"
            else:
                label = f"{day}{dot}\nMD{md}"

            # simple highlight indicator
            if d == picked:
                label = f"✅ {label}"

            if cols[i].button(label, key=f"cal_{year}_{month}_{day}"):
                st.session_state["picked_date"] = d
                ensure_calendar_matches_picked()
                st.rerun()


# -------------------------
# RENDER ENTRYPOINT (Hub-safe)
# -------------------------
def render():
    st.title("🕒 HIGHspeed Zeitachsen-Manager + Kalender")
    st.caption("Zeitachsen-Rechner (Matchday alle 3 Tage) + klickbarer Kalender + freie Einträge + Content-Drops.")

    # -------------------------
    # Load config
    # -------------------------
    try:
        cfg = load_config(CONFIG_PATH)
    except Exception as e:
        st.error(f"Config konnte nicht geladen werden: {e}")
        st.stop()

    available_seasons = sorted(cfg.season_start.keys())
    if not available_seasons:
        st.error("In deiner Config fehlt season_start komplett oder ist leer.")
        st.stop()

    # -------------------------
    # Load state + events
    # -------------------------
    if "ui_state" not in st.session_state:
        st.session_state["ui_state"] = load_state()
    if "events" not in st.session_state:
        st.session_state["events"] = load_events()

    state: UIState = st.session_state["ui_state"]
    events = st.session_state["events"]

    # -------------------------
    # Single source of truth: picked_date
    # -------------------------
    if "picked_date" not in st.session_state:
        try:
            st.session_state["picked_date"] = matchday_date(cfg, int(state.season), int(state.matchday))
        except Exception:
            st.session_state["picked_date"] = cfg.season_start[available_seasons[0]]

    # -------------------------
    # Calendar month state
    # -------------------------
    if "cal_year" not in st.session_state or "cal_month" not in st.session_state:
        ensure_calendar_matches_picked()

    # -------------------------
    # Sidebar controls
    # -------------------------
    with st.sidebar:
        st.subheader("Savegame")
        if st.button("💾 Stand speichern", key="btn_save_state"):
            save_state(state)
            st.success("Stand gespeichert.")
        if st.button("♻️ Stand zurücksetzen", key="btn_reset_state"):
            delete_state()
            st.session_state["ui_state"] = load_state()
            st.success("Zurückgesetzt.")
            st.rerun()

        st.divider()
        st.subheader("Events")
        if st.button("💾 Events speichern", key="btn_save_events"):
            save_events(events)
            st.success("Events gespeichert.")
        st.caption("Events liegen in `events.json`.")

    # -------------------------
    # Layout
    # -------------------------
    left, right = st.columns([1, 1.45], gap="large")

    # =========================
    # LEFT: Rechner + Content-Drop
    # =========================
    with left:
        st.subheader("⚙️ Zeitachsen-Rechner")

        season = st.selectbox(
            "Season",
            options=available_seasons,
            index=available_seasons.index(int(state.season)) if int(state.season) in available_seasons else 0
        )

        matchday = st.number_input("Matchday", min_value=1, step=1, value=int(state.matchday))

        content_type = st.selectbox(
            "Content-Typ",
            options=list(cfg.offset_rules.keys()),
            index=list(cfg.offset_rules.keys()).index(state.content_type) if state.content_type in cfg.offset_rules else 0
        )

        min_off, max_off = cfg.offset_rules[content_type]
        if min_off == max_off:
            offset = int(min_off)
            st.text_input("Offset (Tage)", value=str(offset), disabled=True)
        else:
            default_offset = int(state.offset)
            if default_offset < min_off or default_offset > max_off:
                default_offset = 0 if (0 >= min_off and 0 <= max_off) else int(min_off)
            offset = st.slider("Offset (Tage)", int(min_off), int(max_off), int(default_offset), step=1)

        allow_future = st.checkbox("Future Content erlauben (geplant)", value=bool(state.allow_future))

        # Preview
        try:
            base_md = matchday_date(cfg, int(season), int(matchday))
            computed = base_md + timedelta(days=int(offset))
            st.caption(
                f"MD{int(matchday)} = **{base_md.isoformat()}** ({base_md.strftime('%A')})\n\n"
                f"Content-Date (Offset {int(offset)}): **{computed.isoformat()}** ({computed.strftime('%A')})"
            )
        except Exception as e:
            st.error(str(e))

        colA, colB = st.columns(2)

        with colA:
            if st.button("📅 Berechnen", key="btn_calc"):
                try:
                    d = allocate_inworld_date(
                        cfg,
                        season=int(season),
                        matchday=int(matchday),
                        content_type=content_type,
                        offset_days=int(offset),
                        allow_future=bool(allow_future),
                    )
                    st.success(d.isoformat())

                    # save ui state
                    state.season = int(season)
                    state.matchday = int(matchday)
                    state.content_type = str(content_type)
                    state.offset = int(offset)
                    state.allow_future = bool(allow_future)
                    save_state(state)

                    # jump day selection to computed date
                    st.session_state["picked_date"] = d
                    ensure_calendar_matches_picked()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with colB:
            if st.button("➕ Content → Kalender", key="btn_add_content"):
                try:
                    d = allocate_inworld_date(
                        cfg,
                        season=int(season),
                        matchday=int(matchday),
                        content_type=content_type,
                        offset_days=int(offset),
                        allow_future=True,  # events dürfen geplant sein
                    )
                    title = f"{content_type.upper()} – S{int(season)} MD{int(matchday)} (off {int(offset)})"
                    meta = {
                        "season": int(season),
                        "matchday": int(matchday),
                        "content_type": content_type,
                        "offset": int(offset),
                    }
                    add_event(events, d=d, title=title, notes="", kind="content", meta=meta)
                    save_events(events)
                    st.success(f"Gespeichert: {d.isoformat()}")

                    st.session_state["picked_date"] = d
                    ensure_calendar_matches_picked()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        st.divider()
        st.subheader("➕ Season hinzufügen (optional)")
        with st.expander("Neue Season anlegen", expanded=False):
            new_season = st.number_input("Season Nummer", min_value=1, step=1, value=max(available_seasons) + 1)
            new_start = st.date_input(
                "Startdatum (Matchday 1)",
                value=cfg.season_start[available_seasons[0]],
                key="new_season_start"
            )
            if st.button("✅ Season speichern", key="btn_save_season"):
                write_season_start_into_config(CONFIG_PATH, int(new_season), new_start)
                st.success("Gespeichert. App lädt neu.")
                st.rerun()

        # live ui state (so save button sidebar always matches)
        state.season = int(season)
        state.matchday = int(matchday)
        state.content_type = str(content_type)
        state.offset = int(offset)
        state.allow_future = bool(allow_future)

    # =========================
    # RIGHT: Calendar + Day View + Free Entries
    # =========================
    with right:
        st.subheader("🗓️ Kalender")

        nav1, nav2, nav3, nav4 = st.columns([1, 1, 2, 1])
        with nav1:
            if st.button("◀︎ Monat", key="btn_prev_month"):
                y, m = month_shift(st.session_state["cal_year"], st.session_state["cal_month"], -1)
                st.session_state["cal_year"], st.session_state["cal_month"] = y, m
                st.rerun()

        with nav2:
            if st.button("Monat ▶︎", key="btn_next_month"):
                y, m = month_shift(st.session_state["cal_year"], st.session_state["cal_month"], +1)
                st.session_state["cal_year"], st.session_state["cal_month"] = y, m
                st.rerun()

        with nav3:
            st.markdown(f"**{st.session_state['cal_year']}-{st.session_state['cal_month']:02d}**")

        with nav4:
            if st.button("📍 zum ausgewählten Tag", key="btn_month_to_picked"):
                ensure_calendar_matches_picked()
                st.rerun()

        render_clickable_month(cfg, int(state.season), st.session_state["cal_year"], st.session_state["cal_month"], events)
        st.caption("✅ = ausgewählter Tag | `MDx` = Matchday (3-Tage-Takt) | `•` = Einträge vorhanden")

        st.divider()
        st.subheader("📝 Tagesansicht & Einträge")

        # Day navigation: ALWAYS changes picked_date
        dsel = st.session_state["picked_date"]
        dcol1, dcol2, dcol3, dcol4 = st.columns([1, 1.2, 3, 1])

        with dcol1:
            if st.button("◀︎ Tag", key="btn_prev_day"):
                st.session_state["picked_date"] = dsel - timedelta(days=1)
                ensure_calendar_matches_picked()
                st.rerun()

        with dcol2:
            if st.button("World Today", key="btn_world_today"):
                st.session_state["picked_date"] = cfg.world_today
                ensure_calendar_matches_picked()
                st.rerun()

        with dcol4:
            if st.button("Tag ▶︎", key="btn_next_day"):
                st.session_state["picked_date"] = dsel + timedelta(days=1)
                ensure_calendar_matches_picked()
                st.rerun()

        # Date picker bound directly to picked_date key (single source)
        st.date_input("Datum", key="picked_date")

        dsel = st.session_state["picked_date"]

        md = md_for_date(cfg, int(state.season), dsel)
        if md is None:
            st.info(f"{dsel.isoformat()} ({dsel.strftime('%A')}): Kein Matchday.")
        else:
            st.success(f"{dsel.isoformat()} ({dsel.strftime('%A')}): Matchday **MD{md}**")

        # Events list for the day
        todays = events_on(events, dsel)
        if todays:
            st.markdown("**Einträge:**")
            for ev in todays:
                with st.container(border=True):
                    st.write(f"**{ev.title}**  \n_{ev.kind}_  \n{ev.notes or ''}")
                    if ev.meta:
                        st.caption(f"meta: {ev.meta}")

                    if st.button("🗑️ Löschen", key=f"del_{ev.id}"):
                        delete_event(events, ev.id)
                        save_events(events)
                        st.rerun()
        else:
            st.write("Keine Einträge an diesem Tag.")

        st.divider()

        st.markdown("**➕ Freien Eintrag hinzufügen**")
        with st.form("free_event_form", clear_on_submit=True):
            free_title = st.text_input("Titel")
            free_notes = st.text_area("Notiz", height=90)
            submitted = st.form_submit_button("✅ Freien Eintrag speichern")

            if submitted:
                if not free_title.strip():
                    st.error("Titel fehlt.")
                else:
                    add_event(events, d=dsel, title=free_title, notes=free_notes, kind="free", meta=None)
                    save_events(events)
                    st.success("Gespeichert.")
                    st.rerun()


# Standalone run (optional)
if __name__ == "__main__":
    st.set_page_config(page_title="HIGHspeed – Zeitachsen Manager + Kalender", layout="wide")
    render()
