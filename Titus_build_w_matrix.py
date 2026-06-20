#!/usr/bin/env python3
# Titus_build_w_matrix.py  — versiune chunked pentru CSV de 100+ GB
#
# w(D, Di) = |{triplete (P, A, B) : A=D si B=Di}| / |{triplete (P, A, B) : A=D}|
#
# Strategia: citim CSV-ul in chunks de CHUNK_SIZE randuri.
# Nu incarcam niciodata mai mult de ~1 GB in RAM.
#
# Output:
#   Titus_w_matrix.npz  — matrice scipy sparse (CSR) N x N
#   Titus_w_index.csv   — mapare index -> CodeMaladie
#   Titus_w_summary.json

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

# =============================================================================
# CONFIGURARE
# =============================================================================

ROOT         = Path(r"D:\MULTIMI_VAGI1\Test11\Test11_Final_OK")
TRIPLETS_DIR = ROOT / "out_exact_ordinal_triplets"
OUTDIR       = ROOT / "out_w_matrix"
MALADIES     = ROOT / "data_clean" / "Maladies.xlsx"

# Fisierul CSV de triplete
TRIPLETS_CSV = TRIPLETS_DIR / "Titus_exact_triplets.csv"

# Chunk size: cate randuri citim odata din CSV
# La ~50 bytes/rand -> 2_000_000 randuri ~ 100 MB RAM
CHUNK_SIZE = 2_000_000

# Prag minim w pentru a include perechea in matrice
W_MIN_THRESHOLD = 0.0

# Progress: afiseaza mesaj la fiecare N chunk-uri
PROGRESS_EVERY = 10

# =============================================================================
# MAIN
# =============================================================================

