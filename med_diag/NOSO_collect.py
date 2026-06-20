# NOSO_collect.py
# Pasul 1 — Colectare date (4 surse unificate)
# Search text · Search cod · Categorii · Anamneză

import json
import urllib.request

import streamlit as st

from .NOSO_loader  import search_elements, load_catalogs, get_element_name
from .NOSO_review  import add_element, add_elements_bulk
from .narrative_engine  import extract as _local_extract
from .NOSO_anam_local   import LocalAnamEngine


# ══════════════════════════════════════════════════════════════════════════════
# SURSA 1 — SEARCH TEXT
# ══════════════════════════════════════════════════════════════════════════════
def render_search_text(root: str = ""):
    st.markdown("#### 🔍 Search text")
    st.caption("Caută simptome, semne sau factori de risc după nume.")

    col_q, col_n = st.columns([4, 1])
    with col_q:
        query = st.text_input("Termen de căutare",
                               placeholder="ex: tremor, dyspnea, smoking...",
                               key="collect_text_query")
    with col_n:
        nat = st.selectbox("Natură", ["all", "Sympt", "Signe", "RiskF"],
                            key="collect_text_nat")

    if query.strip():
        results = search_elements(query.strip(), nat, root)
        if not results:
            st.info("Niciun rezultat. Încercați un alt termen.")
        else:
            st.caption(f"{len(results)} rezultate")
            for r in results[:20]:
                c1, c2, c3 = st.columns([5, 1, 1])
                with c1:
                    icon = {"Sympt":"🔵","Signe":"🟣","RiskF":"🟢"}.get(r["nature"],"⚪")
                    st.markdown(f"{icon} `{r['code']}` **{r['name']}**")
                    st.caption(r["nature"])
                with c2:
                    sc = st.number_input("", min_value=10, max_value=700,
                                          value=150, step=10,
                                          key=f"txt_sc_{r['code']}_{r['nature']}",
                                          label_visibility="collapsed")
                with c3:
                    if st.button("＋", key=f"txt_add_{r['code']}_{r['nature']}"):
                        add_element(r["code"], r["nature"], r["name"],
                                    score=sc, source="search_text", root=root)
                        st.toast(f"✓ {r['name']} adăugat")


# ══════════════════════════════════════════════════════════════════════════════
# SURSA 2 — SEARCH COD (uz intern)
# ══════════════════════════════════════════════════════════════════════════════
def render_search_code(root: str = ""):
    st.markdown("#### 🔢 Search cod — uz intern")
    st.caption("Introduceți codul numeric direct.")

    col_c, col_n, col_s, col_b = st.columns([2, 1, 1, 1])
    with col_c:
        code_str = st.text_input("Cod", placeholder="ex: 494",
                                  key="collect_code_input")
    with col_n:
        nat = st.selectbox("Natură", ["Sympt", "Signe", "RiskF"],
                            key="collect_code_nat")
    with col_s:
        sc = st.number_input("Score", min_value=10, max_value=700,
                              value=150, step=10, key="collect_code_sc")
    with col_b:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("＋ Adaugă", key="collect_code_add"):
            try:
                code = int(code_str.strip())
                name = get_element_name(code, nat, root)
                add_element(code, nat, name, score=sc,
                            source="search_code", root=root)
                st.toast(f"✓ {nat} {code} adăugat")
            except ValueError:
                st.error("Cod invalid.")


# ══════════════════════════════════════════════════════════════════════════════
# SURSA 3 — CATEGORII
# ══════════════════════════════════════════════════════════════════════════════
_CATEGORIES = {
    "Neurologic":    ["tremor","parkin","bradykin","extrapyramid","ataxia",
                      "epilep","dementia","sclerosis","neuropath","myopathy",
                      "headache","vertigo","syncope","seizure","confusion"],
    "Cardiovascular":["chest pain","palpitation","dyspnea","edema","tachycardia",
                      "bradycardia","syncope","angina","infarction","hypertension",
                      "arrhythmia","murmur","heart failure"],
    "Respirator":    ["cough","dyspnea","wheeze","hemoptysis","expectoration",
                      "stridor","apnea","rales","pleural","pneumo"],
    "Digestiv":      ["nausea","vomiting","diarrhea","constipation","abdominal",
                      "jaundice","hepato","ascites","rectal","dysphagia"],
    "Metabolic":     ["diabetes","thyroid","obesity","gout","fatigue","weight",
                      "thirst","polyuria","sweating","cholesterol"],
    "Reumatologic":  ["joint pain","stiffness","swelling","arthritis","lupus",
                      "spondyl","vasculitis","myositis","raynaud"],
    "Psihiatric":    ["depression","anxiety","hallucination","confusion","insomnia",
                      "memory","personality","obsessive","panic"],
    "Urinar":        ["dysuria","hematuria","frequency","oliguria","retention",
                      "proteinuria","renal","bladder"],
}

def render_categories(root: str = ""):
    st.markdown("#### 📂 Browse categorii")

    category = st.selectbox("Categorie", list(_CATEGORIES.keys()),
                              key="collect_cat_select")
    keywords = _CATEGORIES[category]

    cats = load_catalogs(root)
    results = []
    seen    = set()
    for kw in keywords:
        for nat, mapping in [("Sympt", cats["sym_map"]),
                              ("Signe", cats["sig_map"]),
                              ("RiskF", cats["rf_map"])]:
            for code, name in mapping.items():
                if kw in name.lower() and (code, nat) not in seen:
                    seen.add((code, nat))
                    results.append({"code": code, "nature": nat, "name": name})

    results.sort(key=lambda x: x["name"])
    st.caption(f"{len(results)} elemente în categoria **{category}**")

    for r in results[:30]:
        c1, c2, c3 = st.columns([5, 1, 1])
        with c1:
            icon = {"Sympt":"🔵","Signe":"🟣","RiskF":"🟢"}.get(r["nature"],"⚪")
            st.markdown(f"{icon} `{r['code']}` {r['name']}")
        with c2:
            sc = st.number_input("", min_value=10, max_value=700,
                                  value=150, step=10,
                                  key=f"cat_sc_{r['code']}_{r['nature']}",
                                  label_visibility="collapsed")
        with c3:
            if st.button("＋", key=f"cat_add_{r['code']}_{r['nature']}"):
                add_element(r["code"], r["nature"], r["name"],
                            score=sc, source=f"cat_{category}", root=root)
                st.toast(f"✓ {r['name']} adăugat")


# ══════════════════════════════════════════════════════════════════════════════
# SURSA 4 — ANAMNEZĂ — interfata NlpRO completa
# ══════════════════════════════════════════════════════════════════════════════

def render_anamneза(api_key: str = "", root: str = ""):
    from .NOSO_anam_tab import render_anam_nlpro
    render_anam_nlpro(root=root)


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL — toate sursele ca tabs
# ══════════════════════════════════════════════════════════════════════════════
def render_collect(api_key: str = "", root: str = ""):
    tab_txt, tab_cod, tab_cat, tab_anam = st.tabs([
        "🔍 Search text",
        "🔢 Search cod",
        "📂 Categorii",
        "🎙️ Anamneză",
    ])
    with tab_txt:  render_search_text(root)
    with tab_cod:  render_search_code(root)
    with tab_cat:  render_categories(root)
    with tab_anam: render_anamneза(api_key, root)
