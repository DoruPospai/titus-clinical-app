# NOSO_ranking.py
# Pasul 3 — Ranking semiologic

import streamlit as st
from .NOSO_loader import diagnose, get_disease_name, get_element_name, load_engine


def render_ranking(root: str = ""):
    st.subheader("Ranking semiologic NOSO")

    ss = st.session_state
    elements_ready = ss.get("noso_elements_ready", [])

    if not elements_ready:
        st.info("Nu există elemente pregătite. "
                "Completați profilul în **Review & Finalize** și apăsați butonul de confirmare.")
        return

    with st.expander(f"Profil activ — {len(elements_ready)} elemente"):
        for code, nat, sc in elements_ready:
            name = get_element_name(code, nat, root)
            icon = {"Sympt": "🔵", "Signe": "🟣", "RiskF": "🟢"}.get(nat, "⚪")
            st.markdown(f"{icon} `{code}` {name} — score {sc}")

    st.divider()

    result = ss.get("noso_ranking_result")
    if not result:
        st.info("Calculați rankingul din **Introducere date → Review & Finalize → 📊 Calculează ranking**.")
        return

    ranking = result.get("ranking", [])
    waiting = result.get("waiting_room", [])
    params  = ss.get("noso_ranking_params", {})

    st.markdown(
        f"**{len(ranking)}** diagnostice peste prag  |  "
        f"**{len(waiting)}** în waiting room  |  "
        f"prag CR = {params.get('cr_thr', 0.20):.2f}  |  "
        f"{params.get('n_elements', 0)} elemente active"
    )

    if not ranking:
        st.warning("Niciun diagnostic peste prag. Reduceți pragul CR sau adăugați mai multe elemente.")
        return

    try:
        engine = load_engine(root)
    except Exception:
        engine = None

    patient_map = {(int(c), n): sc for c, n, sc in elements_ready}
    M_P = sum(patient_map.values()) or 1

    for i, dis in enumerate(ranking):
        cr   = dis.get("cr", 0)
        code = dis.get("code", 0)
        name = _get_name(dis, code, root)
        fill = "█" * int(cr * 20) + "░" * (20 - int(cr * 20))

        # Container principal — collapsed by default
        with st.expander(f"**#{i+1}  {name}**   CR = {cr:.3f}  [{fill}]", expanded=False):

            col_profile, col_metric = st.columns([3, 1])

            with col_metric:
                st.metric("CR", f"{cr:.3f}")
                st.caption(f"Cod: {code}")

            with col_profile:
                if engine is None:
                    for m in dis.get("matched", []):
                        st.markdown(f"- `{m}`")
                    continue

                disease_profile = engine.profiles.get(int(code), {})
                if not disease_profile:
                    st.caption("Profil indisponibil")
                    continue

                sorted_profile = sorted(
                    disease_profile.items(),
                    key=lambda x: x[1],
                    reverse=True
                )

                # Stil CSS inline pentru separarea vizuală container/conținut
                st.markdown("""
<style>
.elem-row {
    background: #f8f9fb;
    border-left: 3px solid #dee2e6;
    border-radius: 4px;
    padding: 6px 10px;
    margin-bottom: 4px;
    font-size: 0.88rem;
    line-height: 1.5;
}
.elem-row.match {
    background: #eaf4ea;
    border-left: 3px solid #28a745;
}
.elem-row.no-match {
    background: #f8f9fb;
    border-left: 3px solid #adb5bd;
    opacity: 0.75;
}
.contrib-bar {
    display: inline-block;
    height: 8px;
    border-radius: 3px;
    vertical-align: middle;
    margin-left: 4px;
}
</style>
""", unsafe_allow_html=True)

                for (elem_code, elem_nat), elem_score in sorted_profile:
                    elem_name     = get_element_name(elem_code, elem_nat, root)
                    nat_icon      = {"Sympt": "🔵", "Signe": "🟣", "RiskF": "🟢"}.get(elem_nat, "⚪")
                    score_pacient = patient_map.get((elem_code, elem_nat), 0)
                    overlap       = min(score_pacient, elem_score)
                    contributie   = round(overlap / M_P * 100)
                    has_match     = score_pacient > 0

                    if elem_score >= 150:
                        intensity_html = '<span style="color:#dc3545;font-weight:600">●</span> puternic'
                    elif elem_score >= 100:
                        intensity_html = '<span style="color:#fd7e14;font-weight:600">●</span> moderat'
                    else:
                        intensity_html = '<span style="color:#6c757d;font-weight:600">●</span> slab'

                    # Bară contribuție proporțională
                    bar_pct   = contributie  # 0-100
                    bar_color = "#28a745" if has_match else "#adb5bd"
                    bar_html  = (
                        f'<span class="contrib-bar" style="width:{bar_pct * 1.4:.0f}px;'
                        f'background:{bar_color};"></span>'
                        f' <span style="color:{bar_color};font-size:0.8rem">{contributie}%</span>'
                    )

                    match_icon = "✅" if has_match else "&nbsp;&nbsp;"
                    row_class  = "elem-row match" if has_match else "elem-row no-match"

                    st.markdown(
                        f'<div class="{row_class}">'
                        f'{match_icon} {nat_icon} <strong>{elem_name}</strong>'
                        f'&nbsp;&nbsp;{intensity_html}'
                        f'&nbsp;&nbsp;&nbsp;{bar_html}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

    if waiting:
        with st.expander(f"Waiting room — {len(waiting)} boli (date insuficiente)", expanded=False):
            rows = [{"Boala": _get_name(w, w.get("code", 0), root),
                     "CR":    f"{w.get('cr', 0):.3f}",
                     "Cod":   str(w.get("code", ""))}
                    for w in waiting[:30]]
            st.dataframe(rows, use_container_width=True)

    ss["noso_ranking_for_context"] = ranking


def _get_name(dis: dict, code: int, root: str) -> str:
    for key in ("name_en", "name_ro", "name", "nom", "NomMaladie"):
        val = dis.get(key, "")
        if val and str(val).strip():
            return str(val).strip()
    return get_disease_name(int(code), root)
