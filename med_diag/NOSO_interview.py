# NOSO_interview.py
# Pagina "Interviu" — conversatie live medic-pacient condusa de app
# Foloseste ANAM_anamnesis_engine pentru arbore de decizie

import sys
from pathlib import Path

import streamlit as st

from .ui_common import panel_header
from .NOSO_review import add_elements_bulk, init_review_state


def render_interview(root: str = ""):
    panel_header(
        "🎤 Interviu",
        "Conversație ghidată — app conduce anamneza, extrage entitățile și le trimite în profil"
    )

    ss = st.session_state
    init_review_state()
    ss.setdefault("iv_engine",   None)
    ss.setdefault("iv_chat",     [])
    ss.setdefault("iv_entities", [])
    ss.setdefault("iv_active",   False)
    ss.setdefault("iv_api_key",  ss.get("sidebar_api_key", ""))

    # ── Configurare ───────────────────────────────────────────────────────────
    col_cfg, col_btn = st.columns([3, 1])
    with col_cfg:
        api_key = st.text_input(
            "Cheie API Claude (opțional — fără cheie: regex local)",
            value=ss["iv_api_key"], type="password", key="iv_api_key_input"
        )
        ss["iv_api_key"] = api_key
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if not ss["iv_active"]:
            if st.button("▶️ Începe interviul", type="primary",
                         use_container_width=True, key="iv_start"):
                _start_interview(ss, api_key)
                st.rerun()
        else:
            if st.button("⏹️ Oprește", use_container_width=True, key="iv_stop"):
                ss["iv_active"] = False
                st.rerun()

    if not ss["iv_active"] and not ss["iv_chat"]:
        st.info("Apasă **▶️ Începe interviul** pentru a porni conversația ghidată.")
        return

    # ── Afișare chat ──────────────────────────────────────────────────────────
    for msg in ss["iv_chat"]:
        role = "assistant" if msg["role"] == "doctor" else "user"
        with st.chat_message(role):
            st.markdown(msg["text"])

    # ── Input pacient ─────────────────────────────────────────────────────────
    if ss["iv_active"]:
        patient_input = st.chat_input("Răspundeți la întrebarea de mai sus...")
        if patient_input:
            ss["iv_chat"].append({"role":"patient","text":patient_input})
            with st.chat_message("user"):
                st.markdown(patient_input)

            eng = ss["iv_engine"]
            if eng:
                next_q, new_ents = eng.process(patient_input)
                ss["iv_entities"].extend(new_ents)

                if next_q:
                    ss["iv_chat"].append({"role":"doctor","text":next_q})
                else:
                    ss["iv_active"] = False
                    ss["iv_chat"].append({
                        "role":"doctor",
                        "text":"Mulțumesc. Interviul este complet."
                    })
                st.rerun()

    # ── Rezultate + transfer la profil ────────────────────────────────────────
    if ss["iv_entities"] or not ss["iv_active"]:
        st.divider()

        entities = ss["iv_entities"]
        prez = [e for e in entities if e.get("polarity","prezent") == "prezent"]
        neg  = [e for e in entities if e.get("polarity","prezent") == "negat"]

        col1, col2, col3 = st.columns(3)
        col1.metric("Entități prezente", len(prez))
        col2.metric("Negate",            len(neg))
        col3.metric("Total turns",       len([m for m in ss["iv_chat"] if m["role"]=="patient"]))

        if prez:
            with st.expander("Entități extrase", expanded=True):
                NAT_ICON = {"Sympt":"🔵","Signe":"🟣","RiskF":"🟢"}
                for e in prez:
                    icon = NAT_ICON.get(e.get("nature",""),"⚪")
                    st.markdown(
                        f"{icon} `{e.get('code',0):04d}` **{e.get('name','')}**"
                        + (f"  ·  *{e.get('temporal_cue','')}*" if e.get("temporal_cue") else "")
                        + (f"  ·  📍{e.get('laterality','')}" if e.get("laterality") else "")
                    )

            # Domeniu detectat
            eng = ss.get("iv_engine")
            if eng and eng.state.detected_domain:
                st.caption(f"Domeniu detectat: **{eng.state.detected_domain}**")

            col_add, col_reset = st.columns(2)
            with col_add:
                if st.button(f"➕ Adaugă {len(prez)} elemente în profil",
                             type="primary", use_container_width=True, key="iv_add"):
                    elements = [
                        (int(e["code"]), e.get("nature","Sympt"), 150)
                        for e in prez if e.get("code")
                    ]
                    add_elements_bulk(elements, source="interviu", root=root)
                    st.success("Elemente adăugate în profil. Mergeți la Review & Finalize.")
                    ss["iv_entities"] = []
                    ss["iv_chat"]     = []
                    ss["iv_engine"]   = None
                    ss["iv_active"]   = False
                    st.rerun()
            with col_reset:
                if st.button("🔄 Interviu nou", use_container_width=True, key="iv_reset"):
                    ss["iv_entities"] = []
                    ss["iv_chat"]     = []
                    ss["iv_engine"]   = None
                    ss["iv_active"]   = False
                    st.rerun()


def _start_interview(ss: dict, api_key: str):
    """Pornește un nou interviu."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from ANAM_anamnesis_engine import AnamnesisEngine
        eng = AnamnesisEngine(api_key=api_key, use_api=bool(api_key))
        first_q = eng.start()
        ss["iv_engine"]  = eng
        ss["iv_chat"]    = [{"role":"doctor","text":first_q}]
        ss["iv_entities"]= []
        ss["iv_active"]  = True
    except Exception as ex:
        st.error(f"Eroare la pornire interviu: {ex}")
