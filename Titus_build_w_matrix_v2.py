#!/usr/bin/env python3
# Titus_build_w_matrix_v2.py
#
# Construieste w_matrix direct in memorie cu checkpoint la fiecare
# CHECKPOINT_EVERY boli. La crash sau oprire, reia exact de unde s-a oprit.
#
# Output: out_w_matrix/
#   Titus_w_matrix.npz          — rezultat final
#   Titus_w_matrix_index.csv    — index code→name→idx
#   Titus_w_matrix_summary.json — statistici finale
#   Titus_w_checkpoint.npz      — checkpoint curent (sters la final)
#   Titus_w_checkpoint.json     — metadata checkpoint

from __future__ import annotations

import csv
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd

# =============================================================================
# CONFIGURATIE
# =============================================================================
TABEL2   = r"D:/MULTIMI_VAGI1/Test11/Test11_Final_OK/data_clean/Tabel2_Titus.xlsx"
MALADIES = r"D:/MULTIMI_VAGI1/Test11/Test11_Final_OK/data_clean/Maladies.xlsx"
OUTDIR   = r"D:/MULTIMI_VAGI1/Test11/Test11_Final_OK/out_w_matrix"

MIN_SUBSET_SIZES               = (3, 4, 5)
INCLUDE_FULL_DISEASE           = True
ALLOWED_PATIENT_SCORES         = (50, 100, 150)
CR_THRESHOLD                   = 0.40
CR_MODE                        = "lambda_fix"
CR_LAMBDA                      = 0.3
MAX_EXACT_PATIENTS_PER_DISEASE = 500_000
FILTER_SEMIO_ONLY              = True
SEMIO_TYPES                    = {"Sympt", "Signe"}

CHECKPOINT_EVERY = 50    # salveaza checkpoint la fiecare N boli procesate
REPORT_EVERY     = 50    # print progres la fiecare N boli

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass(frozen=True, order=True)
class Element:
    nature: str
    code: int

    def key(self) -> str:
        return f"{self.nature}:{self.code}"


@dataclass
class Disease:
    code: int
    name: str
    elements: Tuple[Element, ...]
    raw_scores: Dict[Element, float]

    @property
    def cardinality(self) -> int:
        return len(self.elements)


@dataclass
class Patient:
    source_disease: int
    elements: Tuple[Element, ...]
    scores: Dict[Element, int]

    @property
    def mass(self) -> int:
        return int(sum(self.scores.values()))


# =============================================================================
# INCARCARE DATE
# =============================================================================

