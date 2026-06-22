# NOSO_free_expr_fixed.py
# Matching expresii libere contra lexiconului NlpRO.
# Sursa unica de adevar: sheet-ul Lexicon din workbook-ul NlpRO.
# Se imbogateste automat la fiecare update al lexiconului.

import streamlit as st
import pandas as pd
from pathlib import Path


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


def match_expression(query: str, lexicon: pd.DataFrame,
                     nature_filter: str = "all",
                     fuzzy_threshold: int = 75) -> list[dict]:
    """
    Cauta o expresie in lexicon.

    Strategii in ordine:
    1. Exact match (case-insensitive)
    2. Substring match
    3. Token overlap
    4. Fuzzy match cu rapidfuzz (daca instalat)
    """
    if lexicon.empty or not query.strip():
        return []

    q = query.strip().lower()

    lex = lexicon.copy()
    if nature_filter != "all":
        lex = lex[lex["Nature Element"] == nature_filter]
    if lex.empty:
        return []

    results = []
    seen = set()

    def add(row, score, method):
        try:
            code = int(str(row["CodeElement"]).strip())
        except Exception:
            return

        key = (code, str(row["Nature Element"]).strip())
        if key in seen:
            return
        seen.add(key)

        results.append({
            "expression": str(row["ExpresiePacient"]),
            "code": code,
            "nature": str(row["Nature Element"]).strip(),
            "name": str(row["ElementStandard"]).strip(),
            "score": int(score),
            "method": method,
        })

    for _, row in lex.iterrows():
        if str(row["ExpresiePacient"]).strip().lower() == q:
            add(row, 100, "exact")

    for _, row in lex.iterrows():
        expr = str(row["ExpresiePacient"]).strip().lower()
        if len(q) >= 3 and (q in expr or expr in q):
            add(row, 90, "substring")

    q_tokens = set(q.split())
    if len(q_tokens) >= 2:
        for _, row in lex.iterrows():
            expr_tokens = set(str(row["ExpresiePacient"]).strip().lower().split())
            overlap = len(q_tokens & expr_tokens)
            if overlap >= min(2, len(q_tokens)):
                score = int(overlap / max(len(q_tokens), len(expr_tokens)) * 100)
                if score >= 50:
                    add(row, score, "token")

    try:
        from rapidfuzz import process, fuzz
        expressions = lex["ExpresiePacient"].astype(str).str.lower().tolist()
        matches = process.extract(
            q,
            expressions,
            scorer=fuzz.token_sort_ratio,
            limit=5,
            score_cutoff=fuzzy_threshold,
        )
        for _, score, idx in matches:
            add(lex.iloc[idx], int(score), "fuzzy")
    except ImportError:
        pass

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]

from .editor import append_editor_rows


def _append_to_review_finalize(code: int, nature: str, name: str,
                               score: int, source: str, catalog_df) -> None:
    """
    Depune elementul in Review & Finalize prin mecanismul oficial
    (append_editor_rows), identic cu toate celelalte cai de adaugare
    din pages_input.py. NU se scrie direct in editor_rows — acel rand
    ar avea chei gresite (code/nature/score, litere mici) si ar fi
    invizibil pentru get_editor_df()/editor_df_to_patient_map(), care
    cer schema cu majuscule: Key/Nature/Code/Label/Weight/Source.
    """
    row = {
        "Key":    f"{nature}:{int(code):04d}",
        "Nature": str(nature),
        "Code":   int(code),
        "Label":  str(name),
        "Weight": int(score),
        "Source": str(source),
    }
    append_editor_rows([row], catalog_df)
def render_free_expression(*, key_prefix: str, nature: str,
                           default_weight: int, source_label: str,
                           catalog_df):
    """
    Widget complet pentru tab-ul 'Expresie liberă'.
    Citeste lexiconul din workbook-ul NlpRO configurat in sidebar.
    Depune rezultatele in Review & Finalize prin append_editor_rows(),
    acelasi mecanism oficial folosit de toate celelalte moduri de
    adaugare (keyword, category, code, description).
    """
    ss = st.session_state

    wb_path = ""
    nlpro_script = ss.get("sidebar_nlpro_script", "")
    if nlpro_script:
        try:
            import importlib.util
            import time
            spec = importlib.util.spec_from_file_location(
                f"nlpro_cfg_{int(time.time()*1000)}", nlpro_script
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            wb_path = str(getattr(mod, "DEFAULT_WORKBOOK", ""))
        except Exception:
            pass

    if not wb_path or not Path(wb_path).exists():
        st.warning("Setați calea NlpRO script în sidebar pentru a activa Expresia liberă.")
        st.caption(f"Cale detectată: {wb_path or '—'}")
        return

    lexicon = get_lexicon(wb_path)
    if lexicon.empty:
        st.warning("Lexiconul NlpRO este gol sau nu a putut fi citit.")
        return

    st.caption(f"Lexicon: **{len(lexicon)}** expresii · sursa: `{Path(wb_path).name}`")

    query = st.text_input(
        "Expresie liberă",
        placeholder="ex: am dureri de cap pulsatile, mă doare pieptul la efort...",
        key=f"{key_prefix}_free_query",
    )

    weight = st.selectbox(
        "Pondere",
        [50, 100, 150, 200],
        index=[50, 100, 150, 200].index(
            default_weight if default_weight in [50, 100, 150, 200] else 150
        ),
        key=f"{key_prefix}_free_weight",
    )

    if not query.strip():
        return

    results = match_expression(query, lexicon, nature_filter=nature)

    if not results:
        st.info(
            "Niciun element identificat în lexicon. "
            "Încercați o altă formulare sau folosiți Search by keyword."
        )
        if st.button(
            "➕ Adaugă în Unmatched (pentru îmbogățire lexicon)",
            key=f"{key_prefix}_free_unmatched"
        ):
            unm = ss.get("unmatched_expressions", [])
            if query not in unm:
                unm.append(query)
                ss["unmatched_expressions"] = unm
                st.success(f"'{query}' adăugat în lista Unmatched.")
                st.rerun()
        return

    st.markdown(f"**{len(results)} rezultate:**")

    nat_icons = {"Sympt": "🔵", "Signe": "🟣", "RiskF": "🟢"}

    for r in results:
        method = r["method"]
        if method == "exact":
            icon, method_lbl = "🟢", "potrivire exactă"
        elif method == "substring":
            icon, method_lbl = "🟡", "potrivire parțială"
        elif method == "token":
            icon, method_lbl = "🟡", "cuvinte comune"
        else:
            icon, method_lbl = "🟠", f"similar {r['score']}%"

        nat = r["nature"]
        code = r["code"]
        name = r["name"]
        nat_icon = nat_icons.get(nat, "⚪")

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
            if st.button(
                "＋",
                key=f"{key_prefix}_free_add_{code}_{nat}",
                help="Adaugă în Review & Finalize"
            ):
                if nat not in {"Sympt", "Signe", "RiskF"}:
                    st.warning(f"{name}: natură necunoscută ({nat}), nu a fost adăugat.")
                else:
                    _append_to_review_finalize(
                        code=int(code),
                        nature=nat,
                        name=name,
                        score=int(weight),
                        source=source_label,
                        catalog_df=catalog_df,
                    )
                    st.toast(f"✓ {name} adăugat în Review & Finalize")
                    st.rerun()
