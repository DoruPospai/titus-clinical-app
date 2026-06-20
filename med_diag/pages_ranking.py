"""
pages_ranking.py — TITUS
Afiseaza ranking-ul CR, WaitingRoom, Explain, Suggest, Comorbid.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .editor import editor_df_to_patient_map
from .inference import ranking_to_df, waiting_room_to_df
from .i18n import disease_display, get_lang
from .titus_engine import get_engine, patient_map_to_titus, titus_to_patient_dict
from .ui_common import kpi_card, note, panel_header


# ---------------------------------------------------------------------------
# Afisare tabele
# ---------------------------------------------------------------------------

def _render_ranking_table(df: pd.DataFrame, key: str) -> None:
    if df is None or df.empty:
        st.caption("Niciun rezultat.")
        return

    col_cfg = {}
    if "Google" in df.columns:
        col_cfg["Google"] = st.column_config.LinkColumn("Google", display_text="↗")
    if "CR" in df.columns:
        col_cfg["CR"] = st.column_config.NumberColumn("CR", format="%.4f")
    if "Overlap" in df.columns:
        col_cfg["Overlap"] = st.column_config.NumberColumn("Overlap", format="%.4f")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        key=key,
        column_config=col_cfg if col_cfg else None,
    )


# ---------------------------------------------------------------------------
# Panel Explain
# ---------------------------------------------------------------------------

def _render_explain_panel(engine, patient_dict: dict, ranking_df: pd.DataFrame) -> None:
    st.markdown("#### Explicatie diagnostic")
    if ranking_df.empty:
        st.caption("Ruleaza ranking-ul mai intai.")
        return

    options = [
        f"{int(r['Rank'])}. [{r['Clasa']}] cr={r['CR']:.4f}  {r['Boala']}"
        for _, r in ranking_df.iterrows()
    ]
    idx = st.selectbox("Alege diagnosticul", range(len(options)),
                       format_func=lambda i: options[i], key="explain_select")

    if st.button("Explica", key="explain_btn", use_container_width=True):
        row  = ranking_df.iloc[int(idx)]
        code = int(row["CodeMaladie"])
        expl = engine.explain(patient_dict, code)

        def ename(key):
            c, nat = key
            nm = engine.symp_map.get(c) if nat == "Sympt" else engine.sign_map.get(c)
            return nm.title() if nm else f"{nat}:{c}"

        bd  = expl["breakdown"]
        cr  = expl["cr"]
        cls = expl["cr_class"]

        cardinals_present      = [e for e in expl["present"] if e["cardinal"]]
        non_cardinals_present  = [e for e in expl["present"] if not e["cardinal"]]
        cardinals_absent_d     = [e for e in expl["absent_d"] if e["cardinal"]]
        non_cardinals_absent_d = [e for e in expl["absent_d"] if not e["cardinal"]]
        gap = expl["gap"]

        # ── Sinteza ─────────────────────────────────────────────────────────
        if cr == 1.0:
            sinteza = ("**Potrivire perfecta** — toate simptomele pacientului "
                       "sunt prezente in aceasta boala, fara nicio penalizare.")
            box_color = "#d1fae5"
        elif cr >= 0.80:
            sinteza = ("**Potrivire foarte buna** — profilul pacientului "
                       "corespunde in mare masura acestei boli.")
            box_color = "#dcfce7"
        elif cr >= 0.60:
            sinteza = ("**Potrivire buna** — diagnosticul este plauzibil, "
                       "cu rezerve moderate.")
            box_color = "#fef9c3"
        else:
            sinteza = ("**Potrivire partiala** — diagnosticul posibil, "
                       "dar profilul clinic este incomplet.")
            box_color = "#fee2e2"

        st.markdown(
            f"""
            <div style="background:{box_color};border-radius:12px;padding:16px 20px;margin-bottom:12px;">
            <b style="font-size:1.1rem">{expl['name']}</b>
            &nbsp;&nbsp;<span style="color:#64748b">Cls {cls} &nbsp;|&nbsp; CR = {cr:.4f}</span><br><br>
            {sinteza}<br><br>
            <span style="color:#475569;font-size:0.9rem">
            CR = (overlap <b>{bd['overlap']}</b> − penalizare <b>{bd['penalty']:.1f}</b>)
            / M(P) <b>{bd['M_P']}</b> = <b>{cr:.4f}</b>
            </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            # Confirmate
            if cardinals_present:
                nms = ", ".join(ename(e["key"]) for e in cardinals_present)
                st.markdown(
                    f"""<div style="background:#eff6ff;border-left:4px solid #2563eb;
                    border-radius:8px;padding:12px 14px;margin-bottom:8px;">
                    <b>✓ Simptome cardinale confirmate ({len(cardinals_present)})</b><br>
                    <span style="color:#1e40af">{nms}</span></div>""",
                    unsafe_allow_html=True,
                )
            if non_cardinals_present:
                nms = ", ".join(ename(e["key"]) for e in non_cardinals_present)
                st.markdown(
                    f"""<div style="background:#f0fdf4;border-left:4px solid #16a34a;
                    border-radius:8px;padding:12px 14px;margin-bottom:8px;">
                    <b>✓ Simptome secundare confirmate ({len(non_cardinals_present)})</b><br>
                    <span style="color:#15803d">{nms}</span></div>""",
                    unsafe_allow_html=True,
                )
            # Gap
            if gap:
                nms = ", ".join(ename(e["key"]) for e in gap)
                pen_pct = round(bd['penalty'] / bd['M_P'] * 100)
                st.markdown(
                    f"""<div style="background:#fef2f2;border-left:4px solid #dc2626;
                    border-radius:8px;padding:12px 14px;margin-bottom:8px;">
                    <b>✗ Simptome ale pacientului absente din aceasta boala</b><br>
                    <span style="color:#991b1b">{nms}</span><br>
                    <span style="color:#7f1d1d;font-size:0.85rem">
                    Penalizare totala: {pen_pct}% din scorul maxim posibil
                    </span></div>""",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """<div style="background:#f0fdf4;border-left:4px solid #16a34a;
                    border-radius:8px;padding:12px 14px;">
                    <b>Nicio penalizare</b> — toate simptomele pacientului
                    sunt compatibile cu aceasta boala.</div>""",
                    unsafe_allow_html=True,
                )

        with col2:
            # Ce lipseste din profil
            if cardinals_absent_d:
                nms_list = "".join(
                    f"<li>→ {ename(e['key'])}</li>"
                    for e in cardinals_absent_d[:5]
                )
                st.markdown(
                    f"""<div style="background:#fefce8;border-left:4px solid #ca8a04;
                    border-radius:8px;padding:12px 14px;margin-bottom:8px;">
                    <b>Simptome cardinale ale bolii neconfirmate inca</b><br>
                    <span style="color:#92400e;font-size:0.9rem">
                    Prezenta lor ar intari diagnosticul:</span><br>
                    <ul style="margin:6px 0 0 0;color:#78350f">{nms_list}</ul>
                    </div>""",
                    unsafe_allow_html=True,
                )
            if non_cardinals_absent_d:
                nms = ", ".join(ename(e["key"]) for e in non_cardinals_absent_d[:4])
                st.markdown(
                    f"""<div style="background:#f8fafc;border-left:4px solid #94a3b8;
                    border-radius:8px;padding:12px 14px;">
                    <b>Alte simptome posibile ale bolii:</b><br>
                    <span style="color:#475569">{nms}</span></div>""",
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Panel Suggest
# ---------------------------------------------------------------------------

def _render_suggest_panel(engine, patient_dict: dict, ranking: list[dict]) -> None:
    st.markdown("#### Sugestii pentru diferentiere")
    if not ranking:
        st.caption("Ruleaza ranking-ul mai intai.")
        return

    n_top = st.slider("Diferentiaza primele N diagnostice", 2, min(5, len(ranking)), 3,
                      key="suggest_n_top")

    if st.button("Calculeaza sugestii", key="suggest_btn"):
        suggestions = engine.suggest(patient_dict, ranking, top_diseases=n_top)

        def ename(key):
            c, nat = key
            nm = engine.symp_map.get(c) if nat == "Sympt" else engine.sign_map.get(c)
            return nm.title() if nm else f"{nat}:{c}"

        top_names = [r["name"] for r in ranking[:n_top]]
        note(f"Comparand: <b>{' vs '.join(top_names)}</b>")

        if not suggestions:
            st.info("Nu există simptome discriminante suplimentare clare.")
            return

        for i, s in enumerate(suggestions, 1):
            key_name = ename(s["key"])
            code, nature = s["key"]
            present_in = s["present_in"]
            absent_in  = s["absent_in"]

            if present_in and absent_in:
                impact = (f"prezent în {', '.join(present_in[:2])}; "
                          f"absent în {', '.join(absent_in[:2])}")
            else:
                impact = f"prezent în {', '.join(present_in[:2])}" if present_in else "diferențiaza prin scor"

            delta_rows = [
                {"Boala": engine.disease_names.get(c, str(c)),
                 "ΔCR": round(d, 4),
                 "Directie": "▲" if d > 0 else "▼"}
                for c, d in s["cr_delta"].items()
            ]

            with st.expander(f"{i}. **{key_name}** ({nature} {code})  —  {impact}"):
                st.dataframe(pd.DataFrame(delta_rows), hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Panel Comorbid
# ---------------------------------------------------------------------------

def _render_comorbid_panel(engine, patient_dict: dict) -> None:
    st.markdown("#### Cautare comorbiditate")
    note(
        "Cauta activ perechea (D1, D2) care explica profilul pacientului "
        "mai bine decat orice diagnostic singular."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        top_n      = st.number_input("Top perechi", 1, 10, 5, key="cmb_top_n")
    with col2:
        min_cr     = st.number_input("CR minim singular", 0.10, 0.50, 0.25, step=0.05, key="cmb_min_cr")
    with col3:
        min_impr   = st.number_input("Imbunatatire minima (%)", 5, 30, 10, key="cmb_min_impr")

    if st.button("Cauta comorbiditate", key="cmb_btn"):
        result = engine.comorbid(
            patient_dict,
            min_cr_single=float(min_cr),
            min_improvement=1.0 + float(min_impr) / 100,
            top_n=int(top_n),
        )

        pairs = result["pairs"]
        st.markdown(
            f"Candidati analizati: **{result['n_candidates']}**  |  "
            f"CR best singular: **{result['best_single_cr']:.4f}**"
        )

        if not pairs:
            st.success("Nicio comorbiditate semnificativa detectata.")
            st.caption("Profilul este explicat bine de un singur diagnostic.")
            return

        def ename(key):
            c, nat = key
            nm = engine.symp_map.get(c) if nat == "Sympt" else engine.sign_map.get(c)
            return nm.title() if nm else f"{nat}:{c}"

        for i, p in enumerate(pairs, 1):
            with st.expander(
                f"#{i}  {p['name_a']}  +  {p['name_b']}  "
                f"— CR combinat: {p['cr_pair']:.4f}  (+{p['improvement']:.1f}%)",
                expanded=(i == 1),
            ):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric(p["name_a"], f"CR = {p['cr_a']:.4f}")
                    if p["only_a"]:
                        st.markdown("**Simptome exclusiv D1:**")
                        st.markdown(", ".join(ename(k) for k in p["only_a"]))
                with col_b:
                    st.metric(p["name_b"], f"CR = {p['cr_b']:.4f}")
                    if p["only_b"]:
                        st.markdown("**Simptome exclusiv D2:**")
                        st.markdown(", ".join(ename(k) for k in p["only_b"]))

                if p["both"]:
                    st.markdown(f"**Comune ambelor:** {', '.join(ename(k) for k in p['both'])}")
                if p["unexplained"]:
                    st.warning(
                        f"Inca neexplicate: {', '.join(ename(k) for k in p['unexplained'])}"
                    )



def _render_why_panel(engine, patient_dict: dict, ranking_df: pd.DataFrame) -> None:
    st.markdown("#### De ce D1 e inaintea D2?")
    if ranking_df.empty or len(ranking_df) < 2:
        st.caption("Necesita cel putin 2 diagnostice in ranking.")
        return

    options = [
        f"{int(r['Rank'])}. [{r['Clasa']}] cr={r['CR']:.4f}  {r['Boala']}"
        for _, r in ranking_df.iterrows()
    ]

    c1, c2 = st.columns(2)
    with c1:
        idx_a = st.selectbox("Diagnosticul A (inainte)", range(len(options)),
                             format_func=lambda i: options[i], key="why_a")
    with c2:
        idx_b = st.selectbox("Diagnosticul B (dupa)", range(len(options)),
                             index=min(1, len(options)-1),
                             format_func=lambda i: options[i], key="why_b")

    if st.button("Analizeaza", key="why_btn"):
        if idx_a == idx_b:
            st.warning("Alege doua diagnostice diferite.")
            return

        row_a = ranking_df.iloc[int(idx_a)]
        row_b = ranking_df.iloc[int(idx_b)]
        code_a, code_b = int(row_a["CodeMaladie"]), int(row_b["CodeMaladie"])

        expl_a = engine.explain(patient_dict, code_a)
        expl_b = engine.explain(patient_dict, code_b)

        def ename(key):
            c, nat = key
            nm = engine.symp_map.get(c) if nat == "Sympt" else engine.sign_map.get(c)
            return nm.title() if nm else f"{nat}:{c}"

        cr_a, cr_b = expl_a["cr"], expl_b["cr"]
        st.markdown(
            f"**{expl_a['name']}** cr={cr_a:.4f}  >  "
            f"**{expl_b['name']}** cr={cr_b:.4f}  "
            f"(diferenta: +{cr_a - cr_b:.4f})"
        )

        keys_a = {e["key"] for e in expl_a["present"]}
        keys_b = {e["key"] for e in expl_b["present"]}
        adv_a  = keys_a - keys_b
        adv_b  = keys_b - keys_a
        common = keys_a & keys_b

        col1, col2 = st.columns(2)
        with col1:
            if adv_a:
                st.success(f"**Avantaj {expl_a['name'].split()[0]}** (prezent in A, absent in B):")
                st.markdown(", ".join(ename(k) for k in adv_a))
            bd_a = expl_a["breakdown"]
            st.metric("Penalizare gap A", f"{bd_a['penalty']:.1f}")

        with col2:
            if adv_b:
                st.info(f"**Avantaj {expl_b['name'].split()[0]}** (prezent in B, absent in A):")
                st.markdown(", ".join(ename(k) for k in adv_b))
            bd_b = expl_b["breakdown"]
            st.metric("Penalizare gap B", f"{bd_b['penalty']:.1f}")

        if common:
            st.markdown(f"**Comune ambelor:** {', '.join(ename(k) for k in common)}")

        # W-matrix
        row_idx_a = engine.w_code2row.get(code_a)
        row_idx_b = engine.w_code2row.get(code_b)
        if row_idx_a is not None and row_idx_b is not None:
            w_ab = float(engine.w_matrix_norm[row_idx_a, row_idx_b])
            w_ba = float(engine.w_matrix_norm[row_idx_b, row_idx_a])
            c1, c2 = st.columns(2)
            with c1:
                st.metric(
                    f"{expl_a['name'].split()[0]} bate {expl_b['name'].split()[0]}",
                    f"{w_ab*100:.1f}%"
                )
            with c2:
                st.metric(
                    f"{expl_b['name'].split()[0]} bate {expl_a['name'].split()[0]}",
                    f"{w_ba*100:.1f}%"
                )


# ---------------------------------------------------------------------------
# Pagina principala Ranking
# ---------------------------------------------------------------------------

def page_ranking(
    tabel2_path: str,
    w_matrix_path: str,
    raritate_path: str,
    output_dir: str,
    cr_threshold: float,
    top_k: int,
):
    panel_header(
        "Ranking TITUS",
        "Diagnostic analitic CR-based cu w_matrix ranking, WaitingRoom si instrumente de analiza."
    )

    # ── Incarcare motor ────────────────────────────────────────────────────
    try:
        engine = get_engine(tabel2_path, w_matrix_path, raritate_path)
    except Exception as e:
        st.error(f"Motor TITUS indisponibil: {e}")
        st.stop()

    # ── Profil pacient ─────────────────────────────────────────────────────
    patient_map  = editor_df_to_patient_map(
        pd.DataFrame(st.session_state.get("editor_rows", []))
    )
    titus_elems  = patient_map_to_titus(patient_map)
    patient_dict = titus_to_patient_dict(titus_elems)

    profile          = st.session_state.get("patient_profile", {})
    patient_sex      = str(profile.get("gender", "Unknown"))
    patient_age_m    = int(profile.get("age_in_months", 0) or 0)

    # ── KPI bar ────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Elemente", str(len(patient_map)))
    with c2: kpi_card("Masa pacient", f"{sum(patient_map.values()):.0f}")
    with c3: kpi_card("Prag CR", f"{cr_threshold:.2f}")
    with c4: kpi_card("Top-K", str(top_k))

    note(f"Sex: <b>{patient_sex}</b>  |  Varsta: <b>{patient_age_m}</b> luni")

    # Detectie profil schimbat — reseteaza automat ranking-ul vechi
    import hashlib as _hl
    _profile_sig = _hl.md5(
        str(sorted(patient_map.items())).encode() +
        str(patient_sex).encode() +
        str(patient_age_m).encode()
    ).hexdigest()[:8]
    _last_sig = st.session_state.get("_profile_sig", "")
    if _last_sig and _last_sig != _profile_sig:
        st.session_state["titus_raw_output"]   = None
        st.session_state["titus_ranking_df"]   = None
        st.session_state["titus_waiting_df"]   = None
        st.session_state["titus_demo_applied"] = False
        st.session_state["titus_demo_df"]      = None
        st.session_state["titus_demo_preview"] = None
    st.session_state["_profile_sig"] = _profile_sig

    # ── Buton Run ──────────────────────────────────────────────────────────
    # Avertisment: rezultate stale daca pacientul are RF dar rf_net=0 in toate
    raw_check = st.session_state.get("titus_raw_output")
    if raw_check and titus_elems:
        has_rf_elems = any(nl == "RiskF" for _, nl, _ in titus_elems)
        if has_rf_elems:
            ranking_check = raw_check.get("ranking", [])
            all_rf_zero = ranking_check and all(r.get("rf_net", 0) == 0 for r in ranking_check)
            if all_rf_zero:
                st.warning("⚠ Rezultatele afișate sunt din sesiunea anterioară (fără RF). "
                           "Apasă **▶ Run ranking** pentru a recalcula cu RF.")

    if st.button("▶  Run ranking", type="primary", use_container_width=True):
        if not titus_elems:
            st.warning("Profilul pacientului este gol.")
        else:
            with st.spinner("Calcul ranking..."):
                output = engine.diagnose(
                    titus_elems,
                    top_n        = int(top_k),
                    cr_threshold = float(cr_threshold),
                )
                # Filtru demografic post-ranking: exclude boli incompatibile
                _is_female   = patient_sex == "Female"
                _is_pregnant = (_is_female and
                                str(profile.get("pregnancy","No"))=="Yes")
                def _demo_ok(code):
                    sx = engine.sex_constraint.get(code, "")
                    pr = engine.preg_constraint.get(code, "")
                    if sx == "W" and not _is_female:   return False
                    if sx == "M" and _is_female:       return False
                    if pr == "P" and not _is_pregnant: return False
                    if pr == "S" and _is_pregnant:     return False
                    return True
                if hasattr(engine, "sex_constraint"):
                    output["ranking"] = [
                        r for r in output.get("ranking", [])
                        if _demo_ok(r["code"])
                    ]
                    # Re-numeroteaza rank
                    for i, r in enumerate(output["ranking"], 1):
                        r["rank"] = i
            st.session_state["titus_raw_output"]  = output
            st.session_state["titus_ranking_df"]  = ranking_to_df(output.get("ranking", []))
            st.session_state["titus_waiting_df"]  = waiting_room_to_df(output.get("waiting_room", []))
            # Reset factor demografic — baza s-a schimbat, trebuie recalculat
            st.session_state["titus_demo_applied"] = False
            st.session_state["titus_demo_df"]      = None
            st.session_state["titus_demo_preview"] = None
            n_rf = sum(1 for _, nl, _ in titus_elems if nl == "RiskF")
            msg = f"Ranking complet. {n_rf} RF activi." if n_rf else "Ranking complet (fara RF)."
            st.success(msg)
            # Salveaza semnatura profilului curent
            import hashlib as _hl2
            st.session_state["_profile_sig"] = _hl2.md5(
                str(sorted(patient_map.items())).encode() +
                str(patient_sex).encode() +
                str(patient_age_m).encode()
            ).hexdigest()[:8]

    # ── Afisare rezultate ──────────────────────────────────────────────────
    raw_output  = st.session_state.get("titus_raw_output")
    ranking_df  = st.session_state.get("titus_ranking_df",  pd.DataFrame())
    waiting_df  = st.session_state.get("titus_waiting_df",  pd.DataFrame())

    # Tab-urile sunt mereu vizibile — continut conditionat de raw_output
    _demo_preview   = st.session_state.get("titus_demo_preview")
    _demo_applied   = st.session_state.get("titus_demo_applied", False)
    _demo_tab_label = ("✅ Apply demografic" if _demo_preview is not None and not _demo_applied
                       else "☑ Demografic activ" if _demo_applied
                       else "🧬 Demographic")
    tabs = st.tabs(["📊 Ranking", "⏳ Waiting Room", "🔍 Explain", "💡 Suggest", "⚖️ Why", "🔗 Comorbid", "⚡ RF Impact", _demo_tab_label, "💾 Export"])

    with tabs[0]:
        st.markdown("### Ranking activ")

        # Indicator stare demografica
        demo_applied = st.session_state.get("titus_demo_applied", False)
        demo_df      = st.session_state.get("titus_demo_df")

        if demo_applied and demo_df is not None:
            col_a, col_b = st.columns([4, 1])
            with col_a:
                note("🧬 <b>Factor demografic aplicat</b> — ranking ordonat dupa CR×AgeFactor. "
                     "Bolile excluse (HardExclusion) sunt marcate.")
            with col_b:
                if st.button("✕ Anulare demografic", key="cancel_demo"):
                    st.session_state["titus_demo_applied"] = False
                    st.session_state["titus_demo_df"]      = None
                    st.rerun()
        else:
            note("Boli cu CR ≥ prag, ordonate prin w_matrix. Cls A ≥ 0.80 | B ≥ 0.60 | C ≥ 0.40")

        if raw_output is None:
            st.caption("Apasa 'Run ranking' pentru a vedea rezultatele.")
        else:
            comorbidity = raw_output.get("comorbidity")
            if comorbidity:
                st.warning(
                    f"⚠  Posibila comorbiditate:  "
                    f"**{comorbidity['name_a']}** (cr={comorbidity['cr_a']:.4f})  +  "
                    f"**{comorbidity['name_b']}** (cr={comorbidity['cr_b']:.4f})  "
                    f"→ CR combinat: **{comorbidity['cr_combined']:.4f}**"
                )
            if demo_applied and demo_df is not None:
                # Afisare ranking demografic
                show_cols = ["Rank_demo", "Boala", "CR_demographic", "AgeFactor",
                             "HardExclusion", "AgeLayer", "Google"]
                show_cols = [col for col in show_cols if col in demo_df.columns]
                _render_ranking_table(demo_df[show_cols], key="ranking_table_demo")
            elif not ranking_df.empty:
                _render_ranking_table(
                    ranking_df[["Rank", "Clasa", "CR", "Boala", "Google"]],
                    key="ranking_table_main"
                )
            else:
                st.info("Niciun candidat cu CR ≥ prag.")

    with tabs[1]:
        st.markdown("### Waiting Room")
        note("Boli cu CR sub prag dar cu overlap parțial și cardinal prezent. RARE apar primele.")
        if raw_output is None:
            st.caption("Apasa 'Run ranking' pentru a vedea rezultatele.")
        else:
            # WR semiologic
            if not waiting_df.empty:
                rare_df   = waiting_df[waiting_df["Tip"] == "RARE"].copy()
                common_df = waiting_df[waiting_df["Tip"] == "COMMON"].copy()
                if not rare_df.empty:
                    st.markdown(f"**RARE ({len(rare_df)})**")
                    _render_ranking_table(
                        rare_df[["Tip", "CR", "Overlap", "Boala", "Google"]],
                        key="wr_rare_table"
                    )
                if not common_df.empty:
                    st.markdown(f"**COMMON ({len(common_df)})**")
                    _render_ranking_table(
                        common_df[["Tip", "CR", "Overlap", "Boala", "Google"]],
                        key="wr_common_table"
                    )
            else:
                st.info("Waiting Room semiologic gol.")

            # WR RF — boli cu CR bun dar RF pacient lipsesc
            wr_rf = raw_output.get("waiting_room_rf", [])
            if wr_rf:
                st.markdown("---")
                st.markdown(f"### ⚠ Waiting Room RF ({len(wr_rf)} boli)")
                note("Boli cu CR semiologic ≥ prag dar care nu conțin toți RF pacientului. "
                     "Adaugă RF lipsă pentru a le confirma sau infirma.")
                for w in wr_rf:
                    rare_tag = " 🔴 RARE" if w["rare"] else ""
                    with st.expander(
                        f"**{w['name']}**{rare_tag}  —  CR semio={w['cr_semio']:.4f}  "
                        f"|  {w['reason']}"
                    ):
                        st.markdown(f"**Motiv excludere din ranking:**")
                        st.markdown(f"RF absenti din profilul bolii: "
                                    f"**{', '.join('RF:'+r for r in w['missing_rf'])}**")
                        st.markdown(
                            f"Dacă pacientul NU are acești RF, boala rămâne un candidat valid "
                            f"cu CR semiologic = **{w['cr_semio']:.4f}**."
                        )

    with tabs[2]:
        if raw_output is None:
            st.caption("Apasa 'Run ranking' mai intai.")
        else:
            _render_explain_panel(engine, patient_dict, ranking_df)

    with tabs[3]:
        if raw_output is None:
            st.caption("Apasa 'Run ranking' mai intai.")
        else:
            _render_suggest_panel(engine, patient_dict, raw_output.get("ranking", []))

    with tabs[4]:
        if raw_output is None:
            st.caption("Apasa 'Run ranking' mai intai.")
        else:
            _render_why_panel(engine, patient_dict, ranking_df)

    with tabs[5]:
        _render_comorbid_panel(engine, patient_dict)

    with tabs[6]:
        st.markdown("#### Impact Risk Factors")
        note(
            "Impactul RF asupra CR semiologic. "
            "▲ boost (RF prezent în boală) | ▼ penalizare (RF absent sau pacient fără RF)."
        )
        if raw_output is None:
            st.caption("Ruleaza ranking-ul mai intai.")
        else:
            # ── Diagnosticare pipeline RF ─────────────────────────────────────
            with st.expander("🔧 Diagnosticare RF pipeline", expanded=False):
                # 1. RF in patient profile
                rf_in_profile = [(k,v) for k,v in patient_dict.items() if k[1]=="RiskF"]
                st.markdown(f"**RF in profilul pacientului:** {len(rf_in_profile)}")
                if rf_in_profile:
                    for k,v in rf_in_profile:
                        st.markdown(f"  - RiskF:{k[0]}  (weight={v})")
                else:
                    st.warning("Niciun element RiskF in profilul pacientului. "
                               "Adauga RF din tab-ul 'Risk Factors' → 'Review & Finalize'.")

                # 2. Engine RF support
                has_rf_engine = hasattr(engine, 'rf_profiles')
                version  = getattr(engine, "VERSION",
                             getattr(type(engine), "_module_version", "NECUNOSCUT"))
                loaded_from = getattr(type(engine), "_loaded_from", "NECUNOSCUT")
                st.markdown(f"**Motor RF suportat:** {'✓' if has_rf_engine else '✗'}")
                st.markdown(f"**Versiune motor:** `{version}` "
                            f"{'✓ corect' if version=='RF_v3_2025' else '✗ VECHI!'}")
                st.code(f"Fisier incarcat: {loaded_from}")
                if has_rf_engine:
                    n_rf_diseases = len(engine.rf_profiles)
                    st.markdown(f"**Boli cu RF in motor:** {n_rf_diseases}")

                # 3. RF in ranking results
                ranking_list_check = raw_output.get("ranking", [])
                has_rf_in_results = any("rf_net" in r for r in ranking_list_check)
                st.markdown(f"**rf_net in rezultate:** {'✓' if has_rf_in_results else '✗ — motor fara suport RF'}")

                # 4. Test direct _compute_cr cu vs fara RF
                if rf_in_profile and ranking_list_check:
                    top_code = ranking_list_check[0]["code"]
                    top_name = ranking_list_check[0]["name"]
                    st.markdown("---")
                    st.markdown(f"**Test direct pe: {top_name} (cod {top_code})**")

                    # CR cu tot profilul (semio + RF)
                    cr_full = engine._compute_cr(patient_dict, top_code)
                    # CR numai semio (fara RF)
                    semio_only = {k:v for k,v in patient_dict.items() if k[1] in ("Sympt","Signe")}
                    cr_semio_only = engine._compute_cr(semio_only, top_code)

                    col1, col2, col3 = st.columns(3)
                    if cr_full < 0:
                        # Sentinel: boala exclusa din ranking (RF lipsa) → WaitingRoom RF
                        with col1: st.metric("CR cu RF", "WR RF", delta="RF absent")
                        with col2: st.metric("CR semio", f"{cr_semio_only:.4f}")
                        with col3: st.metric("Diferenta", "→ WaitingRoom RF")
                    else:
                        with col1: st.metric("CR cu RF", f"{cr_full:.4f}")
                        with col2: st.metric("CR fara RF", f"{cr_semio_only:.4f}")
                        with col3: st.metric("Diferenta", f"{cr_full-cr_semio_only:+.4f}")

                    # RF profile al bolii din motor
                    rf_dis = getattr(engine, 'rf_profiles', {}).get(top_code, {})
                    st.markdown(f"**RF in profilul bolii (din motor):** {len(rf_dis)} intrari")
                    if rf_dis:
                        for (k_code, k_nat), score in list(rf_dis.items())[:5]:
                            match = "✓ MATCH" if (k_code, k_nat) in patient_dict else ""
                            st.markdown(f"  - RF:{k_code} score={score:.0f} {match}")
                    else:
                        st.warning(f"Boala {top_code} nu are RF in rf_profiles!")

            ranking_list = raw_output.get("ranking", [])
            if not ranking_list:
                st.info("Niciun candidat în ranking.")
            else:
                # Verifica RF in profilul CURENT (nu in rezultate stale)
                rf_in_current = [(k,v) for k,v in patient_dict.items() if k[1]=="RiskF"]
                all_rf_zero = all(r.get("rf_net", 0) == 0 for r in ranking_list)

                if not rf_in_current:
                    st.info("Niciun element RiskF în profilul pacientului curent. "
                            "Adaugă RF din tab-ul **Input → Risk Factors**.")
                elif all_rf_zero:
                    st.warning(
                        f"⚠ Profilul are **{len(rf_in_current)} RF** dar rezultatele nu "
                        f"reflecta impactul lor. Apasă **▶ Run ranking** pentru a recalcula."
                    )
                else:
                    st.success(f"✓ {len(rf_in_current)} RF activi — impactul este reflectat în tabel.")

                rf_rows = []
                for r in ranking_list:
                    rf_net = r.get("rf_net", 0.0)
                    rf_rows.append({
                        "Rank"    : r["rank"],
                        "Boala"   : r["name"],
                        "CR final": round(r["cr"], 4),
                        "CR semio": round(r.get("cr_semio", r["cr"]), 4),
                        "RF net"  : round(rf_net, 4),
                        "Tip"     : ("▲ boost" if rf_net > 0.0001
                                     else "▼ penalizare" if rf_net < -0.0001
                                     else "—"),
                    })
                rf_df = pd.DataFrame(rf_rows)
                st.dataframe(
                    rf_df, hide_index=True, use_container_width=True,
                    column_config={
                        "CR final": st.column_config.NumberColumn(format="%.4f"),
                        "CR semio": st.column_config.NumberColumn(format="%.4f"),
                        "RF net"  : st.column_config.NumberColumn(format="%.4f"),
                    }
                )

                # Detail per disease
                st.markdown("---")
                st.markdown("**Detaliu per diagnostic:**")
                options = [f"{r['rank']}. {r['name']}" for r in ranking_list]
                sel_idx = st.selectbox("Selecteaza diagnosticul", range(len(options)),
                                       format_func=lambda i: options[i], key="rf_detail_sel")
                sel_r = ranking_list[int(sel_idx)]
                rf_detail = sel_r.get("rf_detail", [])

                def ename_rf(code):
                    nm = engine.symp_map.get(code) or engine.sign_map.get(code)
                    return nm.title() if nm else f"RF:{code}"

                rf_steps = sel_r.get("rf_steps", [])
                cr_s     = sel_r.get("cr_semio", sel_r["cr"])
                rf_net   = sel_r.get("rf_net", 0.0)

                c1, c2, c3 = st.columns(3)
                with c1: kpi_card("CR semiologic", f"{cr_s:.4f}")
                with c2: kpi_card("Impact RF net", f"{rf_net:+.4f}")
                with c3: kpi_card("CR final", f"{sel_r['cr']:.4f}")

                if not rf_steps:
                    st.info("Niciun pas RF pentru acest diagnostic.")
                else:
                    tip_labels = {
                        "A1_boost"       : "▲ A1 boost",
                        "A2_penalizare"  : "▼ A2 penalizare",
                        "B_penalizare"   : "▼ B penalizare",
                    }
                    det_rows = []
                    for s in rf_steps:
                        det_rows.append({
                            "RF cod"   : s["rf_code"],
                            "Tip"      : tip_labels.get(s["tip"], s["tip"]),
                            "sfr"      : s["sfr"],
                            "Δ S"      : s["delta"],
                            "S inainte": s["S_before"],
                            "S dupa"   : s["S_after"],
                        })
                    st.dataframe(
                        pd.DataFrame(det_rows),
                        hide_index=True, use_container_width=True,
                        column_config={
                            "Δ S"      : st.column_config.NumberColumn(format="%+.4f"),
                            "S inainte": st.column_config.NumberColumn(format="%.4f"),
                            "S dupa"   : st.column_config.NumberColumn(format="%.4f"),
                            "sfr"      : st.column_config.NumberColumn(format="%.0f"),
                        }
                    )

    with tabs[7]:
        st.markdown("#### Factor demografic")
        note(
            "Model triangular asimetric [Agemin, mean, Agemax] ponderat prin AgeConfidence. "
            "HardExclusion = boala exclusa complet (confidence=high, varsta in afara intervalului)."
        )
        if raw_output is None:
            st.caption("Ruleaza ranking-ul mai intai.")
        else:
            from .demographics_v2 import apply_age_factor_v2
            from .config import DEFAULT_AGE_META, DEFAULT_MALADIES_PY
            import pandas as _pd

            _preview        = st.session_state.get("titus_demo_preview")
            demo_is_applied = st.session_state.get("titus_demo_applied", False)
            patient_age     = int(
                st.session_state.get("patient_profile", {}).get("age_in_months", 0) or 0
            )

            if _preview is None and not demo_is_applied:
                # ── Starea 1: formular de calcul ──────────────────────────────
                age_path = st.text_input("Order_AgeMetadata_FINAL.xlsx",
                                         str(DEFAULT_AGE_META), key="age_meta_path")
                mal_path = st.text_input("Maladies.xlsx",
                                         str(DEFAULT_MALADIES_PY), key="mal_path_demo")
                kpi_card("Varsta pacient", f"{patient_age} luni ({patient_age//12} ani)")

                if st.button("🧬 Calculeaza factor demografic",
                             key="demo_calc_btn", use_container_width=True,
                             type="primary"):
                    try:
                        age_df = _pd.read_excel(age_path)
                        mal_df = _pd.read_excel(mal_path)
                        _demo  = apply_age_factor_v2(
                            ranking_df, age_df, mal_df, patient_age,
                            use_family_fallback=True,
                        )
                        if "CR_demographic" in _demo.columns:
                            _demo = _demo.sort_values("CR_demographic", ascending=False)
                            _demo["Rank_demo"] = range(1, len(_demo)+1)
                        st.session_state["titus_demo_preview"] = _demo
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Eroare: {ex}")

            else:
                # ── Starea 2: preview + Apply/Cancel ─────────────────────────
                if _preview is not None:
                    show_cols = [col for col in
                        ["Rank_demo","Rank","Boala","CR","CR_demographic",
                         "AgeFactor","HardExclusion","AgeLayer"]
                        if col in _preview.columns]
                    col_cfg = {
                        "CR"            : st.column_config.NumberColumn(format="%.4f"),
                        "CR_demographic": st.column_config.NumberColumn("CR×Demo", format="%.4f"),
                        "AgeFactor"     : st.column_config.NumberColumn(format="%.4f"),
                        "HardExclusion" : st.column_config.CheckboxColumn("Exclus"),
                    }
                    excluded_n = int(_preview.get(
                        "HardExclusion", _pd.Series([False]*len(_preview))).sum())

                    c1, c2, c3 = st.columns(3)
                    with c1: kpi_card("Boli analizate", str(len(_preview)))
                    with c2: kpi_card("Excluse dur",    str(excluded_n))
                    with c3: kpi_card("Varsta",         f"{patient_age} luni")

                    st.dataframe(
                        _preview[show_cols],
                        hide_index=True, use_container_width=True,
                        column_config={k:v for k,v in col_cfg.items()
                                       if k in _preview.columns}
                    )

                col_apply, col_cancel, col_reset = st.columns(3)
                with col_apply:
                    if st.button("✅ Apply factor demografic", type="primary",
                                 key="demo_apply_btn", use_container_width=True,
                                 disabled=demo_is_applied):
                        st.session_state["titus_demo_applied"] = True
                        st.session_state["titus_demo_df"]      = _preview.copy()
                        st.rerun()
                with col_cancel:
                    if st.button("✕ Anulare factor demografic",
                                 key="demo_cancel_btn2", use_container_width=True,
                                 disabled=not demo_is_applied):
                        st.session_state["titus_demo_applied"] = False
                        st.session_state["titus_demo_df"]      = None
                        st.rerun()
                with col_reset:
                    if st.button("🔄 Recalculeaza",
                                 key="demo_reset_btn", use_container_width=True):
                        st.session_state["titus_demo_preview"] = None
                        st.session_state["titus_demo_applied"] = False
                        st.session_state["titus_demo_df"]      = None
                        st.rerun()

    with tabs[8]:
        st.markdown("#### Export sesiune")
        if raw_output is None:
            st.caption("Ruleaza ranking-ul mai intai.")
        else:
            import json as _json
            col1, col2 = st.columns(2)
            with col1:
                # Export JSON
                session_data = {
                    "elements": [
                        {"code": ce, "nature": nl, "score": sc}
                        for ce, nl, sc in titus_elems
                    ],
                    "ranking"     : raw_output.get("ranking", []),
                    "waiting_room": raw_output.get("waiting_room", []),
                    "comorbidity" : raw_output.get("comorbidity"),
                }
                json_str = _json.dumps(session_data, indent=2, ensure_ascii=False)
                st.download_button(
                    "⬇ Descarca JSON",
                    data=json_str,
                    file_name="titus_session.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with col2:
                # Export text
                lines = ["TITUS — Export sesiune", "=" * 60]
                lines.append(f"Profil ({len(titus_elems)} elemente):")
                for ce, nl, sc in titus_elems:
                    lines.append(f"  {nl:<6} {ce:>4}  {sc}")
                lines.append("")
                lines.append("Ranking:")
                for r in raw_output.get("ranking", []):
                    lines.append(
                        f"  {r['rank']:>2}. [{r['cr_class']}] cr={r['cr']:.4f}  {r['name']}"
                    )
                wr = raw_output.get("waiting_room", [])
                if wr:
                    lines.append("")
                    lines.append("Waiting Room:")
                    for w in wr:
                        flag = "RARE  " if w["rare"] else "COMMON"
                        lines.append(f"  {flag}  cr={w['cr']:.4f}  {w['name']}")
                txt = "\n".join(lines)
                st.download_button(
                    "⬇ Descarca TXT",
                    data=txt,
                    file_name="titus_export.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            st.text_area("Previzualizare export", value="\n".join(lines[:30] + ["..."]),
                         height=300, disabled=True)
