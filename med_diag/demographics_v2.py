"""
demographics_v2.py — TITUS
Factor demografic recalibrat pe 3 straturi + detecție familii de boli.

Stratul 1 — AgeEvidence=insufficient sau AgeConfidence=low  → factor neutru 1.0
Stratul 2 — Boli congenitale (mean=0, Agemin=0)            → regula dura pe Agemax
Stratul 3 — Boli cu interval valid                         → triunghi asimetric [Agemin, mean, Agemax]

Factor final = 1.0 - weight * (1.0 - raw)
  weight: high=1.0, medium=0.60, low=0.25
HardExclusion: True doar daca confidence=high si raw=0.0
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

# ── Ponderi confidence ────────────────────────────────────────────────────
CONFIDENCE_WEIGHTS = {
    "high"   : 1.00,
    "medium" : 0.60,
    "low"    : 0.25,
    "missing": 0.00,
}

# ── Prag soft-decay pentru boli congenitale cu confidence != high ─────────
CONGENITAL_SOFT_DECAY_FACTOR = 0.5   # max factor in afara intervalului


# ─────────────────────────────────────────────────────────────────────────
# Helper-e
# ─────────────────────────────────────────────────────────────────────────

def _f(x) -> float:
    """Conversie sigura la float, NaN daca invalid."""
    try:
        v = float(x)
        return np.nan if math.isnan(v) else v
    except Exception:
        return np.nan


def _triangular_asymmetric(age: float, amin: float, mean_: float, amax: float) -> float:
    """
    Triunghi asimetric:
      - La mean_ → 1.0
      - La amin sau amax → 0.5
      - In afara [amin, amax] → 0.0
    """
    if age < amin or age > amax:
        return 0.0
    if age == mean_:
        return 1.0
    if age < mean_:
        span = max(mean_ - amin, 1e-9)
        t = (age - amin) / span
    else:
        span = max(amax - mean_, 1e-9)
        t = (amax - age) / span
    return 0.5 + 0.5 * t


def _compute_raw_for_peak(
    age: float,
    mean_: float,
    amin: float,
    amax: float,
    confidence: str,
) -> Optional[float]:
    """
    Calculeaza factorul raw pentru un singur peak.
    Returneaza None daca datele sunt invalide.
    """
    if math.isnan(amin) or math.isnan(amax) or amax < amin:
        return None

    # Stratul 2: boala congenitala (mean=0, amin=0)
    if _f(mean_) == 0.0 and amin == 0.0:
        if age <= amax:
            return 1.0
        else:
            if confidence == "high":
                return 0.0  # excludere dura
            else:
                # Decay soft dincolo de Agemax
                decay = max(0.0, 1.0 - (age - amax) / max(amax, 12.0))
                return decay * CONGENITAL_SOFT_DECAY_FACTOR

    # Stratul 3: interval valid cu mean
    mean_val = _f(mean_)
    if math.isnan(mean_val) or mean_val < amin or mean_val > amax:
        mean_val = (amin + amax) / 2.0  # fallback: centru interval

    return _triangular_asymmetric(age, amin, mean_val, amax)


# ─────────────────────────────────────────────────────────────────────────
# Calcul factor per boala
# ─────────────────────────────────────────────────────────────────────────

def compute_age_factor_v2(
    age_months: float,
    row: dict,
) -> dict:
    """
    Calculeaza factorul demografic de varsta pentru o boala.

    Returneaza:
      AgeFactor      : float [0.0, 1.0] — factor multiplicativ pe CR
      HardExclusion  : bool  — True = boala exclusa complet (confidence=high, raw=0)
      Layer          : str   — stratul aplicat (diagnostic)
      RawFactor      : float — factorul brut inainte de ponderare
      F12Exclusion   : bool  — True = exclus prin regula F12 (distributie normala)
      F12Detail      : str   — motivul excluderii F12
    """
    age = _f(age_months)
    if math.isnan(age):
        return {"AgeFactor": 1.0, "HardExclusion": False, "Layer": "no_age",
                "RawFactor": np.nan, "F12Exclusion": False, "F12Detail": ""}

    evidence   = str(row.get("AgeEvidence",   "insufficient") or "insufficient").strip().lower()
    confidence = str(row.get("AgeConfidence", "low")          or "low").strip().lower()
    weight     = CONFIDENCE_WEIGHTS.get(confidence, 0.0)

    # Stratul 1: date insuficiente → neutru
    if evidence == "insufficient" or weight == 0.0:
        return {"AgeFactor": 1.0, "HardExclusion": False, "Layer": "insufficient",
                "RawFactor": np.nan, "F12Exclusion": False, "F12Detail": ""}

    # Colecteaza peak-uri valide (suport bimodal)
    peaks = [
        (row.get("mean1"), _f(row.get("Agemin1", np.nan)), _f(row.get("Agemax1", np.nan))),
        (row.get("mean2"), _f(row.get("Agemin2", np.nan)), _f(row.get("Agemax2", np.nan))),
    ]

    raw_values = []
    for mean_, amin, amax in peaks:
        r = _compute_raw_for_peak(age, _f(mean_), amin, amax, confidence)
        if r is not None:
            raw_values.append(r)

    if not raw_values:
        return {"AgeFactor": 1.0, "HardExclusion": False, "Layer": "no_valid_peak",
                "RawFactor": np.nan, "F12Exclusion": False, "F12Detail": ""}

    raw = max(raw_values)   # bimodal: cel mai bun peak

    factor      = 1.0 - weight * (1.0 - raw)
    hard_excl   = (confidence == "high" and raw == 0.0)
    layer       = "congenital" if (_f(peaks[0][0]) == 0.0 and peaks[0][1] == 0.0) else "interval"

    # ── F12: Excludere distributie normala ───────────────────────────────────
    # Aplica cand confidence=high si boala nu e deja exclusa prin triunghi.
    # Sigma = (amax - amin) / 6  — [amin, amax] tratat ca interval ±3σ global.
    # Excludere daca age < mean - 3σ  sau  age > mean + 3σ
    #
    # REGULA PRIORITATE: intervalul explicit [Agemin, Agemax] este autoritar.
    # F12 NU exclude daca age <= global_agemax (pacientul in intervalul documentat).
    # F12 adauga valoare DOAR pentru age > global_agemax: boala cu interval
    # larg (ex: 0-1800 luni) la pacient statistic improbabil dar in-interval.
    f12_exclusion = False
    f12_detail    = ""

    if confidence == "high" and not hard_excl:
        # Intervalul global autoritar: [Agemin1, Agemax2 sau Agemax1]
        valid_amaxes = [amax for _, amin, amax in peaks
                        if not math.isnan(amax)]
        valid_amins  = [amin for _, amin, amax in peaks
                        if not math.isnan(amin)]
        global_agemax = max(valid_amaxes) if valid_amaxes else np.nan
        global_agemin = min(valid_amins)  if valid_amins  else np.nan

        # Daca pacientul este in interiorul intervalului explicit → F12 nu se aplica.
        # Triunghiul asimetric a dat deja factorul corect (raw > 0).
        if (not math.isnan(global_agemax)) and (age <= global_agemax):
            pass  # F12 dezactivat — intervalul explicit acopera pacientul
        else:
            for mean_, amin, amax in peaks:
                m = _f(mean_)
                if math.isnan(m) or math.isnan(amin) or math.isnan(amax):
                    continue
                if m < amin or m > amax:
                    m = (amin + amax) / 2.0

                # Sigma global din intervalul total
                sigma = max((amax - amin) / 6.0, 1.0)
                lower = max(0.0, m - 3.0 * sigma)
                upper = m + 3.0 * sigma

                if age < lower or age > upper:
                    f12_exclusion = True
                    f12_detail = (
                        f"F12: varsta {int(age)}luni in afara ±3σ="
                        f"[{int(lower)},{int(upper)}] "
                        f"(mean={int(m)}luni, σ={int(sigma)}luni)"
                    )
                else:
                    # In intervalul normal — acest peak acopera pacientul
                    f12_exclusion = False
                    f12_detail    = ""
                    break  # bimodal: un peak valid e suficient

    if f12_exclusion:
        factor    = 0.0
        hard_excl = True
        layer     = "f12_normal_exclusion"
    # ── Sfarsit F12 ──────────────────────────────────────────────────────────

    return {
        "AgeFactor"    : round(float(factor), 4),
        "HardExclusion": bool(hard_excl),
        "Layer"        : layer,
        "RawFactor"    : round(float(raw), 4),
        "F12Exclusion" : f12_exclusion,
        "F12Detail"    : f12_detail,
    }


# ─────────────────────────────────────────────────────────────────────────
# Detectie familii
# ─────────────────────────────────────────────────────────────────────────

def build_family_map(
    maladies_df: pd.DataFrame,
    age_df: pd.DataFrame,
    min_family_size: int = 2,
    prefix_words: int = 2,
) -> dict[int, list[int]]:
    """
    Detecteaza familii de boli prin prefix al numelui (primele N cuvinte).
    Returneaza: {code: [code_sibling1, code_sibling2, ...]}
    Familia unui cod = toate bolile cu acelasi prefix, excluzand codul insusi.
    """
    names = maladies_df[["CodeMaladie","NomMaladie"]].copy()
    names["prefix"] = names["NomMaladie"].str.split().str[:prefix_words].str.join(" ").str.strip()

    prefix_groups = names.groupby("prefix")["CodeMaladie"].apply(list).to_dict()

    family_map: dict[int, list[int]] = {}
    for prefix, codes in prefix_groups.items():
        if len(codes) >= min_family_size:
            for code in codes:
                siblings = [c for c in codes if c != code]
                family_map[int(code)] = siblings

    return family_map


def get_best_age_data_for_family(
    code: int,
    family_map: dict[int, list[int]],
    age_lookup: dict[int, dict],
) -> dict:
    """
    Daca boala are AgeEvidence=insufficient, cauta in familia sa un sibling
    cu date mai bune (AgeConfidence=high sau medium).
    Returneaza row-ul cu cele mai bune date disponibile.
    """
    row = age_lookup.get(code, {})
    evidence = str(row.get("AgeEvidence", "insufficient") or "insufficient").lower()

    if evidence != "insufficient":
        return row  # boala are date proprii valabile

    # Cauta in familie
    siblings = family_map.get(code, [])
    best_row = row
    best_conf_rank = -1

    conf_rank = {"high": 3, "medium": 2, "low": 1, "missing": 0}

    for sib_code in siblings:
        sib_row = age_lookup.get(sib_code, {})
        sib_ev  = str(sib_row.get("AgeEvidence", "insufficient") or "insufficient").lower()
        if sib_ev == "insufficient":
            continue
        sib_conf = str(sib_row.get("AgeConfidence", "low") or "low").lower()
        rank = conf_rank.get(sib_conf, 0)
        if rank > best_conf_rank:
            best_conf_rank = rank
            best_row = sib_row

    return best_row


# ─────────────────────────────────────────────────────────────────────────
# Aplicare pe DataFrame de ranking
# ─────────────────────────────────────────────────────────────────────────

def apply_age_factor_v2(
    ranking_df: pd.DataFrame,
    age_df: pd.DataFrame,
    maladies_df: pd.DataFrame,
    patient_age_months: int,
    use_family_fallback: bool = True,
) -> pd.DataFrame:
    """
    Aplica factorul demografic v2 pe un DataFrame de ranking TITUS.
    ranking_df trebuie sa aiba coloana 'code' (CodeMaladie).

    Adauga coloanele:
      AgeFactor, HardExclusion, AgeLayer, AgeRaw, AgeConfidence_used,
      F12Exclusion, F12Detail
    """
    if ranking_df is None or ranking_df.empty:
        return ranking_df

    # Build lookup
    age_lookup = {
        int(r["CodeMaladie"]): r.to_dict()
        for _, r in age_df.iterrows()
    }

    # Build family map
    family_map = {}
    if use_family_fallback and maladies_df is not None:
        family_map = build_family_map(maladies_df, age_df)

    results = []
    for _, row in ranking_df.iterrows():
        code = int(row.get("code", row.get("CodeMaladie", -1)))

        if use_family_fallback:
            age_row = get_best_age_data_for_family(code, family_map, age_lookup)
        else:
            age_row = age_lookup.get(code, {})

        factor_dict = compute_age_factor_v2(patient_age_months, age_row)
        results.append(factor_dict)

    factors_df = pd.DataFrame(results)
    out = ranking_df.copy().reset_index(drop=True)
    out["AgeFactor"]         = factors_df["AgeFactor"].values
    out["HardExclusion"]     = factors_df["HardExclusion"].values
    out["AgeLayer"]          = factors_df["Layer"].values
    out["AgeRaw"]            = factors_df["RawFactor"].values
    out["F12Exclusion"]      = factors_df["F12Exclusion"].values
    out["F12Detail"]         = factors_df["F12Detail"].values

    # Aplica: excludere dura → CR_adjusted = 0, altfel CR * AgeFactor
    cr_col = "cr" if "cr" in out.columns else "CR"
    if cr_col in out.columns:
        out["CR_demographic"] = out.apply(
            lambda r: 0.0 if r["HardExclusion"] else round(float(r[cr_col]) * r["AgeFactor"], 4),
            axis=1,
        )

    return out


# ─────────────────────────────────────────────────────────────────────────
# Statistici sumar (pentru debugging/validare)
# ─────────────────────────────────────────────────────────────────────────

def summarize_age_coverage(age_df: pd.DataFrame) -> dict:
    total = len(age_df)
    insuf = (age_df["AgeEvidence"] == "insufficient").sum()
    high  = (age_df["AgeConfidence"] == "high").sum()
    med   = (age_df["AgeConfidence"] == "medium").sum()
    low   = (age_df["AgeConfidence"] == "low").sum()
    bimod = age_df["mean2"].notna().sum()
    cong  = ((age_df["mean1"] == 0) & (age_df["Agemin1"] == 0)).sum()
    return {
        "total"            : total,
        "insufficient"     : int(insuf),
        "confidence_high"  : int(high),
        "confidence_medium": int(med),
        "confidence_low"   : int(low),
        "bimodal"          : int(bimod),
        "congenital_mean0" : int(cong),
        "pct_usable"       : round((total - insuf) / total * 100, 1),
    }
