#!/usr/bin/env python3
# Titus_infer_hybrid_v5_r5.py
# Inferenta analitica (cr_engine_v2) + neurala cosinus (v7_r3)
# Suporta modurile: current, lambda_fix, lambda_dyn

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

# CrEngine v2 — in acelasi director
import sys
sys.path.insert(0, str(Path(__file__).parent))
from Titus_cr_engine_v2 import (
    CrEngine, load_tabel2_for_engine, parse_patient_items,
    MODE_CURRENT, MODE_LAMBDA_FIX, MODE_LAMBDA_DYN
)

# =============================================================================
# CONFIGURARE
# =============================================================================

ROOT      = Path(r"D:/MULTIMI_VAGI1/Test11/Test11_Final_OK")
OUTDIR    = ROOT / "out_inference_titus_v7"
#TRAIN_DIR = ROOT / "out_training_latent_v7_r3"
TRAIN_DIR = ROOT / "out_training_latent_v5_r5"
TABEL2_CANDIDATES = [
    ROOT / "data_clean" / "Tabel2_Titus.xlsx",
    ROOT / "data_clean" / "Tabel2.xlsx",
]
MALADIES_CANDIDATES = [
    ROOT / "data_clean" / "Maladies.xlsx",
    ROOT / "Maladies.xlsx",
]

# ── Mod cr analitic ───────────────────────────────────────────────────────────
# MODE_CURRENT    : cr clasic runda 1-3
# MODE_LAMBDA_FIX : faza 4a — penalizare gap discreta (recomandat)
# MODE_LAMBDA_DYN : faza 4b — penalizare gap continua (experimental)
CR_MODE = MODE_LAMBDA_FIX
CR_LAMBDA = 0.3

# ── Mod inferenta ─────────────────────────────────────────────────────────────
# "analytic" | "neural" | "both"
INFER_MODE = "both"

# ── Hyperparametri model v7 ───────────────────────────────────────────────────
EMBED      = 256
ENC_HIDDEN = 256

SPYDER_TOPK              = 10
SPYDER_SUPPORT_THRESHOLD = 0.40

# ── Profiluri pacienti ────────────────────────────────────────────────────────
SPYDER_PATIENT_ROSEOLA = [
    "Sympt:22=150", "Signe:52=150", "Sympt:153=100",
    "Sympt:84=150", "Sympt:35=100", "Signe:138=50",
]
SPYDER_PATIENT_DIABETES = [
    "Sympt:109=150", "Sympt:13=150", "Signe:401=50",
]
SPYDER_PATIENT_CERVICAL = [
    "Sympt:28=150", "Sympt:115=150", "Signe:85=50",
]
SPYDER_PATIENT_PRINZMETAL = [
    "Sympt:42=150", "Sympt:58=100", "Signe:1=150",
]
SPYDER_PATIENT_HYPOTHYROIDISM = [
    "Signe:1=150", "Sympt:142=150", "Sympt:238=100",
]
SPYDER_PATIENT_PARKINSON = [
    "Sympt:97=150", "Sympt:109=150", "Sympt:67=150", "Signe:73=150",
]
SPYDER_PATIENT_CIRRHOSIS = [
    "Signe:63=150", "Signe:79=100", "Signe:50=100",
]
SPYDER_PATIENT_DACOSTA = [
    "Sympt:18=150", "Sympt:23=100", "Signe:51=50",
]

# Profil activ
SPYDER_PATIENT_ITEMS = SPYDER_PATIENT_CERVICAL


# =============================================================================
# ARHITECTURA MODEL v7 (identica cu Titus_train_v7_r3)
# =============================================================================

class Encoder(nn.Module):
    def __init__(self, inp: int, hid: int, emb: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(inp, hid), nn.ReLU(), nn.Linear(hid, emb)
        )
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.normalize(self.net(x), p=2, dim=-1)

class CrPredictor(nn.Module):
    def __init__(self, emb: int, hid: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(emb * 2, hid), nn.ReLU(), nn.Linear(hid, 1), nn.Sigmoid()
        )
    def forward(self, zp, zd):
        return self.net(torch.cat([zp, zd], dim=-1)).squeeze(-1)

