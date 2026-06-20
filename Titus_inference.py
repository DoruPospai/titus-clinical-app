#!/usr/bin/env python3
# Titus_inference.py
# Motor de inferenta diagnostica TITUS
#
# Formula: cr_lambda(D|P) = (overlap - 0.3 * gap) / M(P)
#   overlap = suma scoruri elemente comune P si D
#   gap     = suma scoruri elemente D absente din P
#   M(P)    = suma scoruri elemente P (normalizare)
#
# Ranking final:
#   1. Filtram boli cu cr >= CR_THRESHOLD (0.40)
#   2. Sortam descrescator dupa cr
#   3. Pentru boli cu cr similar (delta <= CR_TIE_DELTA),
#      aplicam w(D, Di) din w-matrix pentru a decide ordinea
#
# Utilizare:
#   python Titus_inference.py
#   (interactiv: introdu elementele pacientului rand pe rand)
#
#   sau import si apel direct:
#   from Titus_inference import TitusEngine
#   engine = TitusEngine()
#   results = engine.diagnose([(8,"Signe",150),(2,"Sympt",100)])

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

# =============================================================================
# CONFIGURARE
# =============================================================================

ROOT       = Path(__file__).resolve().parent
DATA_CLEAN = ROOT / "data_clean"

TABEL2     = DATA_CLEAN / "Tabel2_Titus.xlsx"
W_MATRIX   = ROOT / "out_w_matrix" / "Titus_w_matrix.npz"
W_INDEX    = ROOT / "out_w_matrix" / "Titus_w_matrix_index.csv"

CR_THRESHOLD  = 0.40   # prag minim cr pentru candidati
# Prag dinamic: scade usor pentru profiluri bogate (multi parametri)
# Formula: threshold = CR_THRESHOLD - CR_DYN_SLOPE * max(0, N - CR_DYN_BASE)
# Exemplu cu slope=0.01, base=5: N=10 → prag=0.35; N=13 → prag=0.32
CR_DYN_SLOPE  = 0.010  # reducere per element peste baza
CR_DYN_BASE   = 5      # numar elemente de la care incepe reducerea
LAMBDA        = 0.00   # coeficient penalizare gap (dezactivat — gap nu penalizeaza CR)
CR_TIE_DELTA  = 0.05   # delta maxim pentru a considera boli "la egalitate"
WR_MIN_MATCH_RATIO = 0.35

# ── Risk Factors ─────────────────────────────────────────────────────────────
# RF_LAMBDA: contributia maxima a RF asupra CR semiologic
# Formula: cr_adj = cr_semio + RF_LAMBDA * rf_score * (1 - cr_semio)
# RF_LAMBDA=0.00 → RiskF dezactivat complet din CR
RF_LAMBDA = 0.00   # RiskF NU contribuie la CR — discriminarea RF se face in layerul contextual

# ── Comorbiditate ────────────────────────────────────────────────────────────
# MIN_CR_SINGLE  : CR minim pentru ca o boala sa intre in spatiul de cautare
# MAX_CANDIDATES : nr maxim de boli candidate (performanta — N*(N-1)/2 perechi)
# MIN_IMPROVEMENT: CR_pair trebuie sa depaseasca CR_best cu cel putin acest factor
# MAX_PROFILE_SIM: exclude perechi cu similaritate profil > prag (variante, nu comorbid)
# TOP_N          : cate perechi de returnat
COMORBID_MIN_CR_SINGLE   = 0.25
COMORBID_MAX_CANDIDATES  = 250
COMORBID_MIN_IMPROVEMENT = 1.10
COMORBID_MAX_PROFILE_SIM = 0.70
COMORBID_TOP_N           = 5  # fractie minima din elementele pacientului care trebuie sa coincida cu boala
TOP_N         = 20     # cate rezultate aratam implicit

# =============================================================================
# ENGINE
# =============================================================================

