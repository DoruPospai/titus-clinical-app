# semantic_layer.py
# Strat 2 — Embedding semantic pentru TITUS NLP pipeline
#
# Integrare în DOR_clinical_pipeline_singlefile_v19:
#   - Activat automat dacă sentence-transformers + faiss sunt instalate
#   - Fallback silențios la stratul 1 (exact match) dacă lipsesc
#   - Cache FAISS pe disc — rebuild doar la schimbarea Lexiconului
#
# Instalare:
#   pip install sentence-transformers faiss-cpu
#
# Model utilizat:
#   intfloat/multilingual-e5-large  (2.24GB, 1024 dim)
#   Alternativă mai mică:
#   paraphrase-multilingual-MiniLM-L12-v2  (471MB, 384 dim)

import re
import pickle
import hashlib
import unicodedata
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Cache de modul — pastreaza modelul SentenceTransformer incarcat in memorie
# pe durata vietii procesului Python curent. Fara acest cache, fiecare
# instantiere noua a SemanticMatcher (de exemplu la fiecare rerun al
# scriptului de pipeline) reincarca integral modelul de pe disc — operatie
# costisitoare (~2.24GB pentru e5-large) care poate epuiza paging file-ul
# Windows daca se repeta de mai multe ori in succesiune rapida.
_MODEL_CACHE: dict = {}


def _get_cached_model(model_name: str):
    """Returneaza modelul din cache-ul de modul, sau il incarca o singura
    data si il memoreaza pentru apelurile ulterioare din acelasi proces."""
    if model_name in _MODEL_CACHE:
        logger.info(f"SemanticMatcher: model '{model_name}' reutilizat din cache de proces.")
        return _MODEL_CACHE[model_name]

    from sentence_transformers import SentenceTransformer
    try:
        model = SentenceTransformer(model_name, local_files_only=True)
    except Exception:
        model = SentenceTransformer(model_name)
    _MODEL_CACHE[model_name] = model
    return model

# ── Constante ─────────────────────────────────────────────────────────────────

MODEL_NAME         = "intfloat/multilingual-e5-large"
MODEL_NAME_SMALL   = "paraphrase-multilingual-MiniLM-L12-v2"  # fallback mai mic

THRESHOLD_AUTO     = 0.93   # accept automat — calibrat pe experimentul TITUS
THRESHOLD_REVIEW   = 0.90   # accept cu flag EMBED_REVIEW

CACHE_SUFFIX       = ".semantic_cache.pkl"  # salvat lângă workbook
MIN_WORDS          = 2      # utterance-uri cu < 2 cuvinte → skip
MIN_EXPR_LEN       = 3      # expresii prea scurte → excluse din index

# Prefixe pentru multilingual-e5 (necesare pentru calitate optimă)
E5_QUERY_PREFIX    = "query: "
E5_PASSAGE_PREFIX  = "passage: "

# Negații — utterance-urile care încep cu acestea sunt rutate la REVIEW,
# nu AUTO_ACCEPT, indiferent de similaritate (risc de inversare semantică)
_NEGATION_STARTERS = re.compile(
    r"^(nu\b|niciodată|niciodata|nu\s+am|nu\s+știu|nu\s+stiu"
    r"|nu\s+cred|nu\s+prea|nu\s+mai|fără\s|fara\s|nicio\b)",
    re.IGNORECASE | re.UNICODE,
)

# Răspunsuri scurte ambigue — skip complet
_SKIP_PATTERNS = re.compile(
    r"^(da|nu|ok|bine|aha|poate|sigur|normal|exact|corect|"
    r"înțeleg|inteleg|desigur|probabil)[\s,\.!]*$",
    re.IGNORECASE | re.UNICODE,
)


# ── Normalizare (identică cu pipeline-ul principal) ───────────────────────────

