"""
narrative_engine.py — Motor de extracție semiologică din narațiuni în limbaj natural.

Arhitectură:
  Stratul 1 — Exact match substring pe lexiconul TITUS (ExpresiePacient)
  Stratul 2 — Embedding semantic (SemanticMatcher) pe utterance-urile nematch-ate

Fără regex manual. Fără _PATTERNS. Unica sursă de adevăr: lexiconul TITUS.

Inițializare la startup (în app_main.py):
    from .narrative_engine import init_engine
    init_engine(lexicon_df, semantic_matcher)   # apelat o singură dată

Utilizare:
    from .narrative_engine import extract
    results = extract(text)
    # results: list[dict(code, nature, name_ro, certainty, expression)]
"""

import re
import unicodedata
from typing import Optional

# ── State global al motorului ─────────────────────────────────────────────────
_lex_index: dict = {}      # expr_norm -> (code, nature, name_ro, polaritate)
_sem_matcher = None        # SemanticMatcher instance sau None
_initialized = False


# ── Normalizare (identică cu pipeline-ul principal) ───────────────────────────
def _normalize(text: str) -> str:
    s = str(text)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[_/|]+", " ", s)
    s = re.sub(r"[^a-z0-9:+\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── Inițializare motor ────────────────────────────────────────────────────────
def init_engine(lexicon_df, semantic_matcher=None) -> None:
    """
    Inițializează motorul cu lexiconul TITUS și SemanticMatcher opțional.

    Args:
        lexicon_df: DataFrame cu coloanele ExpresiePacient, CodeElement,
                    Nature Element, CatalogName, Polaritate, puternicitate.
        semantic_matcher: instanță SemanticMatcher sau None.
    """
    global _lex_index, _sem_matcher, _initialized

    _lex_index = {}

    for _, row in lexicon_df.iterrows():
        expr = str(row.get("ExpresiePacient", "")).strip()
        code_raw = row.get("CodeElement", "")
        nature = str(row.get("Nature Element", "")).strip()
        catalog = str(row.get("CatalogName", "")).strip()
        polar = str(row.get("Polaritate", "prezent")).strip()

        if not expr or not code_raw or not nature:
            continue

        try:
            code = int(float(str(code_raw)))
        except (ValueError, TypeError):
            continue

        expr_norm = _normalize(expr)
        if len(expr_norm) < 3:
            continue

        # Păstrează prima intrare pentru expresia normalizată.
        # Sortarea după lungime se face ulterior în extract().
        if expr_norm not in _lex_index:
            _lex_index[expr_norm] = (code, nature, catalog, polar)

    _sem_matcher = semantic_matcher
    _initialized = True


# ── Fallback init ─────────────────────────────────────────────────────────────
def _ensure_init() -> None:
    """Fallback: încearcă să preia matcher-ul din Streamlit session_state."""
    global _sem_matcher

    if _sem_matcher is not None:
        return

    try:
        import streamlit as st
        candidate = st.session_state.get("_sem_matcher", None)
        if candidate is not None:
            _sem_matcher = candidate
    except Exception:
        pass


# ── Extracție ─────────────────────────────────────────────────────────────────
def extract(text: str, existing_codes: Optional[set] = None) -> list[dict]:
    """
    Extrage elemente semiologice din text liber.

    Args:
        text: utterance-ul pacientului.
        existing_codes: coduri deja detectate, pentru deduplicare.

    Returns:
        list de dict-uri:
        {
            code,
            nature,
            name_ro,
            certainty: "exact" | "semantic",
            expression,
            polarity,
            source,
            confidence,
            annotation,
        }
    """
    _ensure_init()

    if existing_codes is None:
        existing_codes = set()

    t = _normalize(text)
    if len(t) < 3:
        return []

    seen = set(existing_codes)
    results = []

    # ── Stratul 1: Exact match substring ─────────────────────────────────────
    # Sortăm expresiile după lungime descrescătoare: match mai specific primul.
    sorted_exprs = sorted(_lex_index.keys(), key=len, reverse=True)

    for expr_norm in sorted_exprs:
        code, nature, catalog, polar = _lex_index[expr_norm]

        if code in seen:
            continue

        words = expr_norm.split()
        if len(words) >= 2:
            matched = expr_norm in t
        else:
            # Token singur: doar cu graniță de cuvânt și lungime minimă.
            if len(expr_norm) < 5:
                continue
            matched = bool(re.search(r"\b" + re.escape(expr_norm) + r"\b", t))

        if matched:
            seen.add(code)
            results.append(dict(
                code=code,
                nature=nature,
                name_ro=catalog,
                certainty="exact",
                expression=expr_norm,
                polarity=polar,
                source="LEXICON",
                confidence=1.0,
                annotation="LEXICON_EXACT",
            ))

    # ── Stratul 2: Semantic embedding ────────────────────────────────────────
    sem_available = bool(_sem_matcher and getattr(_sem_matcher, "available", False))

    if sem_available:
        sem = _sem_matcher.match(t)

        if sem is not None:
            try:
                code = int(float(str(sem["CodeElement"])))
            except (ValueError, TypeError, KeyError):
                code = None

            if code and code not in seen:
                # Acceptăm automat doar candidatul EMBED.
                # EMBED_REVIEW și EMBED_REVIEW_NEGATION rămân pentru review/debug,
                # nu intră direct în results.
                if sem.get("source") == "EMBED":
                    seen.add(code)
                    results.append(dict(
                        code=code,
                        nature=sem.get("NatureElement", ""),
                        name_ro=sem.get("ElementStandard") or sem.get("CatalogName") or sem.get("ExpresiePacient", ""),
                        certainty="semantic",
                        expression=sem.get("ExpresiePacient", t),
                        polarity=sem.get("Polaritate", "prezent"),
                        source=sem.get("source", "EMBED"),
                        confidence=sem.get("confidence"),
                        annotation=sem.get("source", "EMBED"),
                    ))

    return results


# ── Debug helper opțional ─────────────────────────────────────────────────────
def debug_state() -> dict:
    """Returnează starea internă a motorului, utilă în Streamlit pentru diagnostic."""
    return {
        "initialized": _initialized,
        "lex_size": len(_lex_index),
        "sem_exists": _sem_matcher is not None,
        "sem_available": getattr(_sem_matcher, "available", None),
        "sem_type": str(type(_sem_matcher)),
    }
