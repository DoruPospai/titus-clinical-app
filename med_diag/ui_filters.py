"""
ui_filters.py — TITUS
Aplica regulile F1-F11 pe cataloagele de simptome/semne inainte de afisare in UI.

Reguli per catalog:
  Sympt : F1 (Masked=23), F6, F7, F8, F11
  Signe : F2 (Masked=23), F7, F10, F11
  RiskF : F3 (Masked=23, Ethnics=7, LivingIn=9), F4 (ObGyn=5 pt Male),
          F5 (Profession=11 pt varsta<216), F9
          → Risk Factors nu sunt inca in UI, rezervat pentru extensie

F12 (distributie normala varsta) — filtru de ranking, nu UI.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st

MASKED_CATEGORY_CODE     = 23
RISKF_MASKED_CODE        = 23
RISKF_ETHNICS_CODE       = 7
RISKF_LIVING_IN_CODE     = 9
RISKF_OB_GYN_CODE        = 5
RISKF_PROFESSION_CODE    = 11
MIN_AGE_PROFESSION_MONTHS= 216

HIDDEN_SYMPT_FEMALE_PREGNANT = {171, 346, 415, 174, 189}
HIDDEN_SYMPT_FEMALE = {52}

_S1, _S2, _S3, _S4, _S5 = 952, 44, 1479, 1195, 1353
HIDDEN_SIGNS_BY_WEEKS = [
    (0,  12,   {_S1, _S2, _S3, _S4, _S5}),
    (13, 16,   {_S1, _S2, _S4, _S5}),
    (17, 20,   {_S1, _S4, _S5}),
    (21, None, {_S1}),
]

def _is_female(gender): return str(gender or "").strip().lower().startswith("f")
def _is_pregnant(p): return _is_female(p.get("gender","")) and str(p.get("pregnancy","No")).strip()=="Yes"
def _weeks(p): return int(p.get("weeks_pregnant") or 0)
def _hidden_signs_for_weeks(w):
    for wmin,wmax,h in HIDDEN_SIGNS_BY_WEEKS:
        if w>=wmin and (wmax is None or w<=wmax): return h
    return set()
def _cat_col(df):
    for c in ("CategoryCode","categorycode","CodeCategorie"):
        if c in df.columns: return c
def _part_col(df):
    for c in ("Particularites","particularites","Particularite","Sex"):
        if c in df.columns: return c


# ── Cheia de cache derivată din profil ───────────────────────────────────────
# @st.cache_data nu acceptă dict ca argument — serializăm profilul ca tuple
# cu câmpurile relevante pentru filtrare (nu user_id, nu dob).

def _profile_key(profile: dict) -> tuple:
    return (
        str(profile.get("gender", "Female")),
        int(profile.get("age_in_months", 0) or 0),
        str(profile.get("pregnancy", "No")),
        int(profile.get("weeks_pregnant") or 0),
    )


@st.cache_data(show_spinner=False)
def apply_ui_filters(catalog_df: pd.DataFrame, nature: str, _profile_key: tuple) -> pd.DataFrame:
    """
    nature = "Sympt" | "Signe" | "RiskF"
    _profile_key: tuple (gender, age_months, pregnancy, weeks) — cheie de cache.
    Cache invalidat automat când se schimbă catalogul sau profilul.
    """
    gender, age_months, pregnancy_str, weeks_val = _profile_key
    is_female = gender.strip().lower().startswith("f")
    pregnant  = is_female and pregnancy_str.strip() == "Yes"
    weeks     = weeks_val if pregnant else 0

    if nature == "RiskF":
        return _apply_riskf_filters_cached(catalog_df, _profile_key)

    if catalog_df is None or catalog_df.empty:
        return catalog_df

    df = catalog_df.copy()
    cc = _cat_col(df)
    pc = _part_col(df)

    # F1/F2: Exclude Masked (23)
    if cc:
        num = pd.to_numeric(df[cc], errors="coerce").fillna(-1).astype(int)
        df  = df[num != MASKED_CATEGORY_CODE].copy()

    # F7: Particularites
    if pc:
        def _keep(val):
            v = str(val or "").strip().upper()
            if v in ("","-","NAN","NONE"): return True
            if v == "M": return not is_female
            if v in ("W","F"): return is_female
            return True
        df = df[df[pc].apply(_keep)].copy()

    # F6: Sympt Female + gravida
    if nature == "Sympt" and is_female and pregnant:
        df = df[~df["Code"].isin(HIDDEN_SYMPT_FEMALE_PREGNANT)].copy()

    # F8: Sympt Female
    if nature == "Sympt" and is_female:
        df = df[~df["Code"].isin(HIDDEN_SYMPT_FEMALE)].copy()

    # F10: Signe Female + gravida per saptamani
    if nature == "Signe" and is_female and pregnant:
        hidden = _hidden_signs_for_weeks(weeks)
        if hidden: df = df[~df["Code"].isin(hidden)].copy()

    # F11: Agemin/Agemax
    ac_min = next((c for c in ("Agemin","agemin","AgeMin") if c in df.columns), None)
    ac_max = next((c for c in ("Agemax","agemax","AgeMax") if c in df.columns), None)
    if ac_min and ac_max:
        lo = pd.to_numeric(df[ac_min], errors="coerce")
        hi = pd.to_numeric(df[ac_max], errors="coerce")
        df = df[(lo.isna()|(lo<=age_months)) & (hi.isna()|(hi>=age_months))].copy()

    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def _apply_riskf_filters_cached(riskf_df: pd.DataFrame, _profile_key: tuple) -> pd.DataFrame:
    """F3, F4, F5, F9 — cached pe profile_key."""
    gender, age_months, pregnancy_str, weeks_val = _profile_key
    is_female = gender.strip().lower().startswith("f")
    pregnant  = is_female and pregnancy_str.strip() == "Yes"
    weeks     = weeks_val if pregnant else 0

    if riskf_df is None or riskf_df.empty:
        return riskf_df

    df = riskf_df.copy()
    cc = _cat_col(df)
    if not cc:
        return df

    num = pd.to_numeric(df[cc], errors="coerce").fillna(-1).astype(int)
    hidden_cats = {RISKF_MASKED_CODE, RISKF_ETHNICS_CODE, RISKF_LIVING_IN_CODE}
    if not is_female:
        hidden_cats.add(RISKF_OB_GYN_CODE)
    if age_months < MIN_AGE_PROFESSION_MONTHS:
        hidden_cats.add(RISKF_PROFESSION_CODE)
    df = df[~num.isin(hidden_cats)].copy()

    RF1,RF2,RF3,RF4,RF5 = 5,292,41,563,669
    hidden_rf = set()
    if is_female and pregnant:
        hidden_rf = {RF1,RF2,RF3,RF4} if weeks<20 else {RF1,RF2,RF5}
    elif is_female:
        hidden_rf = {RF1,RF2}
    if hidden_rf and "Code" in df.columns:
        df = df[~df["Code"].isin(hidden_rf)].copy()

    return df.reset_index(drop=True)


# ── Funcție helper publică pentru apeluri din pages_input ────────────────────
def get_filtered_catalog(catalog_df: pd.DataFrame, nature: str, profile: dict) -> pd.DataFrame:
    """
    Wrapper public: extrage cheia de cache din profil și apelează apply_ui_filters.
    Înlocuiește apelul direct apply_ui_filters(catalog_df, nature, profile).

    Utilizare în pages_input.py:
        from .ui_filters import get_filtered_catalog
        _sympt_f = get_filtered_catalog(sympt_catalog, "Sympt", _profile)
    """
    key = _profile_key(profile)
    return apply_ui_filters(catalog_df, nature, key)
