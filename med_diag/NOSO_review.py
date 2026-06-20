# NOSO_review.py
# Pasul 2 — Review & Finalize Patient Elements
# Tabel editabil complet: adaugă / modifică / șterge elemente

import streamlit as st
from .NOSO_loader import get_element_name, search_elements


# ── Structura unui element în profilul pacientului ────────────────────────────
def _empty_element() -> dict:
    return {"code": 0, "nature": "Sympt", "score": 150,
            "name": "", "source": "manual", "polarity": "prezent"}


def _element_key(e: dict) -> tuple:
    return (int(e["code"]), str(e["nature"]), str(e.get("polarity","prezent")))


# ── Inițializare state ────────────────────────────────────────────────────────
def init_review_state():
    ss = st.session_state
    ss.setdefault("noso_elements",  [])   # lista de elemente curente
    ss.setdefault("noso_edit_idx",  None) # indexul elementului în editare
    ss.setdefault("noso_add_mode",  False)


# ── Adaugă element (din orice sursă externă) ─────────────────────────────────
def add_element(code: int, nature: str, name: str = "",
                score: int = 150, source: str = "manual",
                polarity: str = "prezent", root: str = ""):
    """API public — toate sursele apelează această funcție."""
    init_review_state()
    ss = st.session_state

    if not name:
        name = get_element_name(code, nature, root)

    e   = {"code": code, "nature": nature, "score": score,
           "name": name, "source": source, "polarity": polarity}
    key = _element_key(e)

    # Evită duplicate
    for existing in ss["noso_elements"]:
        if _element_key(existing) == key:
            return

    ss["noso_elements"].append(e)


def add_elements_bulk(elements: list[tuple], source: str = "bulk", root: str = ""):
    """Adaugă o listă de (code, nature, score) deodată."""
    for item in elements:
        if len(item) == 3:
            code, nature, score = item
        elif len(item) == 2:
            code, nature = item; score = 150
        else:
            continue
        add_element(int(code), str(nature), score=int(score),
                    source=source, root=root)


def clear_elements():
    st.session_state["noso_elements"] = []


# ── Render pagina Review ──────────────────────────────────────────────────────
def render_review(root: str = ""):
    init_review_state()
    ss = st.session_state

    elements: list = ss["noso_elements"]

    st.subheader("Review & Finalize Patient Elements")

    if not elements:
        st.info("Niciun element adăugat încă. "
                "Folosiți sursele din meniul lateral pentru a adăuga elemente.")
        _render_add_form(elements, root)
        return

    # ── Statistici rapide ────────────────────────────────────────────────────
    prez  = [e for e in elements if e.get("polarity","prezent") == "prezent"]
    neg   = [e for e in elements if e.get("polarity","prezent") == "negat"]
    nsymp = sum(1 for e in prez if e["nature"] == "Sympt")
    nsign = sum(1 for e in prez if e["nature"] == "Signe")
    nrf   = sum(1 for e in prez if e["nature"] == "RiskF")

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total",    len(elements))
    c2.metric("Prezente", len(prez))
    c3.metric("Sympt",    nsymp)
    c4.metric("Signe",    nsign)
    c5.metric("Negat",    len(neg))

    st.divider()

    # ── Tabel editabil ───────────────────────────────────────────────────────
    NAT_COLOR = {"Sympt": "🔵", "Signe": "🟣", "RiskF": "🟢"}
    POL_COLOR = {"prezent": "", "negat": "~~", "incert": "*"}

    for i, e in enumerate(elements):
        nat  = e.get("nature",   "Sympt")
        pol  = e.get("polarity", "prezent")
        icon = NAT_COLOR.get(nat, "⚪")
        name = e.get("name", get_element_name(e["code"], nat, root))

        col_main, col_score, col_pol, col_edit, col_del = st.columns([4,1,1,1,1])

        with col_main:
            if pol == "negat":
                st.markdown(f"{icon} ~~`{e['code']}`  {name}~~")
            else:
                st.markdown(f"{icon} `{e['code']}`  **{name}**")
            st.caption(f"{nat} · sursă: {e.get('source','—')}")

        with col_score:
            if ss["noso_edit_idx"] == i:
                new_score = st.number_input(
                    "Score", min_value=10, max_value=700,
                    value=int(e["score"]), step=10,
                    key=f"score_edit_{i}", label_visibility="collapsed"
                )
                ss["noso_elements"][i]["score"] = new_score
            else:
                st.markdown(f"**{e['score']}**")
                st.caption("score")

        with col_pol:
            new_pol = st.selectbox(
                "Pol", ["prezent", "negat", "incert"],
                index=["prezent","negat","incert"].index(pol),
                key=f"pol_{i}", label_visibility="collapsed"
            )
            ss["noso_elements"][i]["polarity"] = new_pol

        with col_edit:
            if st.button("✎", key=f"edit_{i}", help="Editează scorul"):
                ss["noso_edit_idx"] = None if ss["noso_edit_idx"] == i else i
                st.rerun()

        with col_del:
            if st.button("✕", key=f"del_{i}", help="Șterge elementul"):
                ss["noso_elements"].pop(i)
                if ss["noso_edit_idx"] == i:
                    ss["noso_edit_idx"] = None
                st.rerun()

    st.divider()

    # ── Buton adăugare manuală ────────────────────────────────────────────────
    _render_add_form(elements, root)

    # ── Acțiuni globale ───────────────────────────────────────────────────────
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("🗑️ Șterge tot", use_container_width=True):
            clear_elements()
            st.rerun()
    with col_b:
        prez_for_engine = [
            (int(e["code"]), e["nature"], int(e["score"]))
            for e in elements
            if e.get("polarity","prezent") == "prezent"
        ]
        st.session_state["noso_elements_ready"] = prez_for_engine
        st.success(f"{len(prez_for_engine)} elemente prezente pregătite pentru NOSO.")


def _render_add_form(elements: list, root: str):
    """Mini-formular pentru adăugare manuală."""
    with st.expander("＋ Adaugă element manual"):
        col_q, col_nat = st.columns([3, 1])
        with col_q:
            query = st.text_input("Caută element", key="review_add_query",
                                   placeholder="ex: tremor, cough, diabetes...")
        with col_nat:
            nat_filter = st.selectbox("Natură", ["all","Sympt","Signe","RiskF"],
                                       key="review_add_nat")

        if query.strip():
            results = search_elements(query, nat_filter, root)[:15]
            if not results:
                st.caption("Niciun rezultat.")
            else:
                for r in results:
                    rc1, rc2, rc3 = st.columns([4, 1, 1])
                    with rc1:
                        st.markdown(f"`{r['code']}` {r['name']}")
                        st.caption(r["nature"])
                    with rc2:
                        score_add = st.number_input(
                            "Scor", min_value=10, max_value=700,
                            value=150, step=10,
                            key=f"add_score_{r['code']}_{r['nature']}",
                            label_visibility="collapsed"
                        )
                    with rc3:
                        if st.button("＋", key=f"add_{r['code']}_{r['nature']}"):
                            add_element(r["code"], r["nature"], r["name"],
                                        score=score_add, source="manual", root=root)
                            st.rerun()
