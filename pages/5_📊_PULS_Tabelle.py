import streamlit as st
from pathlib import Path
import glob

from tools.puls_renderer import render_table_from_matchday_json

st.title("📊 PULS Tabellen-Renderer")

# --- File discovery (robust) ---
def find_matchday_files() -> list[Path]:
    patterns = [
        "data/spieltag_*.json",
        "data/**/spieltag_*.json",
    ]
    found: list[Path] = []
    for p in patterns:
        for f in glob.glob(p, recursive=True):
            found.append(Path(f))
    # uniq + sort
    uniq = sorted({str(p): p for p in found}.values(), key=lambda x: str(x))
    return uniq

files = find_matchday_files()

if not files:
    st.warning("Keine spieltag_*.json gefunden. Lege sie unter /data ab (oder Unterordner).")
    st.stop()

labels = [str(p).replace("\\", "/") for p in files]
selected_label = st.selectbox("Spieltag JSON auswählen", labels, index=min(0, len(labels)-1))
selected_file = Path(selected_label)

delta_date = st.text_input("Δ-Datum (z.B. 2125-10-18)", value="2125-10-18")

template_name = st.text_input("Template (assets/templates)", value="league_table_v1.png")

if st.button("Rendern"):
    try:
        out = render_table_from_matchday_json(
            matchday_json_path=selected_file,
            template_name=template_name,
            delta_date=delta_date,
        )
        st.success(f"OK: {out}")
        st.image(str(out))

        # Download
        png_bytes = Path(out).read_bytes()
        st.download_button(
            "PNG herunterladen",
            data=png_bytes,
            file_name=Path(out).name,
            mime="image/png",
        )
    except Exception as e:
        st.error(str(e))
