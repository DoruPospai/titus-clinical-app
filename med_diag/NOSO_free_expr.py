# NOSO_free_expr.py
# Matching expresii libere contra lexiconului NlpRO.
# Sursa unica de adevar: sheet-ul Lexicon din workbook-ul NlpRO.
# Se imbogateste automat la fiecare update al lexiconului.

import streamlit as st
import pandas as pd
from pathlib import Path


# ── Incarcare lexicon ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_lexicon(wb_path: str, _mtime: float) -> pd.DataFrame:
    """
    Incarca sheet-ul Lexicon din workbook-ul NlpRO.
    Cache invalidat automat la modificarea fisierului (_mtime).
    """
    df = pd.read_excel(wb_path, sheet_name="Lexicon", dtype=str).fillna("")
    required = ["ExpresiePacient", "CodeElement", "Nature Element", "ElementStandard"]
    for col in required:
        if col not in df.columns:
            df[col] = ""
    return df


def get_lexicon(wb_path: str) -> pd.DataFrame:
    try:
        mtime = Path(wb_path).stat().st_mtime
        return _load_lexicon(wb_path, mtime)
    except Exception:
        return pd.DataFrame()


# ── Matching ─────────────────────────────────────────────────────────────────

def match_expression(query: str, lexicon: pd.DataFrame,
                     nature_filter: str = "all",
                     fuzzy_threshold: int = 75) -> list[dict]:
    """
    Cauta o expresie in lexicon.

    Strategii in ordine:
    1. Exact match (case-insensitive)
    2. Substring match
    3. Fuzzy match cu rapidfuzz (daca instalat)

    Args:
        query:          expresia scrisa de utilizator
        lexicon:        DataFrame din sheet-ul Lexicon
        nature_filter:  "Sympt" | "Signe" | "RiskF" | "all"
        fuzzy_threshold: scor minim fuzzy (0-100)

    Returns:
        Lista de dict: {expression, code, nature, name, score, method}
    """
    if lexicon.empty or not query.strip():
        return []

    q = query.strip().lower()

    # Filtru natura
    lex = lexicon.copy()
    if nature_filter != "all":
        lex = lex[lex["Nature Element"] == nature_filter]
    if lex.empty:
        return []

    results = []
    seen    = set()

    def add(row, score, method):
        try:
            code = int(str(row["CodeElement"]).strip())
        except ValueError:
            return
        key = (code, row["Nature Element"])
        if key in seen:
            return
        seen.add(key)
        results.append({
            "expression": row["ExpresiePacient"],
            "code":       code,
            "nature":     str(row["Nature Element"]),
            "name":       str(row["ElementStandard"]),
            "score":      score,
            "method":     method,
        })

    # 1. Exact match
    for _, row in lex.iterrows():
        if row["ExpresiePacient"].strip().lower() == q:
            add(row, 100, "exact")

    # 2. Substring match (query in expresie sau expresie in query)
    for _, row in lex.iterrows():
        expr = row["ExpresiePacient"].strip().lower()
        if (q in expr or expr in q) and len(q) >= 3:
            add(row, 90, "substring")

    # 3. Token overlap (cuvintele din query prezente in expresie)
    q_tokens = set(q.split())
    if len(q_tokens) >= 2:
        for _, row in lex.iterrows():
            expr_tokens = set(row["ExpresiePacient"].strip().lower().split())
            overlap = len(q_tokens & expr_tokens)
            if overlap >= min(2, len(q_tokens)):
                score = int(overlap / max(len(q_tokens), len(expr_tokens)) * 100)
                if score >= 50:
                    add(row, score, "token")

    # 4. Fuzzy match
    try:
        from rapidfuzz import process, fuzz
        expressions = lex["ExpresiePacient"].str.lower().tolist()
        matches = process.extract(q, expressions, scorer=fuzz.token_sort_ratio,
                                  limit=5, score_cutoff=fuzzy_threshold)
        for match_expr, score, idx in matches:
            add(lex.iloc[idx], int(score), "fuzzy")
    except ImportError:
        # rapidfuzz nu e instalat — continua fara fuzzy
        pass

    # Sorteaza dupa scor descrescator
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]


