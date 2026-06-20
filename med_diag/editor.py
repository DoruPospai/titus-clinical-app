import re
from typing import Dict, List

import pandas as pd
import streamlit as st

def parse_code_block(raw_text: str, nature: str, default_weight: int = 150) -> List[Dict[str, object]]:
    items = []
    if not raw_text.strip():
        return items

    chunks = re.split(r"[,\n;]+", raw_text.strip())
    for chunk in chunks:
        c = chunk.strip()
        if not c:
            continue

        weight = default_weight
        if "=" in c:
            left, right = c.split("=", 1)
            code = int(left.strip())
            weight = int(float(right.strip()))
        elif ":" in c:
            left, right = c.split(":", 1)
            code = int(left.strip())
            weight = int(float(right.strip()))
        else:
            code = int(c.strip())

        items.append(
            {
                "Key": f"{nature}:{int(code):04d}",
                "Nature": nature,
                "Code": int(code),
                "Label": "",
                "Weight": int(weight),
                "Source": "codes",
            }
        )
    return items

def rows_to_editor_df(rows: List[Dict[str, object]], catalog_df: pd.DataFrame) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["Key", "Nature", "Code", "Label", "Weight", "Source"])

    out = pd.DataFrame(rows).copy()
    if "Label" not in out.columns:
        out["Label"] = ""

    lookup = catalog_df.set_index("Key")["DisplayName"].to_dict()

    def _resolve_label(r) -> str:
        existing = str(r.get("Label", "")).strip()
        if existing:
            return existing
        # Incearca key exact
        v = lookup.get(str(r.get("Key", "")), "")
        if v:
            return v
        # Incearca cu zero-padding (Sympt:2 → Sympt:0002)
        try:
            nat  = str(r.get("Nature", "")).strip()
            code = int(r.get("Code", 0))
            v = lookup.get(f"{nat}:{code:04d}", "")
            if v:
                return v
        except Exception:
            pass
        return ""

    out["Label"] = out.apply(_resolve_label, axis=1)
    out = out[["Key", "Nature", "Code", "Label", "Weight", "Source"]].drop_duplicates("Key").reset_index(drop=True)
    return out

def set_editor_from_rows(rows: List[Dict[str, object]], catalog_df: pd.DataFrame):
    st.session_state["editor_rows"] = rows_to_editor_df(rows, catalog_df).to_dict(orient="records")

def _normalize_key(row: dict) -> str:
    """Normalizează Key la formatul Sympt:0002 (4 cifre)."""
    key = str(row.get("Key", "")).strip()
    if ":" in key:
        nat, cod = key.split(":", 1)
        try:
            return f"{nat.strip()}:{int(cod.strip()):04d}"
        except ValueError:
            pass
    return key


def append_editor_rows(rows: List[Dict[str, object]], catalog_df: pd.DataFrame):
    # Normalizeaza Key-urile inainte de merge
    for r in rows:
        r["Key"] = _normalize_key(r)
    current = pd.DataFrame(st.session_state.get("editor_rows", []))
    new_df = rows_to_editor_df(rows, catalog_df)
    merged = pd.concat([current, new_df], ignore_index=True) if not current.empty else new_df
    merged = merged.drop_duplicates("Key", keep="last").reset_index(drop=True)
    st.session_state["editor_rows"] = merged.to_dict(orient="records")

def get_editor_df() -> pd.DataFrame:
    rows = st.session_state.get("editor_rows", [])
    if not rows:
        return pd.DataFrame(columns=["Key", "Nature", "Code", "Label", "Weight", "Source"])
    return pd.DataFrame(rows)

def editor_df_to_patient_map(df: pd.DataFrame) -> Dict[str, float]:
    out = {}
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        key = str(row["Key"]).strip()
        try:
            weight = float(row["Weight"])
        except Exception:
            continue
        if key:
            out[key] = weight
    return out