def _normalize(text: str) -> str:
    s = str(text)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[_/|]+", " ", s)
    s = re.sub(r"[^a-z0-9:+\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── SemanticMatcher ───────────────────────────────────────────────────────────

class SemanticMatcher:
    """
    Strat 2 de matching — embedding semantic pe expresiile nematch-ate
    din stratul 1 (exact substring).

    Utilizare în pipeline:
        matcher = SemanticMatcher(workbook_path, lexicon_df)
        result  = matcher.match(utterance_norm)
        if result:
            # result = {
            #   'CodeElement', 'NatureElement', 'CatalogName',
            #   'ElementStandard', 'ExpresiePacient', 'Polaritate',
            #   'puternicitate', 'source', 'confidence'
            # }
    """

    def __init__(self, workbook_path: Path, lexicon_df: pd.DataFrame):
        self._available = False
        self._index     = None
        self._lex_rows  = []   # list of dicts paralel cu index
        self._model     = None
        self._is_e5     = False

        try:
            self._init(workbook_path, lexicon_df)
        except ImportError:
            logger.warning(
                "SemanticMatcher: sentence-transformers sau faiss nu sunt instalate. "
                "Stratul semantic dezactivat. "
                "Instalare: pip install sentence-transformers faiss-cpu"
            )
        except Exception as exc:
            logger.warning(f"SemanticMatcher: initializare esuata — {exc}. Stratul semantic dezactivat.")

    # ── Initializare ──────────────────────────────────────────────────────────

    def _init(self, workbook_path: Path, lexicon_df: pd.DataFrame):
        import faiss
        from sentence_transformers import SentenceTransformer
        import numpy as np

        self._np    = np
        self._faiss = faiss

        # Construim lista de expresii indexabile
        lex_valid = lexicon_df[
            lexicon_df["ExpresiePacient"].astype(str).str.strip().str.len() >= MIN_EXPR_LEN
        ].copy()
        lex_valid["_expr_norm"] = lex_valid["ExpresiePacient"].apply(_normalize)
        lex_valid = lex_valid[lex_valid["_expr_norm"].str.len() >= MIN_EXPR_LEN]
        lex_valid = lex_valid.drop_duplicates(subset=["_expr_norm"])
        
        if len(lex_valid) == 0:
            logger.warning("SemanticMatcher: lexicon gol dupa filtrare.")
            return
        # Hash lexicon pentru cache invalidation
        lex_hash = hashlib.md5(
            lex_valid["_expr_norm"].str.cat(sep="|").encode("utf-8")
        ).hexdigest()[:12]
        
        cache_path = Path(workbook_path).with_suffix(CACHE_SUFFIX)
        
        # Încearcă încărcarea din cache
        if cache_path.exists():
           
            try:
                with open(cache_path, "rb") as f:
                    cached = pickle.load(f)
                if cached.get("hash") == lex_hash and cached.get("model") == MODEL_NAME:
                    logger.info(f"SemanticMatcher: index incarcat din cache ({len(lex_valid)} expresii).")
                    self._index    = faiss.deserialize_index(cached["index_bytes"])
                    self._lex_rows = cached["lex_rows"]
                    # Incarca modelul pentru query-uri — din cache de proces
                    # daca a mai fost incarcat anterior in aceasta sesiune,
                    # altfel din disc local (local_files_only).
                    self._model  = _get_cached_model(MODEL_NAME)
                    self._is_e5  = "e5" in MODEL_NAME.lower()
                    self._available = True
                    return
            except Exception as exc:
                logger.warning(f"SemanticMatcher: cache invalid — {exc}. Rebuild.")

        # Build index FAISS
        logger.info(f"SemanticMatcher: incarc modelul {MODEL_NAME}...")
        try:
            model = _get_cached_model(MODEL_NAME)
            is_e5 = True
        except Exception:
            model = _get_cached_model(MODEL_NAME_SMALL)
            is_e5 = False

        self._model = model
        self._is_e5 = is_e5
        
        exprs = lex_valid["_expr_norm"].tolist()
        if is_e5:
            passages = [E5_PASSAGE_PREFIX + e for e in exprs]
        else:
            passages = exprs

        logger.info(f"SemanticMatcher: construiesc index FAISS ({len(exprs)} expresii)...")
        embeddings = model.encode(
            passages,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        embeddings = np.array(embeddings, dtype=np.float32)

        dim   = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Construieste lista de dict-uri pentru rezultate
        self._lex_rows = []
        for _, row in lex_valid.iterrows():
            self._lex_rows.append({
                "ExpresiePacient": str(row.get("ExpresiePacient", "")),
                "CodeElement":     str(row.get("CodeElement", "")),
                "NatureElement":   str(row.get("Nature Element", "")),
                "CatalogName":     str(row.get("CatalogName", "")),
                "ElementStandard": str(row.get("ElementStandard", "")),
                "ElementStandardDORU": str(row.get("ElementStandard", "")),
                "PolaritatePOSPAI":      str(row.get("Polaritate", "prezent")),
                "puternicitate":   str(row.get("puternicitate", "") or row.get("Intensitate", "")),
            })

        self._index = index

        # Salveaza cache
        try:
            cache_data = {
                "hash":        lex_hash,
                "model":       MODEL_NAME if is_e5 else MODEL_NAME_SMALL,
                "index_bytes": faiss.serialize_index(index),
                "lex_rows":    self._lex_rows,
            }
            with open(cache_path, "wb") as f:
                pickle.dump(cache_data, f)
            logger.info(f"SemanticMatcher: cache salvat la {cache_path}")
        except Exception as exc:
            logger.warning(f"SemanticMatcher: nu pot salva cache — {exc}")

        self._available = True
        logger.info(f"SemanticMatcher: activ cu {len(exprs)} expresii indexate.")

    # ── Matching ───────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._available

    def match(self, utterance_norm: str) -> Optional[dict]:
        """
        Cauta cel mai aproape element semiologic semantic.

        Args:
            utterance_norm: utterance-ul pacientului deja normalizat

        Returns:
            dict cu campurile elementului semiologic + 'source' + 'confidence'
            sau None dacă nu există candidat suficient de bun.
        """
        #import streamlit as st
        #st.write(utterance_norm)
        if not self._available:
            return None

        # Filtru lungime
        words = utterance_norm.split()
        if len(words) < MIN_WORDS:
            return None
        
        # Filtru raspunsuri ambigue scurte
        if _SKIP_PATTERNS.match(utterance_norm):
            return None

        # Detecta negatie — va fi marcat REVIEW indiferent de similaritate
        is_negation = bool(_NEGATION_STARTERS.match(utterance_norm))

        # Embedding query
        if self._is_e5:
            query_text = E5_QUERY_PREFIX + utterance_norm
        else:
            query_text = utterance_norm

        q = self._model.encode(
            [query_text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        q = self._np.array(q, dtype=self._np.float32)

        D, I = self._index.search(q, k=1)
        sim      = float(D[0][0])
        lex_row  = self._lex_rows[int(I[0][0])]
        
        # Determina statusul
        if is_negation:
            # Negațiile nu primesc AUTO, indiferent de similaritate
            if sim >= THRESHOLD_REVIEW:
                source = "EMBED_REVIEW_NEGATION"
            else:
                return None
        elif sim >= THRESHOLD_AUTO:
            source = "EMBED"
        elif sim >= THRESHOLD_REVIEW:
            source = "EMBED_REVIEW"
        else:
            return None

        return {
            **lex_row,
            "source": source,
            "confidence": round(sim, 4),
        
            # Annotation-native metadata
            "MatchMethod": source,
            "Confidence": round(sim, 4),
            "AnnotationSource": "SEMANTIC",
            "AnnotationLabel": source,
        }

    def match_top_k(self, utterance_norm: str, k: int = 5) -> list[dict]:
        """
        Returneaza top-k candidati pentru debug / AutoSuggestions.
        """
        if not self._available:
            return []

        words = utterance_norm.split()
        if len(words) < MIN_WORDS:
            return []

        if _SKIP_PATTERNS.match(utterance_norm):
            return []

        if self._is_e5:
            query_text = E5_QUERY_PREFIX + utterance_norm
        else:
            query_text = utterance_norm

        q = self._model.encode(
            [query_text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        q = self._np.array(q, dtype=self._np.float32)

        D, I = self._index.search(q, k=min(k, len(self._lex_rows)))

        results = []
        for sim, idx in zip(D[0], I[0]):
            lx = self._lex_rows[int(idx)]
            results.append({**lx, "similarity": round(float(sim), 4)})
        return results