class Model(nn.Module):
    def __init__(self, inp: int):
        super().__init__()
        self.enc_p = Encoder(inp, ENC_HIDDEN, EMBED)
        self.enc_d = Encoder(inp, ENC_HIDDEN, EMBED)
        self.predictor = CrPredictor(EMBED, 128)
    def encode_p(self, x): return self.enc_p(x)
    def encode_d(self, x): return self.enc_d(x)
    def cosine_score(self, zp, zd): return (zp * zd).sum(dim=-1)

# =============================================================================
# INFERENTA NEURALA
# =============================================================================

def build_patient_vector(patient_map: Dict[str, float],
                         vocab: Dict[str, int]) -> np.ndarray:
    vec = np.zeros(len(vocab), dtype=np.float32)
    for key, intens in patient_map.items():
        if key in vocab:
            vec[vocab[key]] = intens / 150.0   # normalizare
    return vec

def build_disease_matrix(t2_df: pd.DataFrame, vocab: Dict[str, int],
                         all_codes: List[int]) -> np.ndarray:
    code2row = {c: i for i, c in enumerate(all_codes)}
    X = np.zeros((len(all_codes), len(vocab)), dtype=np.float32)
    for _, row in t2_df.iterrows():
        c = int(row["CodeMaladie"]); k = row["key"]
        if c in code2row and k in vocab:
            X[code2row[c], vocab[k]] = float(row["Score"])
    return X
def neural_scores_v7(patient_map, t2_df, all_codes, device="cpu"):
    model_path = TRAIN_DIR / "Titus_best_model_v5_r5.pt"
    vocab_path = TRAIN_DIR / "Titus_vocab_v5_r5.json"
    emb_path   = TRAIN_DIR / "Titus_disease_embeddings_v5_r5.npy"
    index_path = TRAIN_DIR / "Titus_disease_embeddings_index_v5_r5.csv"

    for p in [model_path, vocab_path, emb_path, index_path]:
        if not p.exists():
            raise FileNotFoundError(f"Negasit: {p}")

    with open(vocab_path, encoding="utf-8") as f:
        vocab = json.load(f)

    emb_matrix = np.load(emb_path)          # (N_boli, EMBED)
    index_df   = pd.read_csv(index_path)

    # row_index = indexul real in emb_matrix pentru fiecare disease_code
    emb_code2row = {
        int(row["disease_code"]): int(row["row_index"])
        for _, row in index_df.iterrows()
    }

    model = Model(len(vocab))
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

    p_vec = build_patient_vector(patient_map, vocab)
    xp_t  = torch.tensor(p_vec, dtype=torch.float32).unsqueeze(0)

    valid_row_indices = []
    valid_positions   = []
    for j, code in enumerate(all_codes):
        c = int(code)
        if c in emb_code2row:
            valid_row_indices.append(emb_code2row[c])
            valid_positions.append(j)

    zd_np = emb_matrix[valid_row_indices]          # (N_valid, EMBED)
    zd_t  = torch.tensor(zd_np, dtype=torch.float32)

    with torch.no_grad():
        zp = model.encode_p(xp_t).expand(len(valid_row_indices), -1)
        scores_valid = model.predictor(zp, zd_t)   # (N_valid,) — sigmoid [0,1]

    scores = np.zeros(len(all_codes), dtype=np.float32)
    scores[valid_positions] = scores_valid.cpu().numpy()
    return scores# =============================================================================
# AFISARE
# =============================================================================

def print_ranking(title: str, chain: List[Tuple], topk: int) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"  {'Rang':<5} {'Code':<8} {'Boala':<45} {'Scor':>10}")
    print(f"  {'-'*4}  {'-'*7}  {'-'*44}  {'-'*10}")
    for rank, (code, name, score) in enumerate(chain[:topk], 1):
        print(f"  {rank:<5} {code:<8} {name:<45} {score:>10.6f}")


# =============================================================================
# MAIN
# =============================================================================

