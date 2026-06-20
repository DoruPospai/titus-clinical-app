# age_factor_apply_v1.py

from pathlib import Path
import math
import numpy as np
import pandas as pd


XLSX_PATH = Path(r"D:\MULTIMI_VAGI1\Test11\Test11_Final_OK\data_clean\Order_AgeMetadata_v8.xlsx")
SHEET_NAME = 0          # sau pune numele foii, de ex. "Diseases"
PATIENT_AGE_MONTHS = 360   # exemplu: 30 ani


CONFIDENCE_WEIGHTS = {
    "missing": 0.00,
    "low": 0.25,
    "medium": 0.60,
    "high": 1.00,
}


def _to_float(x) -> float:
    try:
        if x is None:
            return np.nan
        if isinstance(x, str) and not x.strip():
            return np.nan
        v = float(x)
        if math.isnan(v):
            return np.nan
        return v
    except Exception:
        return np.nan


def _single_peak_age_factor_raw(
    age_months: float,
    mean_months=None,
    agemin_months=None,
    agemax_months=None,
) -> float:
    age = _to_float(age_months)
    mean_ = _to_float(mean_months)
    amin = _to_float(agemin_months)
    amax = _to_float(agemax_months)

    if math.isnan(age):
        return np.nan

    # Fără borne, nu folosim model tare de vârstă
    if math.isnan(amin) or math.isnan(amax) or amax < amin:
        return np.nan

    # În afara intervalului -> incompatibilitate completă pentru acest peak
    if age < amin or age > amax:
        return 0.0

    # Centru de peak
    if math.isnan(mean_) or mean_ < amin or mean_ > amax:
        center = (amin + amax) / 2.0
    else:
        center = mean_

    if amax == amin:
        return 1.0

    if age == center:
        return 1.0

    if age < center:
        denom = max(center - amin, 1e-9)
        tri = (age - amin) / denom
    else:
        denom = max(amax - center, 1e-9)
        tri = (amax - age) / denom

    tri = min(max(tri, 0.0), 1.0)

    # 0.5 la margini, 1.0 în centru
    return 0.5 + 0.5 * tri


def compute_age_factor(
    age_months: float,
    age_confidence,
    mean1=None,
    agemin1=None,
    agemax1=None,
    mean2=None,
    agemin2=None,
    agemax2=None,
):
    raw1 = _single_peak_age_factor_raw(age_months, mean1, agemin1, agemax1)
    raw2 = _single_peak_age_factor_raw(age_months, mean2, agemin2, agemax2)

    usable_raws = [r for r in (raw1, raw2) if not np.isnan(r)]
    age_factor_raw = max(usable_raws) if usable_raws else np.nan

    conf_key = str(age_confidence or "missing").strip().lower()
    age_weight = CONFIDENCE_WEIGHTS.get(conf_key, 0.00)

    if np.isnan(age_factor_raw):
        age_factor = 1.0
        hard_age_exclusion = 0.0
    else:
        age_factor = 1.0 - age_weight * (1.0 - age_factor_raw)
        hard_age_exclusion = 1.0 if (conf_key == "high" and age_factor_raw == 0.0) else 0.0

    return {
        "AgeFactorRaw": float(age_factor_raw) if not np.isnan(age_factor_raw) else np.nan,
        "AgeFactor": float(age_factor),
        "AgeWeight": float(age_weight),
        "HardAgeExclusion": float(hard_age_exclusion),
    }


def compute_age_factor_from_row(row, age_months: float):
    mean1 = row.get("mean1", row.get("mean"))
    agemin1 = row.get("Agemin1", row.get("Agemin"))
    agemax1 = row.get("Agemax1", row.get("Agemax"))

    mean2 = row.get("mean2", None)
    agemin2 = row.get("Agemin2", None)
    agemax2 = row.get("Agemax2", None)

    return compute_age_factor(
        age_months=age_months,
        age_confidence=row.get("AgeConfidence", "missing"),
        mean1=mean1,
        agemin1=agemin1,
        agemax1=agemax1,
        mean2=mean2,
        agemin2=agemin2,
        agemax2=agemax2,
    )


def main():
    df = pd.read_excel(XLSX_PATH, sheet_name=SHEET_NAME)

    extra_cols = ["AgeFactorRaw", "AgeFactor", "AgeWeight", "HardAgeExclusion"]
    df = df.drop(columns=[c for c in extra_cols if c in df.columns], errors="ignore")

    factors_df = df.apply(
        lambda row: pd.Series(compute_age_factor_from_row(row, PATIENT_AGE_MONTHS)),
        axis=1,
    )

    out_df = pd.concat([df, factors_df], axis=1)

    out_path = XLSX_PATH.with_name(
        f"{XLSX_PATH.stem}_AgeFactor_{PATIENT_AGE_MONTHS}m.xlsx"
    )
    out_df.to_excel(out_path, index=False)

    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()