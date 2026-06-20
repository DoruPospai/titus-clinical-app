"""
inference.py — TITUS
Inlocuieste inferenta MLP cu TitusEngine (cr_lambdafix + w_matrix).
"""
from __future__ import annotations

from urllib.parse import quote_plus

import pandas as pd
import streamlit as st


def build_google_search_url(disease_name: object) -> str:
    q = str(disease_name or "").strip()
    if not q:
        return ""
    return f"https://www.google.com/search?q={quote_plus(q)}"


def ranking_to_df(ranking: list[dict]) -> pd.DataFrame:
    """Converteste lista de dict din diagnose() intr-un DataFrame afisabil."""
    if not ranking:
        return pd.DataFrame()
    rows = []
    for r in ranking:
        rows.append({
            "Rank"       : r["rank"],
            "Boala"      : r["name"],
            "CR"         : round(float(r["cr"]), 4),
            "Clasa"      : r["cr_class"],
            "CodeMaladie": r["code"],
            "Google"     : build_google_search_url(r["name"]),
        })
    return pd.DataFrame(rows)


def waiting_room_to_df(waiting_room: list[dict]) -> pd.DataFrame:
    """Converteste WaitingRoom intr-un DataFrame afisabil."""
    if not waiting_room:
        return pd.DataFrame()
    rows = []
    for w in waiting_room:
        rows.append({
            "Tip"        : "RARE" if w["rare"] else "COMMON",
            "Boala"      : w["name"],
            "CR"         : round(float(w["cr"]), 4),
            "Overlap"    : round(float(w["overlap"]), 4),
            "CodeMaladie": w["code"],
            "Google"     : build_google_search_url(w["name"]),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_name_catalogs_titus(
    symptomes_path: str,
    signe_path: str,
    catsympt_path: str,
    catsigne_path: str,
):
    """Re-exporta load_name_catalogs din loaders pentru compatibilitate."""
    from .loaders import load_name_catalogs
    return load_name_catalogs(symptomes_path, signe_path, catsympt_path, catsigne_path)