def build_w_matrix() -> None:
    t0 = time.time()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    print("Titus_build_w_matrix.py  [chunked CSV]")
    print("=" * 60)

    if not TRIPLETS_CSV.exists():
        raise FileNotFoundError(f"Fisier triplete negasit: {TRIPLETS_CSV}")

    file_size_gb = TRIPLETS_CSV.stat().st_size / 1e9
    print(f"Fisier: {TRIPLETS_CSV.name}  ({file_size_gb:.1f} GB)")
    print(f"Chunk size: {CHUNK_SIZE:,} randuri")
    print()

    # ── PASUL 1: colectam codurile distincte de boli ──────────────
    print("Pasul 1/3 — Colectez coduri boli distincte...")
    disease_codes: set[int] = set()
    chunk_idx = 0
    n_rows_total = 0

    for chunk in pd.read_csv(
        TRIPLETS_CSV,
        usecols=["A_code", "B_code"],
        dtype={"A_code": "int32", "B_code": "int32"},
        chunksize=CHUNK_SIZE,
    ):
        disease_codes.update(chunk["A_code"].unique())
        disease_codes.update(chunk["B_code"].unique())
        n_rows_total += len(chunk)
        chunk_idx += 1
        if chunk_idx % PROGRESS_EVERY == 0:
            elapsed = time.time() - t0
            print(f"  chunk {chunk_idx:4d} | randuri={n_rows_total:,} | "
                  f"boli={len(disease_codes)} | {elapsed:.0f}s")

    all_codes = sorted(disease_codes)
    N         = len(all_codes)
    code2idx  = {c: i for i, c in enumerate(all_codes)}
    print(f"  Total randuri: {n_rows_total:,}")
    print(f"  Boli distincte: {N}")
    print()

    # ── PASUL 2: numaram perechile (A, B) ─────────────────────────
    print("Pasul 2/3 — Numar triplete per pereche (D, Di)...")
    count_ab: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    count_a:  dict[int, int]            = defaultdict(int)

    chunk_idx   = 0
    n_rows_proc = 0

    for chunk in pd.read_csv(
        TRIPLETS_CSV,
        usecols=["A_code", "B_code"],
        dtype={"A_code": "int32", "B_code": "int32"},
        chunksize=CHUNK_SIZE,
    ):
        chunk["A_idx"] = chunk["A_code"].map(code2idx)
        chunk["B_idx"] = chunk["B_code"].map(code2idx)
        chunk = chunk.dropna(subset=["A_idx", "B_idx"])
        chunk["A_idx"] = chunk["A_idx"].astype("int32")
        chunk["B_idx"] = chunk["B_idx"].astype("int32")

        pair_counts = chunk.groupby(["A_idx", "B_idx"], sort=False).size()
        for (a, b), cnt in pair_counts.items():
            count_ab[a][b] += int(cnt)

        a_counts = chunk.groupby("A_idx", sort=False).size()
        for a, cnt in a_counts.items():
            count_a[a] += int(cnt)

        n_rows_proc += len(chunk)
        chunk_idx   += 1
        if chunk_idx % PROGRESS_EVERY == 0:
            elapsed = time.time() - t0
            pct = n_rows_proc / n_rows_total * 100 if n_rows_total else 0
            n_pairs_so_far = sum(len(v) for v in count_ab.values())
            print(f"  chunk {chunk_idx:4d} | {pct:5.1f}% | "
                  f"perechi={n_pairs_so_far:,} | {elapsed:.0f}s")

    print(f"  Randuri procesate: {n_rows_proc:,}")
    print(f"  Perechi (A,B) distincte: {sum(len(v) for v in count_ab.values()):,}")
    print()

    # ── PASUL 3: construim si salvam matricea sparsa ───────────────
    print("Pasul 3/3 — Construiesc matricea w(D, Di)...")
    rows, cols, data = [], [], []

    for i, cnt_a in count_a.items():
        if cnt_a == 0:
            continue
        for j, cnt_ab in count_ab[i].items():
            w = cnt_ab / cnt_a
            if w > W_MIN_THRESHOLD:
                rows.append(i)
                cols.append(j)
                data.append(w)

    w_matrix = sp.csr_matrix(
        (np.array(data,  dtype=np.float32),
         (np.array(rows, dtype=np.int32),
          np.array(cols, dtype=np.int32))),
        shape=(N, N)
    )

    w_matrix.setdiag(0)
    w_matrix.eliminate_zeros()

    n_pairs = len(data)
    w_vals  = np.array(data, dtype=np.float32)
    print(f"  Perechi (D,Di) cu w > {W_MIN_THRESHOLD}: {n_pairs:,}")
    print(f"  Densitate: {n_pairs / (N * N) * 100:.3f}%")
    print(f"\n  Statistici w:")
    print(f"    min={w_vals.min():.4f}  max={w_vals.max():.4f}")
    print(f"    mean={w_vals.mean():.4f}  median={float(np.median(w_vals)):.4f}")
    print(f"    w >= 0.5: {int((w_vals >= 0.5).sum()):,}")
    print(f"    w >= 0.8: {int((w_vals >= 0.8).sum()):,}")
    print()

    # ── Salvare ────────────────────────────────────────────────────
    matrix_path  = OUTDIR / "Titus_w_matrix.npz"
    index_path   = OUTDIR / "Titus_w_index.csv"
    summary_path = OUTDIR / "Titus_w_summary.json"

    sp.save_npz(str(matrix_path), w_matrix)
    print(f"Salvat: {matrix_path}")

    name_map: dict[int, str] = {}
    if MALADIES.exists():
        mal_df = pd.read_excel(MALADIES)
        if "CodeMaladie" in mal_df.columns and "NomMaladie" in mal_df.columns:
            name_map = dict(zip(
                mal_df["CodeMaladie"].astype(int),
                mal_df["NomMaladie"].astype(str)
            ))

    pd.DataFrame({
        "row_index"    : list(range(N)),
        "disease_code" : all_codes,
        "disease_name" : [name_map.get(c, str(c)) for c in all_codes],
    }).to_csv(index_path, index=False)
    print(f"Salvat: {index_path}")

    elapsed = time.time() - t0
    summary = {
        "script_name"        : "Titus_build_w_matrix.py",
        "triplets_csv"       : str(TRIPLETS_CSV),
        "n_diseases"         : N,
        "n_rows_total"       : n_rows_total,
        "n_pairs_w"          : n_pairs,
        "matrix_density_pct" : float(round(n_pairs / (N * N) * 100, 4)),
        "w_min"              : float(round(float(w_vals.min()), 6)),
        "w_max"              : float(round(float(w_vals.max()), 6)),
        "w_mean"             : float(round(float(w_vals.mean()), 6)),
        "w_threshold"        : W_MIN_THRESHOLD,
        "chunk_size"         : CHUNK_SIZE,
        "elapsed_sec"        : int(elapsed),
        "elapsed_min"        : round(elapsed / 60, 1),
        "outdir"             : str(OUTDIR),
    }
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(f"Salvat: {summary_path}")
    print(f"\nDurata totala: {int(elapsed)}s  ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    build_w_matrix()