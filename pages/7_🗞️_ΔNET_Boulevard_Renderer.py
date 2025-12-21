from __future__ import annotations

from pathlib import Path
import streamlit as st

from tools.deltanet.boulevard import render_deltanet_boulevard, save_payload_json
from tools.deltanet.name_mapper import NameMapper


st.set_page_config(page_title="ΔNET Boulevard Renderer", layout="wide")
@st.cache_resource
def get_name_mapper() -> NameMapper:
    return NameMapper.from_repo_file()

st.title("🗞️ ΔNET — Boulevard Renderer")
st.markdown("### Player-Name Mapper")

mapper = get_name_mapper()
st.caption(f"Mapping geladen: {mapper.size()} Spieler")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    real_input = st.text_input("Echter Name (Telegram)", placeholder="z.B. Peter Abbandonato")
    if st.button("Fake-Namen finden", use_container_width=True):
        hit = mapper.lookup_fake(real_input)
        if hit.fake and hit.confidence >= 0.9:
            st.success(f"Fake: **{hit.fake}**")
        elif hit.fake:
            st.warning(f"Best guess: **{hit.fake}** (Confidence {hit.confidence:.2f})")
            if hit.suggestions:
                st.write("Vorschläge:")
                for r, f, score in hit.suggestions:
                    st.write(f"- {r} → **{f}** ({score:.2f})")
        else:
            st.error("Kein Treffer. Dann fehlt der Name im Mapping.")

with col2:
    raw = st.text_area(
        "Telegram-News reinkopieren (ersetzt alle echten Namen)",
        placeholder="Beispiel: Peter Abbandonato fällt verletzt aus ...",
        height=140
    )
    if st.button("Text ersetzen", use_container_width=True):
        replaced = mapper.replace_in_text(raw)
        st.text_area("Ergebnis (copy & paste)", value=replaced, height=140)

st.caption("Reißerisch, Social-first. Eigenes Template. Eigenes Layout. Kein System-Look.")

repo_root = Path(__file__).resolve().parents[1]
data_dir = repo_root / "data" / "deltanet" / "boulevard"

with st.sidebar:
    st.subheader("Output")
    out_name = st.text_input("Dateiname (optional)", value="")
    save_json = st.checkbox("Payload als JSON speichern", value=True)

colA, colB = st.columns([1, 1], gap="large")

with colA:
    st.subheader("Inputs")
    brand = st.text_input("Brand", value="ΔNET - Boulevard")
    kicker = st.text_input("Kicker", value="EXKLUSIV")
    heat = st.selectbox("Heat", ["HOT", "AMBER", "NEUTRAL"], index=0)

    headline = st.text_area(
        "Headline (kurz + brutal)",
        value="Martin hat einen kleinen Schnipel",
        height=120
    )
    bg = st.selectbox(
        "Boulevard Hintergrund",
        ["urban", "infra", "trash", "chaos", "lifestyle", "sportnews"],
        index=0,
    )

    teaser = st.text_area(
        "Teaser (1–3 Zeilen, nicht Roman)",
        value="Augenzeugen sprechen von einem nahezu lächerlich kleinen Penis. \n\n" 
        "Experten sind ratlos.",
        height=100
    )

    delta_date = st.text_input("Δ-Datum", value="Δ2125-07-19")
    location = st.text_input("Ort / Sektor", value="IRIS · GLASS QUAY")

    desk = st.text_input("Watermark / Desk", value="ΔNet · Satirische Parallelmeldungen aus dem HIGHspeed-Universum.")

    payload = {
        "brand": brand,
        "kicker": kicker,
        "heat": heat,
        "headline": headline,
        "teaser": teaser,
        "delta_date": delta_date,
        "location": location,
        "desk": desk,
        "bg": bg,  # <— DAS fehlt
    }

    render_btn = st.button("Render PNG", type="primary", use_container_width=True)

with colB:
    st.subheader("Preview / Output")
    if render_btn:
        try:
            out = render_deltanet_boulevard(payload, out_name=(out_name.strip() or None))
            st.success(f"Gerendert: {out}")
            st.image(str(out), use_container_width=True)

            st.download_button(
                "Download PNG",
                data=out.read_bytes(),
                file_name=out.name,
                mime="image/png",
                use_container_width=True
            )

            if save_json:
                jpath = save_payload_json(payload, data_dir=data_dir)
                st.info(f"JSON gespeichert: {jpath}")

        except Exception as e:
            st.error(str(e))
    else:
        st.info("Links füllen → Render PNG.")
