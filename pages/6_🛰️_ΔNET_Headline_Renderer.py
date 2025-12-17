# pages/6_🛰️_ΔNET_Headline_Renderer.py
from __future__ import annotations

from pathlib import Path
import streamlit as st

from tools.deltanet.headline import render_deltanet_headline, save_payload_json


st.set_page_config(page_title="ΔNET Headline Renderer", layout="wide")

st.title("🛰️ ΔNET — Headline Renderer")
st.caption("Authoring-Tool: Text rein, Bild raus. Kein PUX-Backend nötig.")

repo_root = Path(__file__).resolve().parents[1]
data_dir = repo_root / "data" / "deltanet"

with st.sidebar:
    st.subheader("Output")
    out_name = st.text_input("Dateiname (optional)", value="")
    save_json = st.checkbox("Payload zusätzlich als JSON speichern", value=True)

    st.divider()
    st.subheader("Defaults")
    default_delta_date = st.text_input("Default Δ-Datum", value="Δ2125-07-19")
    default_location = st.text_input("Default Location", value="SÜDPLATEAU")
    default_status = st.selectbox("Default Status", ["UNVERIFIED", "DEVELOPING", "CONFIRMED", "CRITICAL"], index=2)
    default_priority = st.selectbox("Default Priority", ["AMBER", "LOW", "HIGH"], index=1)

colA, colB = st.columns([1, 1], gap="large")

with colA:
    st.subheader("Eingaben")

    delta_date = st.text_input("Δ-Datum", value=default_delta_date)
    location = st.text_input("Ort / Sektor / Trasse", value=default_location)

    status = st.selectbox("STATUS", ["UNVERIFIED", "DEVELOPING", "CONFIRMED", "CRITICAL"], index=["UNVERIFIED","DEVELOPING","CONFIRMED","CRITICAL"].index(default_status))
    priority = st.selectbox("PRIORITY", ["AMBER", "LOW", "HIGH"], index=["AMBER","LOW","HIGH"].index(default_priority))

    headline = st.text_area(
        "Headline (Zeilenumbrüche erlaubt)",
        value="SPIELTAG 18 UNTERBROCHEN\nSIGNALVERLUST AUF WYND-45",
        height=120
    )

    subline = st.text_area(
        "Kurztext (optional)",
        value="Mehrere Datenfeeds brachen während der zweiten Phase ab. Eine Ursache wurde bislang nicht bestätigt.",
        height=90
    )

    source = st.text_input("Quelle (Footer)", value="ΔNet - Public Information Layer")

    payload = {
        "delta_date": delta_date.strip(),
        "location": location.strip(),
        "status": status.strip(),
        "priority": priority.strip(),
        "headline": headline.strip(),
        "subline": subline.strip(),
        "source": source.strip(),
    }

    st.divider()

    render_btn = st.button("Render PNG", type="primary", use_container_width=True)

with colB:
    st.subheader("Preview / Output")

    if render_btn:
        try:
            out = render_deltanet_headline(
                payload=payload,
                out_name=(out_name.strip() or None),
            )

            st.success(f"Gerendert: {out}")
            st.image(str(out), use_container_width=True)

            # Download
            png_bytes = out.read_bytes()
            st.download_button(
                "Download PNG",
                data=png_bytes,
                file_name=out.name,
                mime="image/png",
                use_container_width=True
            )

            # Optional: JSON speichern
            if save_json:
                jpath = save_payload_json(payload, data_dir=data_dir)
                st.info(f"JSON gespeichert: {jpath}")

        except Exception as e:
            st.error(str(e))
    else:
        st.info("Links Felder ausfüllen → Render PNG.")
