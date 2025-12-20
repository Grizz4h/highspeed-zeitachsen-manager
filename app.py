import streamlit as st
import subprocess
import streamlit as st

def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()

def sudo_systemctl(args: list[str]) -> tuple[int, str]:
    return _run(["sudo", "-n", "/bin/systemctl", *args])

def sudo_journal(service: str) -> tuple[int, str]:
    return _run(["sudo", "-n", "/usr/bin/journalctl", "-u", service, "-n", "120", "--no-pager"])

with st.sidebar:
    st.markdown("## 🚀 Deploy (Web + Toolbox)")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("DEPLOY · Web jetzt", use_container_width=True):
            code, out = sudo_systemctl(["start", "highspeed-web-deploy.service"])
            st.success("OK" if code == 0 else "FAIL")
            if out: st.code(out)

    with c2:
        if st.button("DEPLOY · Toolbox jetzt", use_container_width=True):
            code, out = sudo_systemctl(["start", "highspeed-toolbox-deploy.service"])
            st.success("OK" if code == 0 else "FAIL")
            if out: st.code(out)

    st.markdown("## 🧾 Deploy-Logs")
    service = st.selectbox(
        "Service",
        ["highspeed-web-deploy.service", "highspeed-toolbox-deploy.service"],
    )
    if st.button("Logs anzeigen", use_container_width=True):
        code, out = sudo_journal(service)
        if code == 0:
            st.code(out or "(leer)")
        else:
            st.error("FAIL (sudoers?)")
            if out: st.code(out)


st.set_page_config(page_title="HIGHspeed Hub", layout="wide")
st.title("🧰 HIGHspeed Hub")
st.caption("Tools: Zeitachse, ΔNET, … (links im Menü)")
