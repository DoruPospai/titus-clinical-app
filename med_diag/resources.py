"""
resources.py — TITUS
Cache manager centralizat pentru toate resursele grele ale platformei.

Principiu: @st.cache_resource încarcă fiecare resursă O SINGURĂ DATĂ
per sesiune server, indiferent de câți utilizatori sau câte reruns.

Utilizare în orice modul:
    from .resources import get_resources
    res = get_resources()
    lexicon_df  = res["lexicon_df"]
    engine      = res["engine"]
    matcher     = res["matcher"]
    ...

Reset complet (buton UI):
    st.cache_resource.clear()
"""

import importlib.util
import logging
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from .config import (
    DEFAULT_ROOT,
    DEFAULT_TABEL2,
    DEFAULT_MALADIES,
    DEFAULT_SYMPTOMES,
    DEFAULT_SIGNE,
    DEFAULT_RISKF,
    DEFAULT_CATRISKF,
    DEFAULT_CATSYMPT,
    DEFAULT_CATSIGNE,
)

logger = logging.getLogger(__name__)

# ── Fișiere motor NOSO ────────────────────────────────────────────────────────
_NOSO_ENGINE_FILE  = "Titus_inference.py"
_NOSO_TABEL2_FILE  = "Tabel2_Titus_NumeElement.xlsx"
_NOSO_TABEL2_SHEET = "Tabel2"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers interne
# ─────────────────────────────────────────────────────────────────────────────

def _fix_sheet(path: Path) -> None:
    """Corectează sheet name Sheet1 → Tabel2 dacă e necesar."""
    try:
        xl = pd.ExcelFile(str(path))
        if _NOSO_TABEL2_SHEET not in xl.sheet_names and xl.sheet_names:
            from openpyxl import load_workbook
            wb = load_workbook(str(path))
            wb[xl.sheet_names[0]].title = _NOSO_TABEL2_SHEET
            wb.save(str(path))
            wb.close()
    except Exception:
        pass


def _load_map(df: pd.DataFrame, code_col: str, name_col: str) -> dict:
    """Construiește dict {code_int → name_str} dintr-un DataFrame."""
    out = {}
    for _, row in df.iterrows():
        code_str = str(row.get(code_col, "")).strip()
        if code_str.isdigit():
            out[int(code_str)] = str(row.get(name_col, "")).strip()
    return out


