import streamlit as st
from pathlib import Path

from tools.puls_renderer import render_from_json_file

st.set_page_config(page_title="PULS Renderer", layout="centered")

st.title("🏒 PULS – Spieltags-Renderer")
st.caption("JSON rein → Spieltagsübersicht PNG raus. Δ-Datum kommt aus UI (nicht aus JSON).")

BASE_DIR = Path(__file__).resolve().parent.parent  # Projektroot (app.py liegt dort)
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

st.divider()

st.subheader("1) JSON wählen")
uploaded = st.file_uploader("JSON hochladen", type=["json"])
local_files = sorted(DATA_DIR.glob("*.json"))

choice = None
if local_files:
    choice = st.selectbox("…oder eine JSON aus /data auswählen", ["—"] + [p.name for p in local_files])

json_path = None

if uploaded is not None:
    target = DATA_DIR / uploaded.name
    target.write_bytes(uploaded.getvalue())
    json_path = target
    st.success(f"Gespeichert: data/{uploaded.name}")
elif choice and choice != "—":
    json_path = DATA_DIR / choice

st.divider()

st.subheader("2) Δ-Datum setzen")
st.caption("Gib nur '2125-10-18' ein. Das Δ setzt der Renderer automatisch davor.")
delta_date_input = st.text_input("Δ-Datum", value="2125-10-18", help="Format: 2125-10-18 (ohne Δ).")

enable_vs = st.toggle("Renderer soll 'VS' in die Mitte schreiben (sonst frei lassen)", value=False)
enable_team_fx = st.toggle("Teamnamen mit FX (Stroke/Shadow)", value=True)


st.divider()

if json_path:
    st.subheader("3) Rendern")
    if st.button("Render Spieltagsübersicht", type="primary"):
        try:
            out_path = render_from_json_file(
            json_path=json_path,
            enable_draw_vs=enable_vs,
            delta_date=delta_date_input,
            enable_fx_on_teams=enable_team_fx,
            header_fx="ice_noise",
        )
            st.success(f"Gerendert: {Path(out_path).name}")

            img_bytes = Path(out_path).read_bytes()
            st.image(img_bytes, caption=Path(out_path).name, use_container_width=True)
            st.download_button(
                "PNG herunterladen",
                data=img_bytes,
                file_name=Path(out_path).name,
                mime="image/png",
            )

        except Exception as e:
            st.error(f"Render fehlgeschlagen: {e}")
else:
    st.info("Wähle oder lade eine JSON-Datei, dann kannst du rendern.")