def normalize_nature(value: object) -> Optional[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    txt = str(value).strip().lower()
    if txt == "sympt":
        return "Sympt"
    if txt == "signe":
        return "Signe"
    return None


def load_diseases(tabel2_path: Path, maladies_path: Optional[Path] = None) -> Dict[int, Disease]:
    df = pd.read_excel(tabel2_path, sheet_name="Tabel2")
    df["NatureLien"] = df["NatureLien"].map(normalize_nature)
    if FILTER_SEMIO_ONLY:
        df = df[df["NatureLien"].isin(SEMIO_TYPES)].copy()

    df["CodeMaladie"] = pd.to_numeric(df["CodeMaladie"], errors="coerce")
    df["CodeElement"] = pd.to_numeric(df["CodeElement"], errors="coerce")
    df["Score"]       = pd.to_numeric(df["Score"],       errors="coerce")
    df = df.dropna(subset=["CodeMaladie", "CodeElement", "Score", "NatureLien"]).copy()
    df["CodeMaladie"] = df["CodeMaladie"].astype(int)
    df["CodeElement"] = df["CodeElement"].astype(int)

    names: Dict[int, str] = {}
    if maladies_path and maladies_path.exists():
        mdf = pd.read_excel(maladies_path)
        if "CodeMaladie" in mdf.columns and "NomMaladie" in mdf.columns:
            for _, row in mdf[["CodeMaladie", "NomMaladie"]].dropna().iterrows():
                names[int(row["CodeMaladie"])] = str(row["NomMaladie"])

    diseases: Dict[int, Disease] = {}
    for code, g in df.groupby("CodeMaladie", sort=True):
        score_map: Dict[Element, float] = {}
        fallback_name = None
        if "NomMaladie" in g.columns:
            vals = g["NomMaladie"].dropna().astype(str).tolist()
            fallback_name = vals[0] if vals else None
        disease_name = names.get(int(code), fallback_name or str(int(code)))
        for _, row in g.iterrows():
            elem = Element(str(row["NatureLien"]), int(row["CodeElement"]))
            score_map[elem] = float(row["Score"])
        diseases[int(code)] = Disease(
            code=int(code),
            name=disease_name,
            elements=tuple(sorted(score_map.keys())),
            raw_scores=score_map,
        )
    return diseases


# =============================================================================
# CR ENGINE
# =============================================================================

class CrEngine:
    def __init__(self, diseases: Dict[int, Disease]) -> None:
        self.all_elems: List[Element] = sorted(
            {e for d in diseases.values() for e in d.elements}
        )
        self.elem2idx: Dict[Element, int] = {e: i for i, e in enumerate(self.all_elems)}
        self.all_codes: List[int]         = sorted(diseases.keys())
        self.code2idx:  Dict[int, int]    = {c: i for i, c in enumerate(self.all_codes)}

        N_D = len(self.all_codes)
        N_E = len(self.all_elems)
        self.S = np.zeros((N_D, N_E), dtype=np.float32)
        for code, disease in diseases.items():
            d_idx = self.code2idx[code]
            for elem, score in disease.raw_scores.items():
                e_idx = self.elem2idx.get(elem)
                if e_idx is not None:
                    self.S[d_idx, e_idx] = float(score)

    def cr_all(self, patient: Patient) -> np.ndarray:
        masse = float(patient.mass)
        if masse <= 0:
            return np.zeros(len(self.all_codes), dtype=np.float32)

        overlap = np.zeros(len(self.all_codes), dtype=np.float32)
        gap     = np.zeros(len(self.all_codes), dtype=np.float32)

        for elem, intensity in patient.scores.items():
            e_idx = self.elem2idx.get(elem)
            if e_idx is None:
                continue
            col = self.S[:, e_idx]
            overlap += np.minimum(np.float32(intensity), col)
            if CR_MODE == "lambda_fix":
                gap += np.float32(intensity) * (col == 0).astype(np.float32)
            elif CR_MODE == "lambda_dyn":
                gap += np.float32(intensity) * (1.0 - col / 150.0)

        if CR_MODE == "current":
            return overlap / masse
        return (overlap - CR_LAMBDA * gap) / masse


# =============================================================================
# GENERARE PACIENTI
# =============================================================================

def exact_patient_count(cardinality: int) -> int:
    total = 0
    for s in MIN_SUBSET_SIZES:
        if s <= cardinality:
            total += math.comb(cardinality, s) * (len(ALLOWED_PATIENT_SCORES) ** s)
    if INCLUDE_FULL_DISEASE and cardinality > 0:
        total += len(ALLOWED_PATIENT_SCORES) ** cardinality
    return total


def iter_all_patients(source: Disease) -> Iterator[Patient]:
    elems = list(source.elements)
    for subset_size in MIN_SUBSET_SIZES:
        if subset_size <= len(elems):
            for combo in itertools.combinations(elems, subset_size):
                for assigned in itertools.product(ALLOWED_PATIENT_SCORES, repeat=len(combo)):
                    elems_sorted = tuple(sorted(combo))
                    yield Patient(
                        source_disease=source.code,
                        elements=elems_sorted,
                        scores={e: int(s) for e, s in zip(elems_sorted, assigned)},
                    )
    if INCLUDE_FULL_DISEASE and elems:
        elems_sorted = tuple(sorted(elems))
        for assigned in itertools.product(ALLOWED_PATIENT_SCORES, repeat=len(elems_sorted)):
            yield Patient(
                source_disease=source.code,
                elements=elems_sorted,
                scores={e: int(s) for e, s in zip(elems_sorted, assigned)},
            )


# =============================================================================
# ACTUALIZARE W-MATRIX
# =============================================================================

def update_w_from_patient(
    engine: CrEngine,
    patient: Patient,
    w: np.ndarray,
) -> int:
    cr_vals   = engine.cr_all(patient)
    src_idx   = engine.code2idx[patient.source_disease]
    source_cr = float(cr_vals[src_idx])

    if source_cr < CR_THRESHOLD:
        return 0

    eligible = [
        (float(cr_val), d_idx)
        for d_idx, cr_val in enumerate(cr_vals)
        if cr_val >= CR_THRESHOLD
    ]
    eligible.sort(key=lambda x: (-x[0], x[1]))

    # Grupeaza pe cr egal, reprezentant = d_idx minim
    chain: List[Tuple[float, int]] = []
    i = 0
    while i < len(eligible):
        cr_cur = eligible[i][0]
        j = i
        while j < len(eligible) and eligible[j][0] == cr_cur:
            j += 1
        rep_idx = min(eligible[k][1] for k in range(i, j))
        chain.append((cr_cur, rep_idx))
        i = j

    n_triplets = 0
    for step in range(len(chain) - 1):
        a_idx = chain[step][1]
        b_idx = chain[step + 1][1]
        if a_idx != b_idx:
            w[a_idx, b_idx] += 1
            n_triplets += 1

    return n_triplets


# =============================================================================
# CHECKPOINT
# =============================================================================

def save_checkpoint(
    outdir: Path,
    w: np.ndarray,
    last_code_done: int,
    d_num_done: int,
    total_triplets: int,
    total_patients: int,
    total_skipped_p: int,
    total_oversized: int,
) -> None:
    np.save(outdir / "Titus_w_checkpoint.npy", w)
    meta = {
        "last_code_done" : int(last_code_done),
        "d_num_done"     : int(d_num_done),
        "total_triplets" : int(total_triplets),
        "total_patients" : int(total_patients),
        "total_skipped_p": int(total_skipped_p),
        "total_oversized": int(total_oversized),
    }
    with open(outdir / "Titus_w_checkpoint.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"    [checkpoint] boala #{d_num_done}  code={last_code_done}"
          f"  triplete={total_triplets:,}")


def load_checkpoint(outdir: Path) -> Optional[dict]:
    cp_npy  = outdir / "Titus_w_checkpoint.npy"
    cp_json = outdir / "Titus_w_checkpoint.json"
    if cp_npy.exists() and cp_json.exists():
        with open(cp_json, encoding="utf-8") as f:
            meta = json.load(f)
        print(f"  [RESUME] checkpoint trovato: ultima boala={meta['last_code_done']}"
              f"  d_num={meta['d_num_done']}  triplete={meta['total_triplets']:,}")
        return meta
    return None


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    outdir = Path(OUTDIR)
    outdir.mkdir(parents=True, exist_ok=True)

    print("Citire Tabel2 + Maladies ...")
    diseases = load_diseases(Path(TABEL2), Path(MALADIES))
    print(f"Boli incarcate: {len(diseases)}")

    print("Construire matrice numpy (CrEngine) ...")
    engine = CrEngine(diseases)
    N_D = len(engine.all_codes)
    print(f"Matrice S: {engine.S.shape}  |  memorie: {engine.S.nbytes/1e6:.1f} MB")

    selected_codes = sorted(diseases.keys())

    # ── Verifica checkpoint ────────────────────────────────────────────────────
    cp_meta = load_checkpoint(outdir)

    if cp_meta is not None:
        w = np.load(outdir / "Titus_w_checkpoint.npy")
        assert w.shape == (N_D, N_D), f"Checkpoint w shape mismatch: {w.shape} vs ({N_D},{N_D})"
        resume_from_code   = int(cp_meta["last_code_done"])
        total_triplets     = int(cp_meta["total_triplets"])
        total_patients     = int(cp_meta["total_patients"])
        total_skipped_p    = int(cp_meta["total_skipped_p"])
        total_oversized    = int(cp_meta["total_oversized"])
        # sari bolile deja procesate
        selected_codes = [c for c in selected_codes if c > resume_from_code]
        d_num_offset   = int(cp_meta["d_num_done"])
        print(f"  Resume de la boala #{d_num_offset+1}  (cod {resume_from_code}+)")
    else:
        w = np.zeros((N_D, N_D), dtype=np.uint32)
        print(f"W-matrix: ({N_D}, {N_D})  |  memorie: {w.nbytes/1e6:.1f} MB")
        total_triplets   = 0
        total_patients   = 0
        total_skipped_p  = 0
        total_oversized  = 0
        d_num_offset     = 0

    print(f"\nElaborare {len(selected_codes)} boli ramase ...\n")

    checkpoint_counter = 0
    last_code_done     = selected_codes[0] - 1 if selected_codes else -1

    for d_num_rel, code in enumerate(selected_codes):
        d_num_abs = d_num_offset + d_num_rel + 1
        disease   = diseases[code]
        n_exact   = exact_patient_count(disease.cardinality)

        if n_exact > MAX_EXACT_PATIENTS_PER_DISEASE:
            print(f"  SKIP [{disease.code}] {disease.name}  patients={n_exact:,}")
            total_oversized += 1
            last_code_done   = code
            checkpoint_counter += 1
        else:
            if d_num_rel % REPORT_EVERY == 0:
                print(f"  Boala {d_num_abs}/{len(diseases)}  [{disease.code}] {disease.name}"
                      f"  patients={n_exact:,}  triplete_total={total_triplets:,}")

            for patient in iter_all_patients(disease):
                n = update_w_from_patient(engine, patient, w)
                if n > 0:
                    total_triplets += n
                    total_patients += 1
                else:
                    total_skipped_p += 1

            last_code_done     = code
            checkpoint_counter += 1

        # Checkpoint periodic
        if checkpoint_counter >= CHECKPOINT_EVERY:
            save_checkpoint(
                outdir, w, last_code_done, d_num_abs,
                total_triplets, total_patients, total_skipped_p, total_oversized,
            )
            checkpoint_counter = 0

    # Checkpoint final prima di salvare il risultato
    save_checkpoint(
        outdir, w, last_code_done, d_num_offset + len(selected_codes),
        total_triplets, total_patients, total_skipped_p, total_oversized,
    )

    # ── Salvare rezultat final ─────────────────────────────────────────────────
    code_arr = np.array(engine.all_codes, dtype=np.int32)
    name_arr = np.array([diseases[c].name for c in engine.all_codes])

    out_npz = outdir / "Titus_w_matrix.npz"
    np.savez_compressed(out_npz, w=w, disease_codes=code_arr, disease_names=name_arr)
    size_mb = out_npz.stat().st_size / 1e6

    # Index CSV
    with open(outdir / "Titus_w_matrix_index.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["idx", "code", "name"])
        writer.writeheader()
        writer.writerows(
            {"idx": i, "code": engine.all_codes[i], "name": diseases[engine.all_codes[i]].name}
            for i in range(N_D)
        )

    # Curata checkpoint
    for cp_file in ["Titus_w_checkpoint.npy", "Titus_w_checkpoint.json"]:
        cp_path = outdir / cp_file
        if cp_path.exists():
            cp_path.unlink()
    print("  [checkpoint files removed]")

    # Summary
    nonzero = int(np.count_nonzero(w))
    w_max   = int(w.max())
    w_sum   = int(w.sum())

    summary = {
        "script"                        : "Titus_build_w_matrix_v2.py",
        "diseases_total"                : N_D,
        "oversized_skipped"             : total_oversized,
        "patients_processed"            : total_patients,
        "patients_below_threshold"      : total_skipped_p,
        "triplets_accumulated"          : total_triplets,
        "w_nonzero_entries"             : nonzero,
        "w_max_value"                   : w_max,
        "w_sum"                         : w_sum,
        "output_npz_mb"                 : round(size_mb, 2),
        "cr_threshold"                  : CR_THRESHOLD,
        "cr_mode"                       : CR_MODE,
        "cr_lambda"                     : CR_LAMBDA,
        "max_exact_patients_per_disease": MAX_EXACT_PATIENTS_PER_DISEASE,
        "checkpoint_every"              : CHECKPOINT_EVERY,
    }

    with open(outdir / "Titus_w_matrix_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nSalvat: {out_npz}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()