def infer() -> None:
    print(f"Titus_infer_hybrid_v7 | CR_MODE={CR_MODE} λ={CR_LAMBDA} | INFER={INFER_MODE}")
    print("=" * 70)

    OUTDIR.mkdir(parents=True, exist_ok=True)

    tabel2_path = None
    for c in TABEL2_CANDIDATES:
        if c.exists(): tabel2_path = c; break
    if tabel2_path is None:
        raise FileNotFoundError("Tabel2_Titus.xlsx negasit.")

    maladies_path = None
    for c in MALADIES_CANDIDATES:
        if c.exists(): maladies_path = c; break

    patient_map = parse_patient_items(SPYDER_PATIENT_ITEMS)
    masse       = sum(patient_map.values())
    print(f"Profil: {SPYDER_PATIENT_ITEMS}")
    print(f"Masse(P) = {masse}")

    # Tabel2
    t2_df = load_tabel2_for_engine(str(tabel2_path))

    # Nume boli
    disease_name_map: Dict[int, str] = {}
    if maladies_path:
        try:
            mal_df = pd.read_excel(maladies_path)
            if "CodeMaladie" in mal_df.columns and "NomMaladie" in mal_df.columns:
                disease_name_map = dict(zip(
                    mal_df["CodeMaladie"].astype(int), mal_df["NomMaladie"].astype(str)
                ))
        except Exception:
            pass

    # ── ANALITIC cu CrEngine v2 ───────────────────────────────────────────────
    engine    = CrEngine(t2_df, mode=CR_MODE, lam=CR_LAMBDA)
    ranking_a = engine.ranking(patient_map, threshold=SPYDER_SUPPORT_THRESHOLD)

    print(f"\nBoli cu cr >= {SPYDER_SUPPORT_THRESHOLD}: {len(ranking_a)}")

    chain_analytic = [
        (code, disease_name_map.get(code, str(code)), cr)
        for code, cr in ranking_a
    ]

    if INFER_MODE in ("analytic", "both"):
        print_ranking(f"RANKING ANALITIC ({CR_MODE} λ={CR_LAMBDA})", chain_analytic, SPYDER_TOPK)

    # ── NEURAL v7 ─────────────────────────────────────────────────────────────
    chain_neural = []
    if INFER_MODE in ("neural", "both"):
        try:
            all_codes = engine.all_codes
            scores    = neural_scores_v7(patient_map, t2_df, all_codes)
            order_n   = np.argsort(-scores)
            chain_neural = [
                (int(all_codes[i]),
                 disease_name_map.get(int(all_codes[i]), str(all_codes[i])),
                 float(scores[i]))
                for i in order_n
            ]
            print_ranking("RANKING NEURAL v7 (cosinus calibrat)", chain_neural, SPYDER_TOPK)

            if INFER_MODE == "both" and chain_analytic:
                top_a  = {c for c, _, _ in chain_analytic[:SPYDER_TOPK]}
                top_n  = {c for c, _, _ in chain_neural[:SPYDER_TOPK]}
                common = top_a & top_n
                print(f"\n  Concordanta top-{SPYDER_TOPK}: {len(common)}/{SPYDER_TOPK} boli comune")
                for c in sorted(common):
                    print(f"    • {disease_name_map.get(c, str(c))}")

                best_code    = chain_analytic[0][0]
                neural_codes = [c for c, _, _ in chain_neural]
                if best_code in neural_codes:
                    print(f"\n  Boala analitica #1 [{best_code}] "
                          f"{disease_name_map.get(best_code,'?')} "
                          f"-> rang neural: {neural_codes.index(best_code)+1}")

        except FileNotFoundError as e:
            print(f"\n  [NEURAL] {e}")

    # ── SALVARE ───────────────────────────────────────────────────────────────
    if chain_analytic:
        pd.DataFrame([
            {"rank": i+1, "code": c, "name": n, "cr": round(s, 6)}
            for i, (c, n, s) in enumerate(chain_analytic)
        ]).to_csv(OUTDIR / "Titus_v7_topk_analytic.csv", index=False)

    if chain_neural:
        pd.DataFrame([
            {"rank": i+1, "code": c, "name": n, "cosine": round(s, 6)}
            for i, (c, n, s) in enumerate(chain_neural[:100])
        ]).to_csv(OUTDIR / "Titus_v7_topk_neural.csv", index=False)

    with open(OUTDIR / "Titus_v7_summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "patient_items": SPYDER_PATIENT_ITEMS,
            "masse_P"      : float(masse),
            "cr_mode"      : CR_MODE,
            "cr_lambda"    : CR_LAMBDA,
            "infer_mode"   : INFER_MODE,
        }, f, indent=2, ensure_ascii=False)

    print(f"\n  Salvat: {OUTDIR}")


if __name__ == "__main__":
    infer()