# ── Render widget ─────────────────────────────────────────────────────────────

def render_free_expression(*, key_prefix: str, nature: str,
                            default_weight: int, source_label: str):
    """
    Widget complet pentru tab-ul 'Expresie liberă'.
    Citeste lexiconul din workbook-ul NlpRO configurat in sidebar.
    """
    from .NOSO_review import add_element

    ss = st.session_state

    # Calea workbook din NlpRO
    wb_path = ""
    nlpro_script = ss.get("sidebar_nlpro_script", "")
    if nlpro_script:
        # Incearca sa citeasca DEFAULT_WORKBOOK din modulul NlpRO
        try:
            import importlib.util, time
            spec = importlib.util.spec_from_file_location(
                f"nlpro_cfg_{int(time.time()*1000)}", nlpro_script
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            wb_path = str(getattr(mod, "DEFAULT_WORKBOOK", ""))
        except Exception:
            pass

    if not wb_path or not Path(wb_path).exists():
        st.warning("Setati calea NlpRO script in sidebar pentru a activa Expresia liberă.")
        st.caption(f"Cale detectata: {wb_path or '—'}")
        return

    lexicon = get_lexicon(wb_path)
    if lexicon.empty:
        st.warning("Lexiconul NlpRO este gol sau nu a putut fi citit.")
        return

    st.caption(f"Lexicon: **{len(lexicon)}** expresii  ·  "
               f"sursa: `{Path(wb_path).name}`")

    query = st.text_input(
        "Expresie liberă",
        placeholder="ex: am dureri de cap pulsatile, mă doare pieptul la efort...",
        key=f"{key_prefix}_free_query",
    )
    weight = st.selectbox(
        "Pondere", [50, 100, 150, 200],
        index=[50,100,150,200].index(
            default_weight if default_weight in [50,100,150,200] else 150
        ),
        key=f"{key_prefix}_free_weight",
    )

    if not query.strip():
        return

    results = match_expression(query, lexicon, nature_filter=nature)

    if not results:
        st.info(
            "Niciun element identificat în lexicon. "
            "Încercați o altă formulare sau folosiți **Search by keyword**."
        )
        # Adauga in Unmatched pentru imbogatire lexicon
        if st.button("➕ Adaugă în Unmatched (pentru îmbogățire lexicon)",
                     key=f"{key_prefix}_free_unmatched"):
            unm = ss.get("unmatched_expressions", [])
            if query not in unm:
                unm.append(query)
                ss["unmatched_expressions"] = unm
                st.success(f"'{query}' adăugat în lista Unmatched.")
        return

    st.markdown(f"**{len(results)} rezultate:**")

    METHOD_LABEL = {
        "exact":     ("🟢", "potrivire exactă"),
        "substring": ("🟡", "potrivire parțială"),
        "token":     ("🟡", "cuvinte comune"),
        "fuzzy":     ("🟠", f"similar {results[0]['score']}%"),
    }

    for r in results:
        icon, method_lbl = METHOD_LABEL.get(r["method"], ("⚪",""))
        nat  = r["nature"]
        code = r["code"]
        name = r["name"]
        nat_icon = {"Sympt":"🔵","Signe":"🟣","RiskF":"🟢"}.get(nat,"⚪")

        c1, c2, c3 = st.columns([5, 1, 1])
        with c1:
            st.markdown(
                f"{nat_icon} `{code:04d}` **{name}**  "
                f"<small>{icon} {method_lbl} · \"{r['expression']}\"</small>",
                unsafe_allow_html=True,
            )
        with c2:
            st.caption(nat)
        with c3:
            if st.button("＋", key=f"{key_prefix}_free_add_{code}_{nat}",
                         help="Adaugă în Review & Finalize"):
                add_element(code, nat, name, score=int(weight),
                            source=source_label)
                st.toast(f"✓ {name} adăugat")
