"""
loaders.py — TITUS
Pastreaza incarcarea cataloagelor de simptome/semne.
Sursa de date: resources.py (cache central) — elimina dublarea I/O
cu NOSO_loader.py care citea aceleasi fisiere Excel independent.
"""
from pathlib import Path
from typing import Dict, Tuple

import os
import pandas as pd
import streamlit as st

from .config import SEMIO_TYPES
from .utils import normalize_nature, normalize_text


@st.cache_data(show_spinner=False)
def load_category_map(path: str, _mtime: float = 0.0) -> Dict[int, str]:
    """
    Pastrat pentru compatibilitate — folosit independent in alte module
    (ex: daca se adauga cataloage noi care nu trec prin resources.py).
    """
    if not path or not Path(path).exists():
        return {}
    df = pd.read_excel(path)
    code_col = next(
        (c for c in df.columns
         if str(c).lower() in {"codecategorie", "categorycode", "code"}),
        None
    )
    name_col = next(
        (c for c in df.columns
         if str(c).lower() in {"nomcategorie", "categoryname", "categorie", "category",
                                "nume categorie"}),
        None
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


@st.cache_data(show_spinner=False)
def load_name_catalogs(
    symptomes_path: str,
    signe_path: str,
    catsympt_path: str,
    catsigne_path: str,
    _mtime: float = 0.0,  # pastrat in semnatura pentru compatibilitate cu app_main.py
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Construieste cataloagele UI (Sympt + Signe) din resursele centrale
    (resources.py), nu din pd.read_excel direct.

    Parametrii de path raman in semnatura pentru compatibilitate cu
    apelul existent din app_main.py — dar nu mai sunt folositi pentru
    citire; sursa efectiva e get_resources().
    """
    from .resources import get_resources
    res = get_resources()

    sym = res["sym_df"]
    sig = res["sig_df"]
    cat_sym_map = res["cat_sym_map"]
    cat_sig_map = res["cat_sig_map"]

    for req, source, df_check in [
        (["CodeSymptome", "NomSymptome"], "Symptomes.xlsx", sym),
        (["CodeSigne",    "NomSigne"],    "Signe.xlsx",     sig),
    ]:
        missing = [c for c in req if c not in df_check.columns]
        if missing:
            raise ValueError(f"{source} lipsesc coloane: {missing}")

    rows = []

    for _, row in sym.iterrows():
        code = row.get("CodeSymptome")
        name = row.get("NomSymptome")
        if pd.isna(code) or pd.isna(name) or str(code).strip() == "":
            continue
        code    = int(float(code))
        display = str(name).strip()
        syns    = str(row.get("Synonimes", "")).strip() if "Synonimes" in sym.columns and pd.notna(row.get("Synonimes")) else ""
        desc_ro = str(row.get("Descriere_RO", "")).strip() if "Descriere_RO" in sym.columns and pd.notna(row.get("Descriere_RO")) else ""
        desc_en = str(row.get("Description_EN", "")).strip() if "Description_EN" in sym.columns and pd.notna(row.get("Description_EN")) else ""
        cat_int = int(float(row["CodeCategorie"])) if "CodeCategorie" in sym.columns and pd.notna(row.get("CodeCategorie")) and str(row.get("CodeCategorie")).strip() != "" else None
        cat_lbl = cat_sym_map.get(cat_int, f"Category {cat_int}" if cat_int else "Uncategorized")
        part = str(row.get("Particularites","")).strip() if "Particularites" in sym.columns and pd.notna(row.get("Particularites")) else "-"
        amin = row.get("Agemin") if "Agemin" in sym.columns else None
        amax = row.get("Agemax") if "Agemax" in sym.columns else None
        display_label = desc_ro if (desc_ro and len(desc_ro) <= 45) else display
        rows.append({
            "Key": f"Sympt:{code:04d}", "Nature": "Sympt", "Code": code,
            "DisplayName": display_label, "CategoryCode": cat_int, "CategoryLabel": cat_lbl,
            "Synonyms": syns, "DescriptionRO": desc_ro, "DescriptionEN": desc_en,
            "SearchableNorm": normalize_text(" | ".join([display, syns, desc_ro, desc_en])),
            "Particularites": part, "Agemin": amin, "Agemax": amax,
        })

    for _, row in sig.iterrows():
        code = row.get("CodeSigne")
        name = row.get("NomSigne")
        if pd.isna(code) or pd.isna(name) or str(code).strip() == "":
            continue
        code    = int(float(code))
        display = str(name).strip()
        syns    = ""
        if "Synonimes" in sig.columns and pd.notna(row.get("Synonimes")):
            syns = str(row["Synonimes"]).strip()
        elif "SYNONYMOUS_CLEAN" in sig.columns and pd.notna(row.get("SYNONYMOUS_CLEAN")):
            syns = str(row["SYNONYMOUS_CLEAN"]).strip()
        desc_ro = str(row.get("Descriere_RO", "")).strip() if "Descriere_RO" in sig.columns and pd.notna(row.get("Descriere_RO")) else ""
        desc_en = str(row.get("Description_EN", "")).strip() if "Description_EN" in sig.columns and pd.notna(row.get("Description_EN")) else ""
        cat_int = int(float(row["CodeCategorie"])) if "CodeCategorie" in sig.columns and pd.notna(row.get("CodeCategorie")) and str(row.get("CodeCategorie")).strip() != "" else None
        cat_lbl = cat_sig_map.get(cat_int, f"Category {cat_int}" if cat_int else "Uncategorized")
        part = str(row.get("Particularites","")).strip() if "Particularites" in sig.columns and pd.notna(row.get("Particularites")) else "-"
        amin = row.get("Agemin") if "Agemin" in sig.columns else None
        amax = row.get("Agemax") if "Agemax" in sig.columns else None
        rows.append({
            "Key": f"Signe:{code:04d}", "Nature": "Signe", "Code": code,
            "DisplayName": display, "CategoryCode": cat_int, "CategoryLabel": cat_lbl,
            "Synonyms": syns, "DescriptionRO": desc_ro, "DescriptionEN": desc_en,
            "SearchableNorm": normalize_text(" | ".join([display, syns, desc_ro, desc_en])),
            "Particularites": part, "Agemin": amin, "Agemax": amax,
        })

    catalog = pd.DataFrame(rows)
    if catalog.empty:
        raise ValueError("Niciun rand utilizabil in Symptomes.xlsx / Signe.xlsx.")

    sympt_catalog = catalog[catalog["Nature"] == "Sympt"].copy()
    signe_catalog = catalog[catalog["Nature"] == "Signe"].copy()
    return catalog, sympt_catalog, signe_catalog


@st.cache_data(show_spinner=False)
def load_riskf_catalog(
    riskf_path: str,
    catriskf_path: str,
    _mtime: float = 0.0,  # pastrat in semnatura pentru compatibilitate cu app_main.py
) -> pd.DataFrame:
    """
    Construieste catalogul Risk Factors din resursele centrale (resources.py).
    Parametrii de path raman pentru compatibilitate cu apelul existent.
    """
    from .resources import get_resources
    res = get_resources()

    df = res["rf_df"]
    cat_map = res["cat_rf_map"]

    rows = []
    for _, row in df.iterrows():
        code = row.get("CodeFactor")
        name = row.get("NomRiskFactor")
        if pd.isna(code) or pd.isna(name) or str(code).strip() == "":
            continue
        code    = int(float(code))
        display = str(name).strip()
        syns    = ""
        for syn_col in ("SYNONYMOUS_CLEAN", "Synonimes", "Synonyms"):
            if syn_col in df.columns and pd.notna(row.get(syn_col)):
                syns = str(row[syn_col]).strip()
                break
        desc_ro = str(row.get("DescriereRO_CLEAN", row.get("Descriere.RO", ""))).strip() if pd.notna(row.get("DescriereRO_CLEAN", row.get("Descriere.RO",""))) else ""
        desc_en = str(row.get("Description_EN_CLEAN", row.get("Description_EN", ""))).strip() if pd.notna(row.get("Description_EN_CLEAN", row.get("Description_EN",""))) else ""
        cat_int = int(float(row["CodeCategorie"])) if "CodeCategorie" in df.columns and pd.notna(row.get("CodeCategorie")) and str(row.get("CodeCategorie")).strip() != "" else None
        cat_lbl = cat_map.get(cat_int, f"Category {cat_int}" if cat_int else "Uncategorized")
        part    = str(row.get("Sex", "")).strip() if pd.notna(row.get("Sex","")) else "-"
        amin    = row.get("agemin") if "agemin" in df.columns else None
        amax    = row.get("agemax") if "agemax" in df.columns else None
        preg    = str(row.get("PREGNANCY", "")).strip() if pd.notna(row.get("PREGNANCY","")) else "-"
        rows.append({
            "Key"           : f"RiskF:{code:04d}",
            "Nature"        : "RiskF",
            "Code"          : code,
            "DisplayName"   : display,
            "CategoryCode"  : cat_int,
            "CategoryLabel" : cat_lbl,
            "Synonyms"      : syns,
            "DescriptionRO" : desc_ro,
            "DescriptionEN" : desc_en,
            "SearchableNorm": normalize_text(" | ".join([display, syns, desc_ro, desc_en])),
            "Particularites": part,
            "Agemin"        : amin,
            "Agemax"        : amax,
            "PREGNANCY"     : preg,
        })

    if not rows:
        raise ValueError("Niciun rand utilizabil in Riskf.xlsx.")
    return pd.DataFrame(rows)
