# NOSO_loader.py
# Strat de izolare între platforma TITUS și motorul NOSO (Titus_inference.py)
#
# Platformă nu apelează niciodată direct Titus_inference.py.
# Toate apelurile trec prin acest modul.
# Dacă motorul se redenumește sau se schimbă, se modifică DOAR acest fișier.

import importlib.util
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Configurare căi (modifică aici dacă redenumești fișierele) ───────────────
NOSO_ENGINE_FILE  = "Titus_inference.py"
NOSO_TABEL2_FILE  = "Tabel2_Titus_NumeElement.xlsx"
NOSO_TABEL2_SHEET = "Tabel2"
NOSO_MAL_FILE     = "Maladies.xlsx"
NOSO_SYM_FILE     = "Symptomes.xlsx"
NOSO_SIG_FILE     = "Signe.xlsx"
NOSO_RF_FILE      = "Riskf.xlsx"


def _base_dir(root_hint: str = "") -> Path:
    """Directorul rădăcină al aplicației."""
    if root_hint:
        return Path(root_hint)
    return Path(__file__).resolve().parent.parent


# ── Fix sheet name ────────────────────────────────────────────────────────────
def _fix_sheet(path: str) -> None:
    """Corectează automat sheet name Sheet1 → Tabel2."""
    try:
        xl = pd.ExcelFile(path)
        if NOSO_TABEL2_SHEET not in xl.sheet_names and xl.sheet_names:
            from openpyxl import load_workbook
            wb = load_workbook(path)
            wb[xl.sheet_names[0]].title = NOSO_TABEL2_SHEET
            wb.save(path)
            wb.close()
    except Exception:
        pass


# ── Încărcare motor ───────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Incarcare motor NOSO...")
def load_engine(root: str = "", _mtime: float = 0.0) -> object:
    """
    Încarcă și returnează instanța TitusEngine.
    _mtime: mtime-ul Tabel2 — cache invalidat automat la orice modificare.
    Folosește st.cache_resource — un singur motor per sesiune.
    """
    base     = _base_dir(root)
    tabel2   = str(base / NOSO_TABEL2_FILE)
    eng_path = base / NOSO_ENGINE_FILE

    if not eng_path.exists():
        raise FileNotFoundError(
            f"Motor NOSO negăsit: {eng_path}\n"
            f"Verificați că {NOSO_ENGINE_FILE} se află în {base}"
        )

    _fix_sheet(tabel2)

    mod_key = f"NOSO_engine_{int(time.time() * 1000)}"
    spec    = importlib.util.spec_from_file_location(mod_key, eng_path)
    mod     = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TitusEngine()


# ── Cataloage ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_catalogs(root: str = "") -> dict:
    """
    Încarcă cataloagele NOSO din cache-ul central (resources.py).
    Interfața publică e identică — niciun apelant (NOSO_collect.py,
    NOSO_ranking.py, NOSO_review.py) nu necesită modificări.

    Returnează dict cu:
      mal_map  : {code_int → NomMaladie}
      mal_women_map : {code_int → Women value}
      sym_map  : {code_int → NomSymptome}
      sig_map  : {code_int → NomSigne}
      rf_map   : {code_int → NomRiskFactor}
      sym_df   : DataFrame complet Symptomes
      sig_df   : DataFrame complet Signe
      rf_df    : DataFrame complet Riskf
    """
    from .resources import get_resources
    res = get_resources()

    return {
        "mal_map":        res["mal_map"],
        "mal_women_map":  res["mal_women_map"],
        "sym_map":        res["sym_map"],
        "sig_map":        res["sig_map"],
        "rf_map":         res["rf_map"],
        "sym_df":         res["sym_df"],
        "sig_df":         res["sig_df"],
        "rf_df":          res["rf_df"],
    }


# ── API public ────────────────────────────────────────────────────────────────
def diagnose(elements: list, top_n: int = 10,
             cr_threshold: float = 0.20, root: str = "") -> dict:
    """
    Apelează motorul NOSO cu lista de elemente a pacientului.

    Args:
        elements:     [(code_int, nature_str, score_int), ...]
        top_n:        număr maxim de boli în ranking
        cr_threshold: prag minim CR
        root:         directorul rădăcină (opțional)

    Returns:
        {"ranking": [...], "waiting_room": [...]}
    """
    import os
    base = _base_dir(root)
    _t2_mtime = (base / NOSO_TABEL2_FILE).stat().st_mtime         if (base / NOSO_TABEL2_FILE).exists() else 0.0
    engine = load_engine(root, _mtime=_t2_mtime)
    return engine.diagnose(elements, top_n=top_n, cr_threshold=cr_threshold)


def get_disease_name(code: int, root: str = "") -> str:
    """Returnează numele bolii după cod."""
    cats = load_catalogs(root)
    return cats["mal_map"].get(code, f"Boala {code}")


def get_element_name(code: int, nature: str, root: str = "") -> str:
    """Returnează numele unui element (simptom/semn/RF) după cod și natură."""
    cats = load_catalogs(root)
    if nature == "Sympt":
        return cats["sym_map"].get(code, f"Sympt {code}")
    if nature == "Signe":
        return cats["sig_map"].get(code, f"Signe {code}")
    if nature == "RiskF":
        return cats["rf_map"].get(code, f"RiskF {code}")
    return f"{nature} {code}"


def search_elements(query: str, nature: str = "all",
                    root: str = "") -> list[dict]:
    """
    Caută elemente după text în cataloage.

    Args:
        query:  textul de căutat (case-insensitive)
        nature: "Sympt" | "Signe" | "RiskF" | "all"
        root:   directorul rădăcină

    Returns:
        [{"code": int, "nature": str, "name": str}, ...]
    """
    cats    = load_catalogs(root)
    q       = query.lower().strip()
    results = []

    sources = []
    if nature in ("Sympt", "all"):
        sources.append(("Sympt", cats["sym_map"]))
    if nature in ("Signe", "all"):
        sources.append(("Signe", cats["sig_map"]))
    if nature in ("RiskF", "all"):
        sources.append(("RiskF", cats["rf_map"]))

    for nat, mapping in sources:
        for code, name in mapping.items():
            if q in name.lower():
                results.append({"code": code, "nature": nat, "name": name})

    results.sort(key=lambda x: x["name"])
    return results