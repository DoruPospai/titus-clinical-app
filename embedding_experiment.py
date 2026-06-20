#!/usr/bin/env python3
"""
EXPERIMENT EMBEDDING SEMANTIC — FAZA DE STUDIU TITUS
======================================================
Rulat LOCAL unde HuggingFace este accesibil.

Dependinte:
    pip install sentence-transformers faiss-cpu pandas openpyxl

Utilizare:
    python3 embedding_experiment.py
"""

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# ── Configurare ───────────────────────────────────────────────────────────
MODEL_NAME  = 'intfloat/multilingual-e5-large'   # 1024 dim, suporta romana
# Alternativa mai mica daca memoria e limitata:
# MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'  # 384 dim

THRESHOLD_AUTO    = 0.90   # accept automat
THRESHOLD_REVIEW  = 0.75   # accept cu flag UNCERTAIN
TOP_K             = 5      # candidati returnati per query

# ── Incarcare date ────────────────────────────────────────────────────────
print("Incarc datele...")
utterances = pd.read_excel('EMBEDDING_EXPERIMENT_utterances.xlsx', dtype=str).fillna('')
lexicon    = pd.read_excel('EMBEDDING_EXPERIMENT_lexicon.xlsx', dtype=str).fillna('')

print(f"Utterance-uri de analizat: {len(utterances)}")
print(f"Expresii in lexicon: {len(lexicon)}")

# ── Incarcare model ────────────────────────────────────────────────────────
print(f"\nIncarc modelul {MODEL_NAME}...")
model = SentenceTransformer(MODEL_NAME)

# ── Build index FAISS ─────────────────────────────────────────────────────
print("Construiesc index FAISS...")
lex_texts  = lexicon['expr_norm'].tolist()
lex_embeds = model.encode(
    lex_texts,
    batch_size=64,
    show_progress_bar=True,
    normalize_embeddings=True   # necesar pentru cosinus cu IndexFlatIP
)

dim   = lex_embeds.shape[1]
index = faiss.IndexFlatIP(dim)  # Inner Product = cosinus dupa normalizare
index.add(lex_embeds.astype(np.float32))
print(f"Index construit: {index.ntotal} vectori, {dim} dimensiuni")

# ── Query ─────────────────────────────────────────────────────────────────
print("\nRulez embedding pe utterance-urile nematch-ate...")
query_texts  = utterances['text_norm'].tolist()
query_embeds = model.encode(
    query_texts,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True
)

D, I = index.search(query_embeds.astype(np.float32), TOP_K)

# ── Construiesc rezultate ─────────────────────────────────────────────────
rows = []
for q_idx, (dists, idxs) in enumerate(zip(D, I)):
    utt_row = utterances.iloc[q_idx]
    best_sim  = float(dists[0])
    best_lex  = lexicon.iloc[int(idxs[0])]

    if best_sim >= THRESHOLD_AUTO:
        status = 'AUTO_ACCEPT'
    elif best_sim >= THRESHOLD_REVIEW:
        status = 'REVIEW'
    else:
        status = 'MISS'

    candidates = []
    for rank, (sim, lex_idx) in enumerate(zip(dists, idxs)):
        lx = lexicon.iloc[int(lex_idx)]
        candidates.append(f"{sim:.3f}|{lx['ExpresiePacient']}|{lx['Nature Element']}:{lx['CodeElement']}")

    rows.append({
        'dialog_id':        utt_row['dialog_id'],
        'turn_id':          utt_row['turn_id'],
        'utterance':        utt_row['text'],
        'utterance_norm':   utt_row['text_norm'],
        'status':           status,
        'best_similarity':  round(best_sim, 4),
        'best_expr':        best_lex['ExpresiePacient'],
        'best_element':     f"{best_lex['Nature Element']}:{best_lex['CodeElement']}",
        'best_catalog':     best_lex['CatalogName'],
        'top5_candidates':  ' || '.join(candidates),
    })

results = pd.DataFrame(rows)

# ── Statistici ────────────────────────────────────────────────────────────
print("\n=== REZULTATE ===")
print(results['status'].value_counts().to_string())
print()
print(f"Similaritate medie: {results['best_similarity'].mean():.3f}")
print(f"Similaritate mediana: {results['best_similarity'].median():.3f}")
print()

# Distributie similaritati
bins = [0, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 1.01]
labels = ['<0.60','0.60-0.70','0.70-0.75','0.75-0.80','0.80-0.85','0.85-0.90','>=0.90']
results['sim_bin'] = pd.cut(results['best_similarity'], bins=bins, labels=labels, right=False)
print("Distributie similaritati:")
print(results['sim_bin'].value_counts().sort_index().to_string())

# ── Export ────────────────────────────────────────────────────────────────
out = 'EMBEDDING_EXPERIMENT_results.xlsx'
results.to_excel(out, index=False)
print(f"\nRezultate salvate in: {out}")
print("\nDone.")
