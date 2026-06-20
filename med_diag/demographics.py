# DOR_demographics_final.py
import numpy as np
import pandas as pd

from .utils import normalize_text, safe_float


def _uniq_join(items):
    out = []
    for x in items:
        if x and x not in out:
            out.append(x)
    return "; ".join(out)


def _confidence_interval_from_mean(mean_age: float, age_min: float, age_max: float):
    if np.isnan(mean_age) or mean_age <= 0:
        return np.nan, np.nan, None, None, None

    z = 1.96

    if (
        not np.isnan(age_min)
        and not np.isnan(age_max)
        and age_max >= age_min
        and age_min <= mean_age <= age_max
    ):
        left_span = max(0.0, mean_age - age_min)
        right_span = max(0.0, age_max - mean_age)

        sigma_left = max(1.0, left_span / 3.0)
        sigma_right = max(1.0, right_span / 3.0)

        ci_lo = max(0.0, mean_age - z * sigma_left)
        ci_hi = mean_age + z * sigma_right

        return (
            float(ci_lo),
            float(ci_hi),
            float(sigma_left),
            float(sigma_right),
            "asymmetric_from_local_bounds",
        )

    if mean_age <= 1:
        sigma = 0.50
    elif mean_age <= 6:
        sigma = 2.0
    elif mean_age <= 12:
        sigma = 3.0
    elif mean_age <= 120:
        sigma = max(6.0, 0.20 * mean_age)
    else:
        sigma = max(12.0, 0.15 * mean_age)

    ci_lo = max(0.0, mean_age - z * sigma)
    ci_hi = mean_age + z * sigma

    return (
        float(ci_lo),
        float(ci_hi),
        float(sigma),
        float(sigma),
        "fallback_sigma",
    )


def _is_patient_female(sex: str) -> bool:
    s = str(sex or "").strip().lower()
    return s.startswith("f")


def _sex_rule_excludes(sex_rule: str, patient_sex: str) -> bool:
    rule = normalize_text(sex_rule or "")
    patient_is_female = _is_patient_female(patient_sex)

    if rule in {"w", "f", "female"}:
        return not patient_is_female
    if rule in {"m", "male"}:
        return patient_is_female
    return False


def _pregnancy_rule_requires_pregnancy(preg_rule: str) -> bool:
    rule = normalize_text(preg_rule or "")
    if not rule:
        return False
    if rule in {"n", "no", "0", "non"}:
        return False
    return True


def apply_demographic_context(df: pd.DataFrame, demographics_df: pd.DataFrame, profile: dict) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    patient_sex = str(profile.get("gender", "Female") or "Female").strip()
    age_m = int(profile.get("age_in_months") or 0)
    pregnant = (_is_patient_female(patient_sex) and str(profile.get("pregnancy", "No")) == "Yes")

    if demographics_df is not None and not demographics_df.empty:
        demo = demographics_df.copy()
        demo["CodeMaladie"] = pd.to_numeric(demo["CodeMaladie"], errors="coerce").astype("Int64")
        out = out.merge(demo, on="CodeMaladie", how="left")
    else:
        for c in ["Women", "mean", "Agemin", "Agemax", "SEX", "PREGNANCY"]:
            out[c] = np.nan if c not in {"SEX", "PREGNANCY"} else ""

    penalties = []
    filters = []
    implications = []
    final_scores = []

    for _, row in out.iterrows():
        base = float(row.get("Scor Latent", 0.0))
        mean_age = safe_float(row.get("mean"), default=np.nan)
        age_min = safe_float(row.get("Agemin"), default=np.nan)
        age_max = safe_float(row.get("Agemax"), default=np.nan)
        sex_rule = row.get("SEX", "")
        preg_rule = row.get("PREGNANCY", "")

        ci_lo, ci_hi, _, _, ci_mode = _confidence_interval_from_mean(mean_age, age_min, age_max)

        filter_reasons = []
        implication_reasons = []

        if _sex_rule_excludes(sex_rule, patient_sex):
            filter_reasons.append("Sex exclusion")
            implication_reasons.append(
                f"Patient sex is {patient_sex.lower()}, which is incompatible with the local SEX rule."
            )

        if _pregnancy_rule_requires_pregnancy(preg_rule) and not pregnant:
            filter_reasons.append("Pregnancy exclusion")
            implication_reasons.append(
                "This disease is pregnancy-specific and is excluded for the current pregnancy context."
            )

        if not np.isnan(ci_lo) and not np.isnan(ci_hi):
            if age_m < ci_lo or age_m > ci_hi:
                filter_reasons.append("Age exclusion")
                if ci_mode == "asymmetric_from_local_bounds" and not np.isnan(age_min) and not np.isnan(age_max):
                    implication_reasons.append(
                        f"Patient age of {age_m} months falls outside the 95% confidence interval around the local mean age of {int(mean_age)} months "
                        f"(estimated CI: {int(ci_lo)}-{int(ci_hi)} months from Agemin={int(age_min)} and Agemax={int(age_max)})."
                    )
                else:
                    implication_reasons.append(
                        f"Patient age of {age_m} months falls outside the 95% confidence interval derived from the local mean age of {int(mean_age)} months "
                        f"(estimated CI: {int(ci_lo)}-{int(ci_hi)} months)."
                    )

        excluded = len(filter_reasons) > 0

        if excluded:
            penalty = 100.0
            final_score = 0.0
            filter_text = _uniq_join(filter_reasons)
            implication_text = _uniq_join(implication_reasons)
        else:
            penalty = 0.0
            final_score = base
            filter_text = ""
            implication_text = ""

        penalties.append(float(penalty))
        filters.append(filter_text)
        implications.append(implication_text)
        final_scores.append(float(final_score))

    out["Filter"] = filters
    out["Penalty"] = penalties
    out["Implication"] = implications
    out["Latent Penalizat"] = final_scores

    out = out.sort_values(["Latent Penalizat", "disease_code"], ascending=[False, True]).reset_index(drop=True)
    return out
AGE_CONFIDENCE_WEIGHTS = {
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
        if np.isnan(v):
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

    if np.isnan(age):
        return np.nan

    if np.isnan(amin) or np.isnan(amax) or amax < amin:
        return np.nan

    if age < amin or age > amax:
        return 0.0

    if np.isnan(mean_) or mean_ < amin or mean_ > amax:
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
    age_weight = AGE_CONFIDENCE_WEIGHTS.get(conf_key, 0.00)

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


def compute_age_factor_from_row(row, patient_age_months: float):
    mean1 = row.get("mean1", row.get("mean"))
    agemin1 = row.get("Agemin1", row.get("Agemin"))
    agemax1 = row.get("Agemax1", row.get("Agemax"))

    mean2 = row.get("mean2", None)
    agemin2 = row.get("Agemin2", None)
    agemax2 = row.get("Agemax2", None)

    return compute_age_factor(
        age_months=patient_age_months,
        age_confidence=row.get("AgeConfidence", "missing"),
        mean1=mean1,
        agemin1=agemin1,
        agemax1=agemax1,
        mean2=mean2,
        agemin2=agemin2,
        agemax2=agemax2,
    )


def apply_age_factor(df: pd.DataFrame, patient_age_months: int) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    extra_cols = ["AgeFactorRaw", "AgeFactor", "AgeWeight", "HardAgeExclusion"]
    for col in extra_cols:
        if col in out.columns:
            out = out.drop(columns=[col])

    factors_df = out.apply(
        lambda row: pd.Series(compute_age_factor_from_row(row, patient_age_months)),
        axis=1,
    )

    out = pd.concat([out, factors_df], axis=1)
    return out