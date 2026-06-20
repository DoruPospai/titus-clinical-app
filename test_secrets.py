"""
test_secrets.py — verificare rapidă dacă secrets.toml e citit corect.
Rulează acest fișier separat cu: streamlit run test_secrets.py
(NU din Spyder direct — st.secrets necesită contextul Streamlit runtime)
"""
import streamlit as st

st.write("Chei disponibile în st.secrets:", list(st.secrets.keys()))

if "gdrive" in st.secrets:
    st.success("Secțiunea [gdrive] a fost găsită!")
    st.write("folder_id:", st.secrets["gdrive"].get("folder_id", "LIPSEȘTE"))
    st.write("Chei service_account:", list(st.secrets["gdrive"].get("service_account", {}).keys()))
else:
    st.error("Secțiunea [gdrive] NU a fost găsită în secrets.toml")
    st.info("Verifică: D:\\MULTIMI_VAGI1\\Test11\\Test11_Final_OK\\.streamlit\\secrets.toml")