class TitusEngine:
    """Motor de inferenta diagnostica TITUS."""

    def __init__(self) -> None:
        print("Titus Inference Engine — incarcare date...")
        self._load_disease_profiles()
        self._load_w_matrix()
        print(f"  Boli incarcate: {len(self.disease_index)}")
        print(f"  W-matrix shape: {self.w_matrix.shape}")
        # Harti nume elemente pentru explain (Sympt, Signe, RiskF)
        self.symp_map: dict[int, str] = {}
        self.sign_map: dict[int, str] = {}
        self.rf_map:   dict[int, str] = {}
        for path, attr, col_c, col_n in [
            (DATA_CLEAN / "Symptomes.xlsx", "symp_map", "CodeSymptome",  "NomSymptome"),
            (DATA_CLEAN / "Signe.xlsx",     "sign_map", "CodeSigne",     "NomSigne"),
            (DATA_CLEAN / "Riskf.xlsx",     "rf_map",   "CodeFactor",    "NomRiskFactor"),
        ]:
            if path.exists():
                df = pd.read_excel(path)
                if col_c in df.columns and col_n in df.columns:
                    setattr(self, attr, dict(zip(
                        df[col_c].astype(int), df[col_n].astype(str)
                    )))
        print("Gata.\n")

    # ── Incarcare date ────────────────────────────────────────────

    def tabel2_changed(self) -> bool:
        """True daca Tabel2 s-a modificat pe disk de la ultima incarcare."""
        current = TABEL2.stat().st_mtime if TABEL2.exists() else 0
        return current != getattr(self, "_tabel2_mtime", 0)

    def _load_disease_profiles(self) -> None:
        """Incarca Tabel2_Titus.xlsx si construieste profilul fiecarei boli."""
        # Salveaza mtime pentru detectia modificarilor ulterioare
        self._tabel2_mtime = TABEL2.stat().st_mtime if TABEL2.exists() else 0
        df = pd.read_excel(TABEL2, sheet_name="Tabel2")
        ss = df[df["NatureLien"].isin(["Sympt", "Signe"])].copy()

        # Normalizam scorurile (siguranta)
        def _norm(s):
            try:
                s = float(s)
            except Exception:
                return 50
            if s <= 75:  return 50
            if s <= 125: return 100
            return 150

        ss["Score"] = ss["Score"].apply(_norm)

        # Incarcam numele din toate randurile (inclusiv RiskF)
        self.disease_names: dict[int, str] = dict(
            zip(df["CodeMaladie"].astype(int), df["NomMaladie"].astype(str))
        )

        # profile[code] = dict{ (CodeElement, NatureLien) -> score }
        self.profiles: dict[int, dict[tuple[int, str], int]] = {}

        for row in ss.itertuples(index=False):
            code = int(row.CodeMaladie)
            if code not in self.profiles:
                self.profiles[code] = {}
            key = (int(row.CodeElement), str(row.NatureLien))
            self.profiles[code][key] = int(row.Score)

        self.disease_index: list[int] = sorted(self.profiles.keys())

        # rf_profiles[code] = dict{ (CodeElement, "RiskF") -> score }
        rf_rows = df[df["NatureLien"] == "RiskF"].copy()
        rf_rows["Score"] = rf_rows["Score"].apply(_norm)
        self.rf_profiles: dict[int, dict[tuple[int, str], int]] = {}
        for row in rf_rows.itertuples(index=False):
            code = int(row.CodeMaladie)
            if code not in self.rf_profiles:
                self.rf_profiles[code] = {}
            key = (int(row.CodeElement), "RiskF")
            self.rf_profiles[code][key] = int(row.Score)

        # Statut raritate — din Titus_raritate.csv daca exista
        self.rare_diseases: set[int] = set()
        raritate_path = DATA_CLEAN / "Titus_raritate.csv"
        if raritate_path.exists():
            rdf = pd.read_csv(raritate_path)
            if "CodeMaladie" in rdf.columns and "Raritate" in rdf.columns:
                self.rare_diseases = set(
                    rdf[rdf["Raritate"] == "RARE"]["CodeMaladie"].astype(int).tolist()
                )
            print(f"  Boli RARE incarcate: {len(self.rare_diseases)}")

    def _load_w_matrix(self) -> None:
        """Incarca matricea w din format numpy dens (np.savez_compressed)."""
        data = np.load(str(W_MATRIX), allow_pickle=True)
        self.w_matrix: np.ndarray = data["w"].astype(np.float32)
        row_sums = self.w_matrix.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        self.w_matrix_norm = self.w_matrix / row_sums

        if W_INDEX.exists():
            idx_df = pd.read_csv(W_INDEX)
            self.w_row2code: dict[int, int] = dict(
                zip(idx_df["idx"].astype(int), idx_df["code"].astype(int))
            )
        else:
            codes = data["disease_codes"].astype(int)
            self.w_row2code = {i: int(c) for i, c in enumerate(codes)}
        self.w_code2row: dict[int, int] = {v: k for k, v in self.w_row2code.items()}
        nonzero = int(np.count_nonzero(self.w_matrix))
        print(f"  Perechi w(D,Di) non-zero: {nonzero:,}")

    # ── Formula cr ───────────────────────────────────────────────

    def _compute_cr(
        self,
        patient: dict[tuple[int, str], int],
        disease_code: int,
    ) -> float:
        """
        Formula cr_lambda_fix extinsa cu contributia Risk Factors.

        Pas 1 — CR semiologic (Sympt + Signe):
          cr_semio = (overlap - LAMBDA * gap) / M(P_semio)
          gap = sum P[e] unde D[e]=0

        Pas 2 — Boost RF (daca pacientul are elemente RiskF):
          rf_score = overlap_rf / M(P_rf)
          cr_adj   = cr_semio + RF_LAMBDA * rf_score * (1 - cr_semio)
        """
        # Separa elemente semiologice de Risk Factors
        semio = {k: v for k, v in patient.items() if k[1] in ("Sympt", "Signe")}
        rf_p  = {k: v for k, v in patient.items() if k[1] == "RiskF"}

        # ── Pas 1: CR semiologic ──────────────────────────────────────────────
        disease = self.profiles.get(disease_code, {})
        M_semio = sum(semio.values()) if semio else 0

        if M_semio == 0:
            cr_semio = 0.0
        else:
            overlap = gap = 0
            for key, p_score in semio.items():
                d_score = disease.get(key, 0)
                overlap += min(p_score, d_score)
                if d_score == 0:
                    gap += p_score
            cr_semio = (overlap - LAMBDA * gap) / M_semio

        # ── Pas 2: Boost RF ───────────────────────────────────────────────────
        if not rf_p:
            return float(cr_semio)

        rf_disease = self.rf_profiles.get(disease_code, {})
        M_rf = sum(rf_p.values())
        if M_rf == 0:
            return float(cr_semio)

        overlap_rf = sum(
            min(p_score, rf_disease.get(key, 0))
            for key, p_score in rf_p.items()
        )
        rf_score = overlap_rf / M_rf

        # Boost asimptotic: RF adauga cel mult RF_LAMBDA * (1 - cr_semio)
        cr_adj = cr_semio + RF_LAMBDA * rf_score * max(0.0, 1.0 - cr_semio)
        return float(cr_adj)
    # ── Ranking cu w-matrix ───────────────────────────────────────

    def _w_rank(self, candidates: list[tuple[int, float]]) -> list[tuple[int, float]]:
        """
        Sortare finala:
        - Grupeaza boli cu cr similar (delta <= CR_TIE_DELTA)
        - In interiorul grupului, rankeaza dupa w(D, Di) median
        - Grupuri sortate dupa cr descrescator
        """
        if len(candidates) <= 1:
            return candidates

        # Sortam initial dupa cr descrescator
        candidates = sorted(candidates, key=lambda x: x[1], reverse=True)

        # Grupam in "tie groups"
        groups: list[list[tuple[int, float]]] = []
        current_group: list[tuple[int, float]] = [candidates[0]]

        for i in range(1, len(candidates)):
            if current_group[0][1] - candidates[i][1] <= CR_TIE_DELTA:
                current_group.append(candidates[i])
            else:
                groups.append(current_group)
                current_group = [candidates[i]]
        groups.append(current_group)

        # In fiecare grup, sortam dupa w median (cat de mult bate pe ceilalti)
        result: list[tuple[int, float]] = []
        for group in groups:
            if len(group) == 1:
                result.extend(group)
                continue

            codes_in_group = [c for c, _ in group]
            scored = []
            for code, cr in group:
                row = self.w_code2row.get(code)
                if row is None:
                    w_score = 0.0
                else:
                    # w median fata de celelalte boli din grup
                    other_rows = [
                        self.w_code2row[oc]
                        for oc in codes_in_group
                        if oc != code and oc in self.w_code2row
                    ]
                    if other_rows:
                        w_vals = [
                            float(self.w_matrix_norm[row, or_])
                            for or_ in other_rows
                        ]
                        w_score = float(np.mean(w_vals))
                    else:
                        w_score = 0.0
                scored.append((code, cr, w_score))

            # Sortam grup dupa (cr desc, w_score desc)
            scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
            result.extend([(c, cr) for c, cr, _ in scored])

        return result

    # ── Interfata publica ─────────────────────────────────────────

    def _has_cardinal(
        self,
        patient: dict[tuple[int, str], int],
        disease_code: int,
    ) -> bool:
        """True daca profilul pacientului contine cel putin un element cardinal (150) al bolii."""
        disease = self.profiles.get(disease_code, {})
        for key, d_score in disease.items():
            if d_score >= 150 and key in patient:
                return True
        return False

    def diagnose(
        self,
        patient_elements: Sequence[tuple[int, str, int]],
        top_n: int = TOP_N,
        cr_threshold: float = CR_THRESHOLD,
    ) -> list[dict]:
        """
        Parametri:
            patient_elements: lista de (CodeElement, NatureLien, Score)
                              NatureLien: "Sympt" sau "Signe"
                              Score: 50, 100 sau 150
            top_n: numarul maxim de rezultate returnate
            cr_threshold: prag minim cr (default 0.40)

        Returneaza:
            lista de dict cu cheile:
              rank, code, name, cr, cr_class
        """
        # Construim profilul pacientului
        patient: dict[tuple[int, str], int] = {}
        for code_elem, nature, score in patient_elements:
            if nature not in ("Sympt", "Signe", "RiskF"):
                continue
            if score not in (50, 100, 150):
                score = 150 if score > 125 else (100 if score > 75 else 50)
            patient[(int(code_elem), nature)] = int(score)

        if not patient:
            return []

        M_P = sum(patient.values())

        # Verificam legea cardinalelor
        has_cardinal = any(s == 150 for s in patient.values())
        if not has_cardinal:
            print("  ATENTIE: profilul pacientului nu contine niciun element cardinal (150).")
            print("  Rezultatele pot fi nesigure.\n")

        # Prag dinamic — scade usor pentru profiluri bogate
        n_elem = len(patient)
        dynamic_threshold = max(
            cr_threshold - CR_DYN_SLOPE * max(0, n_elem - CR_DYN_BASE),
            cr_threshold * 0.75,   # nu cobori sub 75% din pragul de baza
        )
        if n_elem > CR_DYN_BASE:
            pass  # threshold ajustat silentios

        # Calculam cr pentru toate bolile
        candidates:    list[tuple[int, float]] = []
        waiting_room:  list[dict]              = []

        for code in self.disease_index:
            cr = self._compute_cr(patient, code)

            if cr >= dynamic_threshold:
                candidates.append((code, cr))
            else:
                # WaitingRoom: cr sub prag — criterii stricte pentru a evita false pozitive
                if cr > 0:
                    disease  = self.profiles.get(code, {})
                    M_P_loc  = sum(patient.values()) or 1
                    # Numar elemente comune (matching)
                    matching = [k for k in patient if k in disease]
                    min_req  = max(2, math.ceil(len(patient) * WR_MIN_MATCH_RATIO))
                    if len(matching) < min_req:
                        continue
                    # Cel putin un element comun sa fie cardinal al bolii
                    if not any(disease[k] >= 150 for k in matching):
                        continue
                    overlap = sum(
                        min(p_score, disease.get(key, 0))
                        for key, p_score in patient.items()
                    )
                    is_rare = code in self.rare_diseases
                    waiting_room.append({
                        "code"    : code,
                        "name"    : self.disease_names.get(code, str(code)),
                        "cr"      : round(cr, 4),
                        "overlap" : round(overlap / M_P_loc, 4),
                        "rare"    : is_rare,
                    })

        # Separa RARE si COMMON, sorteaza dupa cr desc in fiecare grup
        wr_rare   = sorted([w for w in waiting_room if     w["rare"]], key=lambda x: -x["cr"])
        wr_common = sorted([w for w in waiting_room if not w["rare"]], key=lambda x: -x["cr"])
        # Cap: 10 RARE + 5 COMMON (suficient pentru context clinic)
        waiting_room = wr_rare[:10] + wr_common[:5]

        if not candidates:
            return {"ranking": [], "waiting_room": waiting_room}

        # Ranking final cu w-matrix
        ranked = self._w_rank(candidates)
        ranked = ranked[:top_n]

        # Formatam rezultatele
        results = []
        for rank, (code, cr) in enumerate(ranked, start=1):
            if cr >= 0.80:   cr_class = "A"
            elif cr >= 0.60: cr_class = "B"
            elif cr >= 0.40: cr_class = "C"
            else:            cr_class = "D"

            disease     = self.profiles.get(code, {})
            overlap_ss  = sum(min(p_score, disease.get(k, 0)) for k, p_score in patient.items())
            results.append({
                "rank"     : rank,
                "code"     : code,
                "name"     : self.disease_names.get(code, str(code)),
                "cr"       : round(cr, 4),
                "cr_class" : cr_class,
                "overlap_ss": overlap_ss,
                "M_P_ss"   : M_P,
            })

        # ── Detectie comorbiditate ────────────────────────────────────
        # Dupa ce avem ranking-ul, verificam daca profilul pacientului
        # ar fi mai bine explicat de 2 diagnostice simultane.
        # Conditie: top2 ambele in clasa A sau B, si CR_sum > CR_top1 * 1.1
        comorbidity = None
        if len(results) >= 2:
            r1, r2 = results[0], results[1]
            if r1["cr"] >= 0.60 and r2["cr"] >= 0.60:
                # Simuleaza: pacientul are D1 + D2
                # Overlap combinat = union elemente D1 U D2
                d1 = self.profiles.get(r1["code"], {})
                d2 = self.profiles.get(r2["code"], {})
                combined = {}
                for k, v in d1.items():
                    combined[k] = v
                for k, v in d2.items():
                    combined[k] = max(combined.get(k, 0), v)

                overlap_c = gap_c = 0
                for key, p_score in patient.items():
                    d_score = combined.get(key, 0)
                    overlap_c += min(p_score, d_score)
                    if d_score == 0:
                        gap_c += p_score

                cr_combined = (overlap_c - LAMBDA * gap_c) / M_P

                # Semnal de comorbiditate: cr_combined > max(cr1, cr2) * 1.05
                if cr_combined > max(r1["cr"], r2["cr"]) * 1.05:
                    comorbidity = {
                        "code_a"     : r1["code"],
                        "name_a"     : r1["name"],
                        "cr_a"       : r1["cr"],
                        "code_b"     : r2["code"],
                        "name_b"     : r2["name"],
                        "cr_b"       : r2["cr"],
                        "cr_combined": round(cr_combined, 4),
                    }

        return {"ranking": results, "waiting_room": waiting_room,
                "comorbidity": comorbidity}

    def print_results(self, results) -> None:
        """Afiseaza rezultatele formatat. Accepta dict {ranking, waiting_room} sau lista."""
        if isinstance(results, list):
            ranking      = results
            waiting_room = []
        else:
            ranking      = results.get("ranking", [])
            waiting_room = results.get("waiting_room", [])

        # ── Ranking activ ─────────────────────────────────────────
        if not ranking:
            print("  Niciun candidat gasit (cr >= threshold).")
        else:
            print(f"\n  {'Rank':<4} {'Cls':<4} {'CR':>7}  {'Cod':<6} {'Boala'}")
            print("  " + "-" * 62)
            for r in ranking:
                print(f"  {r['rank']:<4} [{r['cr_class']}]  {r['cr']:>6.4f}"
                      f"  {r['code']:<6} {r['name']}")

        # ── Waiting Room ──────────────────────────────────────────
        if waiting_room:
            wr_rare   = [w for w in waiting_room if     w["rare"]]
            wr_common = [w for w in waiting_room if not w["rare"]]

            print(f"\n  ┌─ WAITING ROOM "
                  f"({len(wr_rare)} RARE  +  {len(wr_common)} COMMON) ─────────────────┐")
            print(f"  │  {'Tip':<6} {'CR':>7}  {'Overlap':>8}  {'Cod':<6} {'Boala'}")
            print(f"  │  " + "-" * 56)

            for w in wr_rare:
                print(f"  │  {'RARE':<6} {w['cr']:>6.4f}  {w['overlap']:>8.4f}"
                      f"  {w['code']:<6} {w['name']}")

            if wr_rare and wr_common:
                print(f"  │  " + "·" * 40)

            for w in wr_common:
                print(f"  │  {'COMMON':<6} {w['cr']:>6.4f}  {w['overlap']:>8.4f}"
                      f"  {w['code']:<6} {w['name']}")

            print(f"  └" + "─" * 60)

        # ── Comorbiditate ─────────────────────────────────────────────
        comorbidity = results.get("comorbidity") if isinstance(results, dict) else None
        if comorbidity:
            print(f"  ⚠  POSIBILA COMORBIDITATE detectata:")
            print(f"     {comorbidity['name_a']} (cr={comorbidity['cr_a']:.4f})")
            print(f"  +  {comorbidity['name_b']} (cr={comorbidity['cr_b']:.4f})")
            print(f"     CR combinat: {comorbidity['cr_combined']:.4f} "
                  f"(superior celui mai bun diagnostic individual)")
            print()

        print()


    def explain(
        self,
        patient: dict[tuple[int, str], int],
        disease_code: int,
    ) -> dict:
        """
        Explicatie detaliata a cr pentru boala data.
        Returneaza: present, gap, absent_d, breakdown.
        """
        disease = self.profiles.get(disease_code, {})
        M_P     = sum(patient.values()) or 1

        present  = []
        gap_list = []
        absent_d = []
        overlap_total = 0
        gap_total     = 0

        for key, p_score in patient.items():
            d_score = disease.get(key, 0)
            if d_score > 0:
                contrib = min(p_score, d_score)
                overlap_total += contrib
                present.append({
                    "key": key, "p_score": p_score,
                    "d_score": d_score, "contrib": contrib,
                    "cardinal": d_score >= 150,
                })
            else:
                gap_total += p_score
                gap_list.append({
                    "key": key, "p_score": p_score,
                    "penalty": round(LAMBDA * p_score, 1),
                })

        for key, d_score in disease.items():
            if key not in patient:
                absent_d.append({
                    "key": key, "d_score": d_score,
                    "cardinal": d_score >= 150,
                })

        cr = (overlap_total - LAMBDA * gap_total) / M_P
        if cr >= 0.80:   cr_class = "A"
        elif cr >= 0.60: cr_class = "B"
        elif cr >= 0.40: cr_class = "C"
        else:            cr_class = "D"

        present.sort(key=lambda x: (-x["cardinal"], -x["d_score"]))
        absent_d.sort(key=lambda x: (-x["cardinal"], -x["d_score"]))

        return {
            "code": disease_code,
            "name": self.disease_names.get(disease_code, str(disease_code)),
            "cr": round(cr, 4), "cr_class": cr_class,
            "present": present, "gap": gap_list,
            "absent_d": absent_d[:8],
            "n_disease_total": len(disease),
            "breakdown": {
                "overlap": overlap_total, "gap": gap_total,
                "M_P": M_P, "penalty": round(LAMBDA * gap_total, 1),
                "cr": round(cr, 4),
            },
        }

    def print_explain(self, expl: dict) -> None:
        """Afiseaza explicatia in format clinic narativ."""

        def ename(key):
            code, nature = key
            if nature == "Sympt":
                nm = self.symp_map.get(code)
            elif nature == "Signe":
                nm = self.sign_map.get(code)
            else:  # RiskF
                nm = self.rf_map.get(code)
            return nm.title() if nm else f"{nature}:{code}"

        bd       = expl["breakdown"]
        present  = expl["present"]
        gap      = expl["gap"]
        absent_d = expl["absent_d"]
        n_total  = expl["n_disease_total"]
        cr       = expl["cr"]
        cls      = expl["cr_class"]
        name     = expl["name"]

        cardinals_present     = [e for e in present if e["cardinal"]]
        non_cardinals_present = [e for e in present if not e["cardinal"]]
        cardinals_absent_d    = [e for e in absent_d if e["cardinal"]]
        non_cardinals_absent_d= [e for e in absent_d if not e["cardinal"]]

        print(f"\n  ╔══ {name}  [Cls {cls}  cr={cr:.2f}] ══")

        # 1. Sinteza
        if cr == 1.0:
            print(f"  ║  Potrivire perfecta — toate simptomele pacientului")
            print(f"  ║  sunt prezente in aceasta boala, fara penalizari.")
        elif cr >= 0.80:
            print(f"  ║  Potrivire foarte buna — profilul pacientului")
            print(f"  ║  corespunde in mare masura acestei boli.")
        elif cr >= 0.60:
            print(f"  ║  Potrivire buna — diagnosticul este plauzibil,")
            print(f"  ║  cu rezerve moderate.")
        elif cr >= 0.40:
            print(f"  ║  Potrivire partiala — diagnosticul posibil,")
            print(f"  ║  dar profilul clinic este incomplet.")
        print(f"  ║")

        # 2. Elemente comune
        if cardinals_present:
            nms = ", ".join(ename(e["key"]) for e in cardinals_present)
            print(f"  ║  Simptome cardinale confirmate ({len(cardinals_present)}):")
            print(f"  ║    {nms}")
        if non_cardinals_present:
            nms = ", ".join(ename(e["key"]) for e in non_cardinals_present)
            print(f"  ║  Simptome secundare confirmate ({len(non_cardinals_present)}):")
            print(f"  ║    {nms}")

        # 3. Gap — penalizari
        if gap:
            print(f"  ║")
            nms = ", ".join(ename(e["key"]) for e in gap)
            print(f"  ║  Simptome ale pacientului absente din aceasta boala")
            print(f"  ║  (penalizeaza scorul):")
            print(f"  ║    {nms}")
            pen_pct = round(bd['penalty'] / bd['M_P'] * 100)
            print(f"  ║  Penalizare totala: {pen_pct}% din scorul maxim posibil.")
        else:
            print(f"  ║  Nicio penalizare — toate simptomele pacientului")
            print(f"  ║  sunt compatibile cu aceasta boala.")

        # 4. Ce lipseste din profil — sugestii
        if cardinals_absent_d:
            print(f"  ║")
            print(f"  ║  Simptome cardinale ale bolii NECONFIRMATE inca")
            print(f"  ║  (prezenta lor ar intari diagnosticul):")
            for e in cardinals_absent_d[:4]:
                print(f"  ║    → {ename(e['key'])}")
        if non_cardinals_absent_d:
            nms = ", ".join(ename(e["key"]) for e in non_cardinals_absent_d[:3])
            print(f"  ║  Alte simptome posibile ale bolii: {nms}")
            if n_total - len(present) > 8:
                print(f"  ║  (si alte {n_total - len(present) - len(absent_d)} simptome)")

        print(f"  ╚{'═' * 52}\n")


    def suggest(
        self,
        patient: dict[tuple[int, str], int],
        ranking: list[dict],
        top_diseases: int = 3,
        top_suggestions: int = 5,
    ) -> list[dict]:
        """
        Sugereaza elementele care ar diferentia cel mai bine primele
        top_diseases diagnostice din ranking.

        Pentru fiecare element absent din profilul pacientului:
          - Simuleaza adaugarea lui la scor 150, 100, 50
          - Calculeaza delta_cr = cr_nou(D1) - cr_nou(D2) pentru fiecare pereche
          - Scorul de discriminare = sum(abs(delta_cr)) peste toate perechile
        Returneaza elementele cu discriminare maxima.
        """
        if not ranking:
            return []

        top = ranking[:top_diseases]
        top_codes = [r["code"] for r in top]

        # Colecteaza toate elementele din bolile top care nu sunt in pacient
        candidates: dict[tuple[int, str], set] = {}
        for code in top_codes:
            disease = self.profiles.get(code, {})
            for key, d_score in disease.items():
                if key not in patient:
                    if key not in candidates:
                        candidates[key] = set()
                    candidates[key].add(code)

        M_P = sum(patient.values())

        # Perechi de diagnostice pentru comparatie
        pairs = []
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                pairs.append((top_codes[i], top_codes[j]))

        # Scor CR curent pentru fiecare boala top
        cr_current = {code: self._compute_cr(patient, code) for code in top_codes}

        results = []
        for key, in_diseases in candidates.items():
            # Testeaza cu scor 150 (cel mai informativ)
            patient_aug = dict(patient)
            patient_aug[key] = 150
            M_aug = sum(patient_aug.values())

            # CR augmentat pentru fiecare boala top
            cr_aug = {}
            for code in top_codes:
                disease = self.profiles.get(code, {})
                overlap = gap = 0
                for k, p_sc in patient_aug.items():
                    d_sc = disease.get(k, 0)
                    overlap += min(p_sc, d_sc)
                    if d_sc == 0:
                        gap += p_sc
                cr_aug[code] = (overlap - LAMBDA * gap) / M_aug

            # Discriminare = sum |delta_cr| su tutte le coppie
            discriminare = 0.0
            for c1, c2 in pairs:
                delta_now = cr_current[c1] - cr_current[c2]
                delta_aug = cr_aug[c1]     - cr_aug[c2]
                # Bonus daca delta creste (diferentiaza mai bine)
                discriminare += abs(delta_aug - delta_now)
                # Bonus suplimentar daca schimba ordinea
                if (delta_now >= 0) != (delta_aug >= 0):
                    discriminare += 0.2

            # Prezenta in bolile top
            coverage = len(in_diseases) / len(top_codes)
            # Scor final
            final_score = discriminare * (0.7 + 0.3 * coverage)

            if final_score > 0.001:
                # Determina in ce boli apare
                in_names = [
                    self.disease_names.get(c, str(c))
                    for c in top_codes if c in in_diseases
                ]
                absent_names = [
                    self.disease_names.get(c, str(c))
                    for c in top_codes if c not in in_diseases
                ]
                results.append({
                    "key"          : key,
                    "score"        : round(final_score, 4),
                    "cr_delta"     : {c: round(cr_aug[c] - cr_current[c], 4)
                                      for c in top_codes},
                    "present_in"   : in_names,
                    "absent_in"    : absent_names,
                })

        results.sort(key=lambda x: -x["score"])
        return results[:top_suggestions]

    def print_suggest(self, suggestions: list[dict], ranking: list[dict],
                      top_diseases: int = 3) -> None:
        """Afiseaza sugestiile de simptome in format narativ."""

        def ename(key):
            code, nature = key
            if nature == "Sympt":
                nm = self.symp_map.get(code)
            elif nature == "Signe":
                nm = self.sign_map.get(code)
            else:  # RiskF
                nm = self.rf_map.get(code)
            return nm.title() if nm else f"{nature}:{code}"

        top = ranking[:top_diseases]
        names = [r["name"] for r in top]

        print(f"\n  ╔══ Sugestii pentru diferentierea primelor {len(top)} diagnostice ══")
        if len(top) > 1:
            print(f"  ║  Comparand: {' vs '.join(names)}")
        print(f"  ║")

        if not suggestions:
            print(f"  ║  Nu exista simptome discriminante suplimentare.")
            print(f"  ╚{'═' * 52}\n")
            return

        print(f"  ║  Adaugand unul din urmatoarele simptome, diagnosticul")
        print(f"  ║  ar deveni mai clar:")
        print(f"  ║")

        for i, s in enumerate(suggestions, 1):
            key_name = ename(s["key"])
            code, nature = s["key"]

            # Explica impactul
            present_in = s["present_in"]
            absent_in  = s["absent_in"]

            if present_in and absent_in:
                impact = (f"prezent in {', '.join(present_in[:2])}; "
                          f"absent in {', '.join(absent_in[:2])}")
            elif present_in:
                impact = f"prezent in toate: {', '.join(present_in[:2])}"
            else:
                impact = "diferentiaza prin scor"

            # Delta CR
            deltas = s["cr_delta"]
            delta_str = "  ".join(
                f"{self.disease_names.get(c, str(c)).split()[0]} "
                f"{'▲' if d > 0 else '▼'}{abs(d):.2f}"
                for c, d in deltas.items()
            )

            print(f"  ║  {i}. {key_name}  ({nature} {code})")
            print(f"  ║     {impact}")
            print(f"  ║     Impact CR: {delta_str}")
            print(f"  ║")

        print(f"  ╚{'═' * 52}\n")


    def why(
        self,
        patient: dict[tuple[int, str], int],
        code_a: int,
        code_b: int,
    ) -> None:
        """Explica de ce boala A e inaintea bolii B in ranking."""

        def ename(key):
            code, nature = key
            if nature == "Sympt":
                nm = self.symp_map.get(code)
            elif nature == "Signe":
                nm = self.sign_map.get(code)
            else:  # RiskF
                nm = self.rf_map.get(code)
            return nm.title() if nm else f"{nature}:{code}"

        expl_a = self.explain(patient, code_a)
        expl_b = self.explain(patient, code_b)
        name_a = expl_a["name"]
        name_b = expl_b["name"]
        cr_a   = expl_a["cr"]
        cr_b   = expl_b["cr"]

        print(f"\n  ╔══ De ce {name_a} > {name_b} ? ══")
        print(f"  ║  CR {name_a}: {cr_a:.4f}  vs  CR {name_b}: {cr_b:.4f}  "
              f"(diferenta: +{cr_a - cr_b:.4f})")
        print(f"  ║")

        # Elemente prezente in A dar absente in B
        keys_in_a = {e["key"] for e in expl_a["present"]}
        keys_in_b = {e["key"] for e in expl_b["present"]}

        advantage_a = keys_in_a - keys_in_b
        advantage_b = keys_in_b - keys_in_a
        common      = keys_in_a & keys_in_b

        if advantage_a:
            nms = ", ".join(ename(k) for k in advantage_a)
            print(f"  ║  Avantaj {name_a.split()[0]}:")
            print(f"  ║    Simptome prezente in A, absente in B: {nms}")

        if advantage_b:
            nms = ", ".join(ename(k) for k in advantage_b)
            print(f"  ║  Avantaj {name_b.split()[0]}:")
            print(f"  ║    Simptome prezente in B, absente in A: {nms}")

        if common:
            nms = ", ".join(ename(k) for k in common)
            print(f"  ║  Comune ambelor: {nms}")

        # Gap comparison
        gap_a = sum(e["penalty"] for e in expl_a["gap"])
        gap_b = sum(e["penalty"] for e in expl_b["gap"])
        if gap_a != gap_b:
            print(f"  ║")
            print(f"  ║  Penalizare gap: {name_a.split()[0]}={gap_a:.0f}  "
                  f"{name_b.split()[0]}={gap_b:.0f}")
            if gap_a < gap_b:
                print(f"  ║  → {name_a} penalizat mai putin "
                      f"(simptomele pacientului mai compatibile)")
            else:
                print(f"  ║  → {name_b} penalizat mai putin, dar cr mai mic "
                      f"(overlap insuficient)")

        # W-matrix contribution
        row_a = self.w_code2row.get(code_a)
        row_b = self.w_code2row.get(code_b)
        if row_a is not None and row_b is not None:
            w_ab = float(self.w_matrix_norm[row_a, row_b])
            w_ba = float(self.w_matrix_norm[row_b, row_a])
            print(f"  ║")
            print(f"  ║  W-matrix: {name_a.split()[0]} bate {name_b.split()[0]}"
                  f" in {w_ab*100:.1f}% din cazuri")
            print(f"  ║           {name_b.split()[0]} bate {name_a.split()[0]}"
                  f" in {w_ba*100:.1f}% din cazuri")

        print(f"  ╚{'═' * 52}\n")


    def comorbid(
        self,
        patient: dict[tuple[int, str], int],
        min_cr_single:   float = COMORBID_MIN_CR_SINGLE,
        max_candidates:  int   = COMORBID_MAX_CANDIDATES,
        min_improvement: float = COMORBID_MIN_IMPROVEMENT,
        max_profile_sim: float = COMORBID_MAX_PROFILE_SIM,
        top_n:           int   = COMORBID_TOP_N,
    ) -> dict:
        """
        Cauta activ cea mai buna pereche (D1, D2) care explica profilul
        pacientului mai bine decat orice diagnostic singular.

        Algoritm:
          1. Filtreaza bolile cu CR >= min_cr_single → candidati
          2. Limiteaza la max_candidates (sortati dupa CR desc)
          3. Pentru fiecare pereche: calculeaza CR_pair fata de union(D1, D2)
          4. Exclude perechile prea similare (pot fi variante ale aceleiasi boli)
          5. Returneaza top_n perechi cu CR_pair maxim si imbunatatire >= min_improvement
        """
        import itertools

        M_P = sum(patient.values()) or 1

        # Pasul 1+2: candidati
        scored = []
        for code in self.disease_index:
            cr = self._compute_cr(patient, code)
            if cr >= min_cr_single:
                scored.append((code, cr))
        scored.sort(key=lambda x: -x[1])
        scored = scored[:max_candidates]

        best_single_cr = scored[0][1] if scored else 0.0
        threshold_pair = best_single_cr * min_improvement

        # Pasul 3+4: perechi
        results = []
        codes = [c for c, _ in scored]

        for (code_a, cr_a), (code_b, cr_b) in itertools.combinations(scored, 2):
            # Similaritate profile (Jaccard pe chei)
            da = set(self.profiles.get(code_a, {}).keys())
            db = set(self.profiles.get(code_b, {}).keys())
            if da and db:
                sim = len(da & db) / len(da | db)
                if sim > max_profile_sim:
                    continue  # variante ale aceleiasi boli

            # CR combinat fata de uniunea profilelelor
            disease_a = self.profiles.get(code_a, {})
            disease_b = self.profiles.get(code_b, {})
            combined  = {}
            for k, v in disease_a.items():
                combined[k] = v
            for k, v in disease_b.items():
                combined[k] = max(combined.get(k, 0), v)

            overlap_c = gap_c = 0
            for key, p_score in patient.items():
                d_score = combined.get(key, 0)
                overlap_c += min(p_score, d_score)
                if d_score == 0:
                    gap_c += p_score

            cr_pair = (overlap_c - LAMBDA * gap_c) / M_P

            if cr_pair < threshold_pair:
                continue

            # Atribuire simptome pacient: D1, D2, ambele, niciuna
            only_a = []   # in D1, nu in D2
            only_b = []   # in D2, nu in D1
            both   = []   # in ambele
            none_  = []   # in niciuna

            for key, p_score in patient.items():
                in_a = key in disease_a
                in_b = key in disease_b
                if in_a and in_b:
                    both.append(key)
                elif in_a:
                    only_a.append(key)
                elif in_b:
                    only_b.append(key)
                else:
                    none_.append(key)

            results.append({
                "code_a"     : code_a,
                "name_a"     : self.disease_names.get(code_a, str(code_a)),
                "cr_a"       : round(cr_a, 4),
                "code_b"     : code_b,
                "name_b"     : self.disease_names.get(code_b, str(code_b)),
                "cr_b"       : round(cr_b, 4),
                "cr_pair"    : round(cr_pair, 4),
                "improvement": round((cr_pair / best_single_cr - 1) * 100, 1),
                "sim"        : round(sim if da and db else 0.0, 3),
                "only_a"     : only_a,
                "only_b"     : only_b,
                "both"       : both,
                "unexplained": none_,
            })

        results.sort(key=lambda x: -x["cr_pair"])

        return {
            "best_single_cr" : round(best_single_cr, 4),
            "n_candidates"   : len(scored),
            "n_pairs_tested" : len(results) + (len(scored) * (len(scored)-1) // 2 - len(results)),
            "pairs"          : results[:top_n],
            "params"         : {
                "min_cr_single"  : min_cr_single,
                "max_candidates" : max_candidates,
                "min_improvement": min_improvement,
                "max_profile_sim": max_profile_sim,
            },
        }

    def print_comorbid(self, result: dict) -> None:
        """Afiseaza rezultatele cautarii de comorbiditate in format narativ."""

        def ename(key):
            code, nature = key
            if nature == "Sympt":
                nm = self.symp_map.get(code)
            elif nature == "Signe":
                nm = self.sign_map.get(code)
            else:  # RiskF
                nm = self.rf_map.get(code)
            return nm.title() if nm else f"{nature}:{code}"

        pairs  = result["pairs"]
        params = result["params"]

        print(f"\n  ╔══ Cautare comorbiditate ══")
        print(f"  ║  Candidati analizati: {result['n_candidates']}")
        print(f"  ║  Cel mai bun diagnostic singular: cr={result['best_single_cr']:.4f}")
        print(f"  ║  Imbunatatire minima ceruta: {params['min_improvement']*100-100:.0f}%")
        print(f"  ║")

        if not pairs:
            print(f"  ║  Nicio comorbiditate semnificativa detectata.")
            print(f"  ║  Profilul pacientului este explicat bine de un singur diagnostic.")
            print(f"  ╚{'═' * 52}\n")
            return

        print(f"  ║  {len(pairs)} pereche(i) semnificative gasite:")

        for i, p in enumerate(pairs, 1):
            impr = p["improvement"]
            print(f"  ║")
            print(f"  ║  {'─'*48}")
            print(f"  ║  #{i}  {p['name_a']}  +  {p['name_b']}")
            print(f"  ║      CR individual: {p['cr_a']:.4f} / {p['cr_b']:.4f}")
            print(f"  ║      CR combinat:   {p['cr_pair']:.4f}  "
                  f"(+{impr:.1f}% fata de cel mai bun singular)")

            if p["only_a"]:
                nms = ", ".join(ename(k) for k in p["only_a"])
                print(f"  ║      Simptome explicate de {p['name_a'].split()[0]}: {nms}")
            if p["only_b"]:
                nms = ", ".join(ename(k) for k in p["only_b"])
                print(f"  ║      Simptome explicate de {p['name_b'].split()[0]}: {nms}")
            if p["both"]:
                nms = ", ".join(ename(k) for k in p["both"])
                print(f"  ║      Simptome comune ambelor: {nms}")
            if p["unexplained"]:
                nms = ", ".join(ename(k) for k in p["unexplained"])
                print(f"  ║      Inca neexplicate: {nms}")

        print(f"  ╚{'═' * 52}\n")


# =============================================================================
# MOD INTERACTIV
# =============================================================================

def interactive_session(engine: TitusEngine) -> None:
    """Sesiune interactiva: utilizatorul introduce elementele pacientului."""
    print("=" * 60)
    print("TITUS — Sesiune diagnostica interactiva")
    print("=" * 60)
    print("Introdu elementele pacientului in formatul:")
    print("  CodeElement NatureLien Score")
    print("  ex: 8 Signe 150")
    print("  ex: 2 Sympt 100")
    print()
    print("Comenzi speciale:")
    print("  run          — calculeaza diagnosticul")
    print("  explain N    — explica de ce boala cu rank N e pe acea pozitie")
    print("  suggest [N]  — sugereaza simptome pentru a diferentia primele N diagnostice")
    print("  why N M      — explica de ce boala N e inaintea bolii M")
    print("  top N        — reafiseaza ranking cu primele N rezultate")
    print("  save [file]  — salveaza sesiunea curenta in JSON")
    print("  load [file]  — incarca sesiunea din JSON")
    print("  export [f]   — exporta profil + rezultate + explicatii in text")
    print("  comorbid [N] [min_cr] [min_impr] — cauta comorbiditate")
    print("  list         — afiseaza elementele curente numerotate")
    print("  remove N     — sterge elementul cu numarul N din lista")
    print("  clear        — sterge tot profilul")
    print("  quit         — iesire")
    print()

    elements:        list[tuple[int, str, int]] = []
    last_results:    dict | None                  = None
    current_patient: dict                         = {}

    while True:
        try:
            line = input("Element> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nIesire.")
            break

        if not line:
            continue

        cmd = line.lower()

        if cmd == "quit":
            break

        elif cmd.startswith("top "):
            parts = cmd.split()
            if len(parts) == 2 and parts[1].isdigit():
                new_top = int(parts[1])
                if last_results is not None:
                    # Re-afiseaza cu noul top_n
                    trimmed = dict(last_results)
                    trimmed["ranking"] = last_results["ranking"][:new_top]
                    engine.print_results(trimmed)
                else:
                    print(f"  Ruleaza mai intai run.\n")
            else:
                print("  Folosire: top N  (ex: top 5)\n")

        elif cmd.startswith("save"):
            import json as _json
            parts = cmd.split()
            fname = parts[1] if len(parts) > 1 else "titus_session.json"
            if not fname.endswith(".json"):
                fname += ".json"
            session = {
                "elements": [
                    {"code": ce, "nature": nl, "score": sc}
                    for ce, nl, sc in elements
                ],
                "results": last_results,
            }
            with open(fname, "w", encoding="utf-8") as fj:
                _json.dump(session, fj, indent=2, ensure_ascii=False)
            print(f"  Sesiune salvata in: {fname}\n")

        elif cmd.startswith("load"):
            import json as _json
            parts = cmd.split()
            fname = parts[1] if len(parts) > 1 else "titus_session.json"
            try:
                with open(fname, encoding="utf-8") as fj:
                    session = _json.load(fj)
                elements = [
                    (e["code"], e["nature"], e["score"])
                    for e in session.get("elements", [])
                ]
                last_results    = session.get("results")
                current_patient = {(int(ce), nl): int(sc) for ce, nl, sc in elements}
                print(f"  Sesiune incarcata: {len(elements)} elemente.\n")
                if last_results:
                    engine.print_results(last_results)
            except FileNotFoundError:
                print(f"  Fisier negasit: {fname}\n")
            except Exception as ex:
                print(f"  Eroare la incarcare: {ex}\n")

        elif cmd.startswith("export"):
            import json as _json
            parts = cmd.split()
            fname = parts[1] if len(parts) > 1 else "titus_export.txt"
            lines = []
            lines.append("TITUS — Export sesiune")
            lines.append("=" * 60)
            lines.append(f"Profil pacient ({len(elements)} elemente):")
            for ce, nl, sc in elements:
                lines.append(f"  {nl:<6} {ce:>4}  {sc}")
            if last_results:
                lines.append("")
                lines.append("Ranking:")
                for r in last_results.get("ranking", []):
                    rank = r["rank"]; cls = r["cr_class"]
                    cr   = r["cr"];   nm  = r["name"]
                    lines.append(f"  {rank:>2}. [{cls}] cr={cr:.4f}  {nm}")
                wr = last_results.get("waiting_room", [])
                if wr:
                    lines.append("")
                    lines.append("Waiting Room:")
                    for w in wr:
                        flag = "RARE  " if w["rare"] else "COMMON"
                        wcr  = w["cr"]; wnm = w["name"]
                        lines.append(f"  {flag}  cr={wcr:.4f}  {wnm}")
                lines.append("")
                lines.append("Explicatii top 5:")
                for r in last_results.get("ranking", [])[:5]:
                    expl = engine.explain(current_patient, r["code"])
                    bd   = expl["breakdown"]
                    rank = r["rank"]; nm = r["name"]; cr = r["cr"]
                    lines.append(f"  {rank:>2}. {nm}  cr={cr:.4f}")
                    if expl["gap"]:
                        pen = bd["penalty"]; mp = bd["M_P"]
                        lines.append(f"      Penalizare: {pen:.0f} / {mp}")
            with open(fname, "w", encoding="utf-8") as ft:
                ft.write("\n".join(lines))
            print(f"  Export salvat in: {fname}\n")

        elif cmd.startswith("why "):
            parts = cmd.split()
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                if last_results is None:
                    print("  Ruleaza mai intai \'run\'.\n")
                else:
                    ra, rb   = int(parts[1]), int(parts[2])
                    ranking  = last_results.get("ranking", [])
                    match_a  = next((r for r in ranking if r["rank"] == ra), None)
                    match_b  = next((r for r in ranking if r["rank"] == rb), None)
                    if match_a and match_b:
                        engine.why(current_patient, match_a["code"], match_b["code"])
                    else:
                        print(f"  Rank invalid. Alege doua rank-uri din ultimul run.\n")
            else:
                print("  Folosire: why N M  (ex: why 1 2)\n")

        elif cmd == "clear":
            elements = []
            print("  Profil sters.\n")

        elif cmd == "list":
            if not elements:
                print("  Profil gol.\n")
            else:
                print(f"  Profil curent ({len(elements)} elemente):")
                for i, (ce, nl, sc) in enumerate(elements, 1):
                    print(f"    {i:>2}. {nl:<6} {ce:>4} [{sc}]")
                print()

        elif cmd.startswith("remove "):
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    n = int(parts[1])
                    if 1 <= n <= len(elements):
                        removed = elements.pop(n - 1)
                        print(f"  Sters: {removed[1]} {removed[0]} [{removed[2]}]  "
                              f"(ramas: {len(elements)} elem)\n")
                    else:
                        print(f"  Numar invalid. Foloseste 'list' pentru a vedea lista.\n")
                except ValueError:
                    print("  Format: remove N  (ex: remove 3)\n")
            else:
                print("  Format: remove N  (ex: remove 3)\n")

        elif cmd.startswith("comorbid"):
            if last_results is None:
                print("  Ruleaza mai intai 'run'.\n")
            elif not current_patient:
                print("  Profil gol.\n")
            else:
                # Parametri optionali: comorbid [top_n] [min_cr] [min_impr]
                parts  = cmd.split()
                kwargs = {}
                if len(parts) >= 2 and parts[1].isdigit():
                    kwargs["top_n"] = int(parts[1])
                if len(parts) >= 3:
                    try: kwargs["min_cr_single"] = float(parts[2])
                    except: pass
                if len(parts) >= 4:
                    try: kwargs["min_improvement"] = float(parts[3])
                    except: pass
                result = engine.comorbid(current_patient, **kwargs)
                engine.print_comorbid(result)

        elif cmd.startswith("suggest"):
            parts = cmd.split()
            n_top = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
            if last_results is None:
                print("  Ruleaza mai intai 'run'.\n")
            elif not last_results.get("ranking"):
                print("  Niciun candidat in ranking.\n")
            else:
                suggestions = engine.suggest(
                    current_patient, last_results["ranking"], top_diseases=n_top
                )
                engine.print_suggest(suggestions, last_results["ranking"], n_top)

        elif cmd.startswith("explain"):
            parts = cmd.split()
            if len(parts) < 2 or not parts[1].isdigit():
                print("  Folosire: explain N  (N = rank din ultimul run)\n")
            elif last_results is None:
                print("  Ruleaza mai intai 'run'.\n")
            else:
                rank_req = int(parts[1])
                ranking  = last_results.get("ranking", [])
                match    = next((r for r in ranking if r["rank"] == rank_req), None)
                if match is None:
                    print(f"  Rank {rank_req} nu exista in ultimul rezultat.\n")
                else:
                    expl = engine.explain(current_patient, match["code"])
                    engine.print_explain(expl)

        elif cmd == "run":
            if not elements:
                print("  Niciun element introdus.\n")
                continue
            print(f"\n  Profil pacient ({len(elements)} elemente):")
            for ce, nl, sc in elements:
                print(f"    {nl:<6} {ce:>4}  {sc}")
            print()
            last_results    = engine.diagnose(elements)
            current_patient = {(int(ce), nl): int(sc) for ce, nl, sc in elements}
            engine.print_results(last_results)

        else:
            parts = line.split()
            if len(parts) == 3:
                try:
                    ce    = int(parts[0])
                    nl    = parts[1].capitalize()
                    score = int(parts[2])
                    if nl not in ("Sympt", "Signe", "RiskF"):
                        print(f"  NatureLien invalid: '{nl}'. Foloseste Sympt, Signe sau RiskF.")
                        continue
                    if score not in (50, 100, 150):
                        print(f"  Score invalid: {score}. Foloseste 50, 100 sau 150.")
                        continue
                    elements.append((ce, nl, score))
                    print(f"  + {nl} {ce} [{score}]  (total: {len(elements)} elem)")
                except ValueError:
                    print("  Format invalid. Exemplu: 8 Signe 150")
            else:
                print("  Format invalid. Exemplu: 8 Signe 150")


# =============================================================================
# MOD BATCH
# =============================================================================

def run_batch(engine: "TitusEngine", cases: list[dict], top_n: int = 5) -> dict:
    """
    Ruleaza o lista de cazuri de test si returneaza raport complet.
    Fiecare caz: {id, label, keywords, elements}
    """
    import time

    results_all = []
    passed_top3 = 0
    passed_top5 = 0
    total       = len(cases)

    def matches(name, keywords):
        nl = name.lower()
        return any(kw.lower() in nl for kw in keywords)

    t_start = time.time()

    for case in cases:
        t0      = time.time()
        output  = engine.diagnose(case["elements"], top_n=top_n)
        elapsed = time.time() - t0

        ranking  = output.get("ranking", [])
        waiting  = output.get("waiting_room", [])
        keywords = case.get("keywords", [])

        hit_rank = None
        for r in ranking:
            if matches(r["name"], keywords):
                hit_rank = r["rank"]
                break

        # Cauta si in WaitingRoom
        in_waiting = any(matches(w["name"], keywords) for w in waiting)

        status = "TOP3" if hit_rank and hit_rank <= 3 else (
                 "TOP5" if hit_rank and hit_rank <= 5 else (
                 "WR"   if in_waiting else "MISS"))

        if status == "TOP3": passed_top3 += 1
        if status in ("TOP3","TOP5"): passed_top5 += 1

        results_all.append({
            "id"        : case["id"],
            "label"     : case["label"],
            "status"    : status,
            "hit_rank"  : hit_rank,
            "in_waiting": in_waiting,
            "top1"      : ranking[0]["name"] if ranking else "—",
            "top1_cr"   : ranking[0]["cr"]   if ranking else 0,
            "elapsed_ms": round(elapsed * 1000, 1),
            "ranking"   : ranking,
            "waiting"   : waiting,
        })

    total_time = time.time() - t_start

    return {
        "total"       : total,
        "passed_top3" : passed_top3,
        "passed_top5" : passed_top5,
        "missed"      : total - passed_top5,
        "pct_top3"    : round(passed_top3 / total * 100, 1),
        "pct_top5"    : round(passed_top5 / total * 100, 1),
        "total_sec"   : round(total_time, 2),
        "avg_ms"      : round(total_time / total * 1000, 1),
        "cases"       : results_all,
    }


def print_batch_report(report: dict) -> None:
    """Afiseaza raportul batch in format tabelar."""
    print("\n" + "=" * 70)
    print(f"TITUS — Raport Batch  ({report['total']} cazuri)")
    print("=" * 70)
    print(f"  Top 3: {report['passed_top3']}/{report['total']}"
          f"  ({report['pct_top3']}%)")
    print(f"  Top 5: {report['passed_top5']}/{report['total']}"
          f"  ({report['pct_top5']}%)")
    print(f"  Timp total: {report['total_sec']}s  "
          f"(medie {report['avg_ms']}ms/caz)")
    print()
    print(f"  {'ID':<4} {'Status':<6} {'Rank':<5} {'CR-1':>6}  "
          f"{'Timp':>6}  {'Diagnostic #1'}")
    print("  " + "-" * 65)
    for c in report["cases"]:
        rank_str = str(c["hit_rank"]) if c["hit_rank"] else ("WR" if c["in_waiting"] else "—")
        status_icon = {"TOP3": "✓", "TOP5": "~", "WR": "◎", "MISS": "✗"}.get(c["status"], "?")
        print(f"  {c['id']:<4} {status_icon} {c['status']:<5} "
              f"{rank_str:<5} {c['top1_cr']:>6.4f}  "
              f"{c['elapsed_ms']:>5.0f}ms  {c['top1'][:35]}")
    print()
    missed = [c for c in report["cases"] if c["status"] == "MISS"]
    if missed:
        print("  Cazuri nerezolvate:")
        for c in missed:
            print(f"    [{c['id']}] {c['label']}")
    print("=" * 70 + "\n")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    engine = TitusEngine()

    # Daca sunt argumente in linia de comanda: JSON cu lista de elemente
    if len(sys.argv) > 1:
        try:
            elems = json.loads(sys.argv[1])
            # Format: [[code, nature, score], ...]
            patient = [(int(e[0]), str(e[1]), int(e[2])) for e in elems]
            results = engine.diagnose(patient)
            engine.print_results(results)
        except Exception as ex:
            print(f"Eroare la parsare argumente: {ex}")
            sys.exit(1)
    else:
        interactive_session(engine)