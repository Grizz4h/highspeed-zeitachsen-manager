import streamlit as st
import subprocess
from pathlib import Path
import os

# -------------------------
# Streamlit config (MUSS früh)
# -------------------------
st.set_page_config(page_title="HIGHspeed Hub", layout="wide")

# -------------------------
# Helpers
# -------------------------
def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()

def sudo_journal(service: str) -> tuple[int, str]:
    return _run(["sudo", "-n", "/usr/bin/journalctl", "-u", service, "-n", "120", "--no-pager"])

# -------------------------
# Paths (Raspberry)
# -------------------------
PUBLISHER_DIR = Path("/opt/highspeed/publisher")
SCRIPT_PULL = PUBLISHER_DIR / "data_pull.sh"

SERVER_MODE = (os.name != "nt" and PUBLISHER_DIR.exists())

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown("## 🚀 Deploy")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("DEPLOY · Web jetzt", use_container_width=True):
            code, out = _run(["/bin/systemctl", "start", "highspeed-web-deploy.service"])
            st.success("OK" if code == 0 else "FAIL")
            if out:
                st.code(out)

    with c2:
        if st.button("DEPLOY · Toolbox jetzt", use_container_width=True):
            # FIX: richtiger Service!
            code, out = _run(["/bin/systemctl", "start", "highspeed-toolbox-deploy.service"])
            st.success("OK" if code == 0 else "FAIL")
            if out:
                st.code(out)

    st.divider()
    st.markdown("## 📦 Data Repo Pull (für Renderer)")

    if not SERVER_MODE:
        st.info("Data Pull nur auf dem Raspberry verfügbar.")
    else:
        if not SCRIPT_PULL.exists():
            st.error(f"data_pull.sh fehlt: {SCRIPT_PULL}")
        else:
            c3, c4 = st.columns(2)
            with c3:
                if st.button("⬇️ Pull Data (DEV)", use_container_width=True):
                    code, out = _run([str(SCRIPT_PULL), "dev"])
                    st.success("OK" if code == 0 else "FAIL")
                    if out:
                        st.code(out)

            with c4:
                if st.button("⬇️ Pull Data (MAIN)", use_container_width=True):
                    code, out = _run([str(SCRIPT_PULL), "main"])
                    st.success("OK" if code == 0 else "FAIL")
                    if out:
                        st.code(out)

    st.divider()
    st.markdown("## 🧾 Deploy-Logs")

    service = st.selectbox(
        "Service",
        [
            "highspeed-web-deploy.service",
            "highspeed-toolbox-deploy.service",
        ],
    )
    if st.button("Logs anzeigen", use_container_width=True):
        code, out = sudo_journal(service)
        if code == 0:
            st.code(out or "(leer)")
        else:
            st.error("FAIL (sudoers?)")
            if out:
                st.code(out)

# ============================================================
# Main
# ============================================================
st.title("🧰 HIGHspeed Hub")
st.caption("Tools: Zeitachse, ΔNET, … (links im Menü)")
