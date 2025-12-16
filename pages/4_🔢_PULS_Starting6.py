import json
from pathlib import Path
import re
import streamlit as st

from tools.puls_renderer import (
    list_matchups_from_matchday_json,
    extract_starting6_for_matchup,
)

# optional: wenn du später den echten PNG-Renderer einbaust
try:
    from tools.puls_renderer import render_starting6_from_files
    HAS_RENDER = True
except Exception:
    HAS_RENDER = False


st.set_page_config(page_title="Starting6 Renderer", layout="wide")
st.title("🏒 Starting6 Renderer")
st.caption("Lädt Matchups + Starting6 aus Matchday-JSON + Lineups-JSON.")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

matchday_files = sorted(DATA_DIR.glob("spieltag_[0-9][0-9].json"))
lineup_files = sorted(DATA_DIR.glob("spieltag_[0-9][0-9]_lineups.json"))

if not matchday_files or not lineup_files:
    st.error("Keine JSONs gefunden in /data. Erwartet z.B. spieltag_04.json und spieltag_04_lineups.json")
    st.stop()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_spieltag_number(filename: str) -> int | None:
    m = re.search(r"spieltag_(\d+)", filename)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _home_away(m):
    # erlaubt: (home, away) ODER {"home":..., "away":...}
    if isinstance(m, (list, tuple)) and len(m) >= 2:
        return str(m[0]), str(m[1])
    if isinstance(m, dict):
        return str(m.get("home", "")), str(m.get("away", ""))
    return "", ""


# --- Auswahl ---
col1, col2 = st.columns(2)
with col1:
    matchday_path: Path = st.selectbox("Matchday JSON", matchday_files, format_func=lambda p: p.name)

with col2:
    # default: lineup passend zum spieltag vorauswählen (falls vorhanden)
    md_no = _extract_spieltag_number(matchday_path.name)
    default_idx = 0
    if md_no is not None:
        wanted = f"spieltag_{md_no:02d}_lineups.json"
        for i, p in enumerate(lineup_files):
            if p.name == wanted:
                default_idx = i
                break

    lineup_path: Path = st.selectbox(
        "Lineups JSON",
        lineup_files,
        index=default_idx,
        format_func=lambda p: p.name,
    )

# --- JSON laden ---
try:
    matchday_data = _load_json(matchday_path)
except Exception as e:
    st.error(f"Matchday JSON kaputt: {matchday_path.name}")
    st.exception(e)
    st.stop()

try:
    lineups_data = _load_json(lineup_path)
except Exception as e:
    st.error(f"Lineups JSON kaputt: {lineup_path.name}")
    st.exception(e)
    st.stop()

# --- Matchups extrahieren ---
matchups = list_matchups_from_matchday_json(matchday_data)
if not matchups:
    st.error("Keine Matchups aus Matchday JSON extrahiert. (Check: matchday['results'] muss home/away enthalten)")
    st.write("Debug: matchday keys =", list(matchday_data.keys()))
    st.stop()

# --- Top-Game auswählen ---
sel = st.selectbox(
    "Top-Game auswählen",
    matchups,
    format_func=lambda m: f"{_home_away(m)[0].upper()} vs {_home_away(m)[1].upper()}",
)

home_team, away_team = _home_away(sel)

if not home_team or not away_team:
    st.error("Matchup-Format unbekannt. Debug-Ausgabe unten.")
    st.write("matchups[0] type:", type(matchups[0]).__name__)
    st.json(matchups[:3])
    st.stop()

# --- Starting6 extrahieren ---
try:
    starting6 = extract_starting6_for_matchup(lineups_data, home_team, away_team)
except Exception as e:
    st.error(
        "Starting6 konnte nicht extrahiert werden.\n\n"
        "Sehr wahrscheinlich stimmen die Team-Namen aus der Matchday-JSON nicht exakt mit den Keys in "
        "lineups_json['teams'] überein."
    )
    st.write("Debug: home_team =", home_team)
    st.write("Debug: away_team =", away_team)

    teams = (lineups_data.get("teams") or {})
    if isinstance(teams, dict):
        st.write("Debug: verfügbare teams keys (Auszug):", list(teams.keys())[:25])

    st.exception(e)
    st.stop()

# --- Anzeige ---
with st.expander("Starting6 (Debug)", expanded=False):
    st.json(starting6)


# --- Render Button (optional) ---
st.divider()
st.subheader("PNG rendern (optional)")

if not HAS_RENDER:
    st.info("Renderer-Funktion render_starting6_from_files ist (noch) nicht importierbar. Debug läuft aber.")
else:
    template_name = st.text_input("Template-Datei in assets/templates", value="starting6v1.png")
    out_name_default = f"starting6_{home_team.replace(' ', '-')}_vs_{away_team.replace(' ', '-')}.png"
    out_name = st.text_input("Output-Dateiname", value=out_name_default)

    if st.button("Render Starting6 PNG", type="primary"):
        try:
            out_path = render_starting6_from_files(
                matchday_json_path=matchday_path,
                lineups_json_path=lineup_path,
                home_team=home_team,
                away_team=away_team,
                template_name=template_name,
                out_name=out_name,
            )
            out_path = Path(out_path)
            st.success(f"Gerendert: {out_path.name}")

            img_bytes = out_path.read_bytes()

            with st.expander("Vorschau", expanded=True):
                st.image(img_bytes, caption=out_path.name, width=520)

            st.download_button(
                "PNG herunterladen",
                data=img_bytes,
                file_name=out_path.name,
                mime="image/png",
            )

        except Exception as e:
            st.error("Render fehlgeschlagen.")
            st.exception(e)

