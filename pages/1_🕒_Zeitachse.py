import streamlit as st

st.set_page_config(page_title="🕒 Zeitachse", layout="wide")

from tools.zeitachse import app_timeaxis

app_timeaxis.render()
