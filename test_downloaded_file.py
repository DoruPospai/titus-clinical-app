"""
test_downloaded_file.py — verifică ce conține efectiv Symptomes.xlsx
DUPĂ descărcarea de pe Drive, pe containerul Streamlit Cloud.
Rulează ca aplicație separată (sau temporar înlocuiește app.py).
"""
import streamlit as st
import pandas as pd
from pathlib import Path

st.title("Test conținut fișier descărcat")

if "gdrive" not in st.secrets:
    st.error("Secțiunea [gdrive] nu există în secrets.")
    st.stop()

from med_diag.drive_sync import download_all
from med_diag.config import DEFAULT_ROOT, DEFAULT_SYMPTOMES

st.write("Rulez download_all()...")
status = download_all(DEFAULT_ROOT)
st.json(status)

st.divider()
st.write("Calea fișierului local:", str(DEFAULT_SYMPTOMES))
st.write("Fișierul există local?", DEFAULT_SYMPTOMES.exists())

if DEFAULT_SYMPTOMES.exists():
    size_kb = DEFAULT_SYMPTOMES.stat().st_size / 1024
    st.write(f"Dimensiune fișier local: {size_kb:.2f} KB")

    try:
        df = pd.read_excel(str(DEFAULT_SYMPTOMES))
        st.write("Coloane găsite:", list(df.columns))
        st.write("Număr rânduri:", len(df))
        st.dataframe(df.head(5))
    except Exception as exc:
        st.error(f"Eroare la citire: {exc}")