def _load_category_map(path: Path) -> dict:
    """Dict {code_int → category_name} din fișiere cat*.xlsx."""
    if not path or not path.exists():
        return {}
    df = pd.read_excel(str(path))
    code_col = next(
        (c for c in df.columns if str(c).lower() in
         {"codecategorie", "categorycode", "code"}), None
    )
    name_col = next(
        (c for c in df.columns if str(c).lower() in
         {"nomcategorie", "categoryname", "categorie", "category", "nume categorie"}), None
    )
    if not code_col or not name_col:
        return {}
    out = {}
    for _, row in df.iterrows():
        try:
            code = int(float(row[code_col]))
        except Exception:
            continue
        name = str(row[name_col]).strip()
        if name:
            out[code] = name
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Cache manager principal
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="TITUS — inițializare resurse...")
def get_resources() -> dict:
    """
    Încarcă toate resursele grele o singură dată per sesiune server.

    Returnează dict cu:
        lexicon_df    : DataFrame Lexicon (ClinicalPipeline)
        matcher       : SemanticMatcher (sau None dacă indisponibil)
        engine        : TitusEngine (motorul NOSO)
        mal_df        : DataFrame Maladies
        sym_df        : DataFrame Symptomes
        sig_df        : DataFrame Signe
        rf_df         : DataFrame Riskf
        mal_map       : {code → NomMaladie}
        mal_women_map : {code → Women value}
        sym_map       : {code → NomSymptome}
        sig_map       : {code → NomSigne}
        rf_map        : {code → NomRiskFactor}
        cat_sym_map   : {code → categorie simptom}
        cat_sig_map   : {code → categorie semn}
        cat_rf_map    : {code → categorie RF}
    """
    res = {}

    # ── 1. Lexicon ────────────────────────────────────────────────────────────
    wb_path = DEFAULT_ROOT / "ClinicalPipeline_RO_SINGLE_v14_RUNTIME_AUDIT.xlsx"
    if wb_path.exists():
        logger.info("TITUS resources: incarc Lexicon...")
        res["lexicon_df"] = pd.read_excel(str(wb_path), sheet_name="Lexicon")
    else:
        logger.warning(f"TITUS resources: Workbook lipsă — {wb_path}")
        res["lexicon_df"] = pd.DataFrame()

    # ── 2. SemanticMatcher ────────────────────────────────────────────────────
    try:
        from .semantic_layer import SemanticMatcher
        from .narrative_engine import init_engine
        logger.info("TITUS resources: inițializez SemanticMatcher...")
        matcher = SemanticMatcher(wb_path, res["lexicon_df"])
        init_engine(lexicon_df=res["lexicon_df"], semantic_matcher=matcher)
        res["matcher"] = matcher
    except Exception as exc:
        logger.warning(f"TITUS resources: SemanticMatcher indisponibil — {exc}")
        res["matcher"] = None

    # ── 3. Cataloage Excel ────────────────────────────────────────────────────
    logger.info("TITUS resources: incarc cataloage Excel...")

    def _read(path: Path) -> pd.DataFrame:
        if path and path.exists():
            return pd.read_excel(str(path), dtype=str).fillna("")
        return pd.DataFrame()

    res["mal_df"] = _read(DEFAULT_MALADIES)
    res["sym_df"] = _read(DEFAULT_SYMPTOMES)
    res["sig_df"] = _read(DEFAULT_SIGNE)
    res["rf_df"]  = _read(DEFAULT_RISKF)

    # ── 4. Lookup maps ────────────────────────────────────────────────────────
    res["mal_map"] = _load_map(res["mal_df"], "CodeMaladie",  "NomMaladie")
    res["sym_map"] = _load_map(res["sym_df"], "CodeSymptome", "NomSymptome")
    res["sig_map"] = _load_map(res["sig_df"], "CodeSigne",    "NomSigne")
    res["rf_map"]  = _load_map(res["rf_df"],  "CodeFactor",   "NomRiskFactor")

    # Women map pentru filtrul de sex din NOSO_context
    res["mal_women_map"] = {}
    if not res["mal_df"].empty and "Women" in res["mal_df"].columns:
        for _, r in res["mal_df"].iterrows():
            code_str = str(r.get("CodeMaladie", "")).strip()
            if code_str.isdigit():
                w = str(r.get("Women", "")).strip()
                if w and w != "nan":
                    try:
                        res["mal_women_map"][int(code_str)] = int(float(w))
                    except Exception:
                        pass

    # ── 5. Category maps ──────────────────────────────────────────────────────
    res["cat_sym_map"] = _load_category_map(DEFAULT_CATSYMPT)
    res["cat_sig_map"] = _load_category_map(DEFAULT_CATSIGNE)
    res["cat_rf_map"]  = _load_category_map(DEFAULT_CATRISKF)

    # ── 6. Motor NOSO ─────────────────────────────────────────────────────────
    tabel2_path = DEFAULT_ROOT / _NOSO_TABEL2_FILE
    eng_path    = DEFAULT_ROOT / _NOSO_ENGINE_FILE

    if eng_path.exists():
        logger.info("TITUS resources: incarc TitusEngine...")
        try:
            _fix_sheet(tabel2_path)
            mod_key = f"NOSO_engine_{int(time.time() * 1000)}"
            spec    = importlib.util.spec_from_file_location(mod_key, eng_path)
            mod     = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            res["engine"] = mod.TitusEngine()
        except Exception as exc:
            logger.warning(f"TITUS resources: TitusEngine indisponibil — {exc}")
            res["engine"] = None
    else:
        logger.warning(f"TITUS resources: motor NOSO lipsă — {eng_path}")
        res["engine"] = None

    logger.info("TITUS resources: inițializare completă.")
    return res
