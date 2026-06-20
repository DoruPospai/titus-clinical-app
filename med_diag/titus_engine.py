"""
titus_engine.py
Wrapper Streamlit pentru TitusEngine din Titus_inference.py.
Foloseste st.cache_resource pentru a incarca motorul o singura data.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import streamlit as st


# ---------------------------------------------------------------------------
# Incarcare TitusEngine din directorul radacina al proiectului
# ---------------------------------------------------------------------------

def _import_engine(tabel2_path: str, w_matrix_path: str, raritate_path: str):
    """
    Incarca TitusEngine direct de pe disk cu importlib.util.
    Bypaseaza complet sys.modules si pyc cache — intotdeauna versiunea curenta.
    """
    import importlib.util

    # Cauta Titus_inference.py in directorul radacina al proiectului
    search_dirs = [
        Path(tabel2_path).parent.parent,  # data_clean -> root
        Path(".").resolve(),
    ]

    py_path = None
    for d in search_dirs:
        candidate = d / "Titus_inference.py"
        if candidate.exists():
            py_path = candidate
            break

    if py_path is None:
        raise ImportError(
            f"Titus_inference.py nu a fost gasit in: "
            f"{[str(d) for d in search_dirs]}"
        )

    # Incarca modulul direct de pe disk (bypaseaza orice cache)
    import sys as _sys
    # Folosim un key unic la fiecare apel pentru a evita orice cache de modul
    import time as _time
    mod_key = f"Titus_inference_{int(_time.time()*1000)}"
    spec = importlib.util.spec_from_file_location(mod_key, py_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Salveaza calea si versiunea pe clasa incarcata
    cls = mod.TitusEngine
    cls._loaded_from = str(py_path)
    cls._module_version = getattr(mod, "TITUS_VERSION", "ABSENT")
    return cls


def _ensure_tabel2_sheet(tabel2_path: str) -> None:
    """
    Dacă fișierul Tabel2 nu are sheet-ul 'Tabel2' (ex. are 'Sheet1'),
    îl redenumește automat — in-place, transparent pentru TitusEngine.
    """
    import pandas as pd
    from openpyxl import load_workbook

    try:
        xl = pd.ExcelFile(tabel2_path)
        sheets = xl.sheet_names
        if "Tabel2" in sheets:
            return  # deja corect
        # Primul sheet disponibil → redenumit 'Tabel2'
        first = sheets[0]
        wb = load_workbook(tabel2_path)
        ws = wb[first]
        ws.title = "Tabel2"
        wb.save(tabel2_path)
        wb.close()
    except Exception:
        pass  # dacă nu reușim, lăsăm TitusEngine să dea eroarea originală


@st.cache_resource(show_spinner="Incarcare motor TITUS...")
def get_engine(tabel2_path: str, w_matrix_path: str, raritate_path: str):
    """
    Incarca si cacheaza TitusEngine.
    Foloseste importlib.util pentru a citi intotdeauna de pe disk.
    """
    _ensure_tabel2_sheet(tabel2_path)
    EngineClass = _import_engine(tabel2_path, w_matrix_path, raritate_path)
    engine = EngineClass()
    return engine


# ---------------------------------------------------------------------------
# Convertor format editor → format TITUS
# ---------------------------------------------------------------------------

def patient_map_to_titus(patient_map: dict) -> list[tuple[int, str, int]]:
    """
    Converteste formatul editor {"Sympt:13": 150, "Signe:401": 50}
    in formatul TITUS [(13, "Sympt", 150), (401, "Signe", 50)].
    """
    elements = []
    for key, weight in patient_map.items():
        if ":" not in str(key):
            continue
        nature, code_str = str(key).split(":", 1)
        nature = nature.strip().capitalize()
        if nature not in ("Sympt", "Signe", "Riskf"):
            continue
        if nature == "Riskf": nature = "RiskF"  # normalizeaza
        try:
            code   = int(code_str.strip())
            weight = int(float(weight))
            elements.append((code, nature, weight))
        except (ValueError, TypeError):
            continue
    return elements


def titus_to_patient_dict(elements: list[tuple[int, str, int]]) -> dict:
    """Converteste lista TITUS inapoi in dict intern {(code,nature): score}."""
    return {(int(ce), nat): int(sc) for ce, nat, sc in elements}
