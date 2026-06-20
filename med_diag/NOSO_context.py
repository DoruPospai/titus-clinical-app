# NOSO_context.py
# Pasul 4 — Strat contextual
# Filtrare și reordonare post-ranking pe baza profilului pacientului

import streamlit as st
import pandas as pd
from pathlib import Path
from .NOSO_loader import load_catalogs, get_disease_name


def render_context(root: str = ""):
    st.subheader("Strat contextual")
    st.caption("Filtrare și ajustare ranking pe baza profilului demografic și clinic.")

    ss    = st.session_state
    ranking = ss.get("noso_ranking_for_context", [])

    if not ranking:
        st.info("Rulați mai întâi **Ranking semiologic** pentru a aplica filtrul contextual.")
        return

    # ── Import automat din Profil Pacient validat ─────────────────────────────
    pp = ss.get("patient_profile", {})

    # Mapping living_in → Geografie + RF LIVING IN
    _LIVING_GEO = {
        "Europe North":   ("Europa",   251),  # RF:0251 LIVING IN EUROPE NORTH
        "Europe South":   ("Europa",   263),  # RF:0263 LIVING IN EUROPE SOUTH WEST
        "America North":  ("America",  190),  # RF:0190 LIVING IN AMERICA NORTH
        "America South":  ("America",  207),  # RF:0191 LIVING IN AMERICA SOUTH
        "Asia North":     ("Asia",     553),  # RF:0553 LIVING IN ASIA NORTH
        "Asia South":     ("Asia",     200),  # RF:0200 LIVING IN ASIA SOUTH
        "Africa North":   ("Africa",   431),  # RF:0431 LIVING IN AFRICA NORTH
        "Africa South":   ("Africa",   413),  # RF:0413 LIVING IN AFRICA SOUTH
        "Africa Central": ("Africa",   209),  # RF:0209 LIVING IN AFRICA CENTRAL
        "Africa West":    ("Africa",   189),  # RF:0189 LIVING IN AFRICA WEST
        "Australia":      ("Global",   186),  # RF:0186 LIVING IN AUSTRALIA
    }
    _TROPICAL_REGIONS = {"America South","Asia South","Africa North","Africa South",
                         "Africa Central","Africa West"}

    _geo_options   = ["Global", "Europa", "Africa", "Asia", "America", "Tropical"]
    _living_in     = pp.get("living_in", "")
    _geo_tuple     = _LIVING_GEO.get(_living_in, ("Global", None))
    _geo_default   = _geo_tuple[0]
    _living_rf     = _geo_tuple[1]  # RF cod pentru living_in

    # Mapping ethnics → RF
    _ETHNIC_RF = {
        "Caucasian": 99,   # RF:0099 CAUCASIAN
        "Asian":     57,   # RF:0057 ASIAN
    }
    _ethnic_rf = _ETHNIC_RF.get(pp.get("ethnics", ""), None)

    # Condiții speciale → RF
    _SPECIAL_RF = {
        "Altitudine înaltă":                              642,  # LIVING IN HIGH ALTITUDE
        "Călătorie recentă în zonă endemică / tropicală": 184,  # CLIMATE TROPICAL-SUBTROPICAL
        "Zonă epidemie activă":                           997,  # COVID / epidemie
        "Pacient imunodeprimat":                          47,   # IMMUNOCOMPROMISED
        "Mediu confinat (închisoare, cămin, spital)":     974,  # LIVING CONFINED
    }
    _special_conds = pp.get("special_conditions", [])
    _special_rfs   = [_SPECIAL_RF[c] for c in _special_conds if c in _SPECIAL_RF]

    # RF-uri contextuale activate automat
    _auto_rfs = set()
    if _living_rf:           _auto_rfs.add(_living_rf)
    if _ethnic_rf:           _auto_rfs.add(_ethnic_rf)
    if _living_in in _TROPICAL_REGIONS: _auto_rfs.add(184)  # CLIMATE TROPICAL-SUBTROPICAL
    for rf_code in _special_rfs: _auto_rfs.add(rf_code)

    ss["ctx_auto_rfs"] = list(_auto_rfs)

    # ── Profil pacient — copiat exact din fișa pacientului ───────────────────
    st.markdown("**Profil pacient**")

    pp         = ss.get("patient_profile", {})
    age_months = int(pp.get("age_in_months", 0))
    varsta_luni = age_months
    gender     = pp.get("gender", "")
    sex        = {"Male": "Feminin" if False else "Masculin",
                  "Female": "Feminin"}.get(gender, "Necunoscut")
    sex        = {"Male": "Masculin", "Female": "Feminin"}.get(gender, "Necunoscut")
    gravida    = (pp.get("pregnancy", "No") == "Yes") and (gender == "Female")
    living_in  = pp.get("living_in", "")
    ethnics    = pp.get("ethnics", "")
    dob        = pp.get("dob", "")
    pregnancy  = pp.get("pregnancy", "No")
    weeks      = pp.get("weeks_pregnant", None)
    user_id    = pp.get("user_id", "")
    special    = pp.get("special_conditions", [])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("User ID",       value=str(user_id),   disabled=True, key="_ctx_uid")
        st.text_input("Date of birth", value=str(dob),       disabled=True, key="_ctx_dob")
    with c2:
        st.text_input("Sex",           value=gender,         disabled=True, key="_ctx_sex")
        st.text_input("Living in",     value=living_in,      disabled=True, key="_ctx_liv")
    with c3:
        st.text_input("Ethnics",       value=ethnics,        disabled=True, key="_ctx_eth")
        preg_str = pregnancy
        if pregnancy == "Yes" and weeks:
            preg_str = f"Yes — {weeks} săpt."
        st.text_input("Pregnancy",     value=preg_str,       disabled=True, key="_ctx_preg")

    c4, _ = st.columns([1, 2])
    with c4:
        st.text_input("Age (months)",  value=str(age_months), disabled=True, key="_ctx_age")

    if special:
        st.caption(f"Condiții speciale: {', '.join(special)}")

    st.divider()

    # ── RF-uri activate automat din profil ────────────────────────────────────
    if _auto_rfs:
        _rf_candidates = [
            Path(root) / "Riskf.xlsx",
            Path(root) / "data" / "Riskf.xlsx",
            Path(root) / "catalogs" / "Riskf.xlsx",
            Path(__file__).resolve().parent.parent / "Riskf.xlsx",
        ]
        rf_df = pd.DataFrame()
        for _p in _rf_candidates:
            if _p.exists():
                try:
                    rf_df = pd.read_excel(str(_p), usecols=["CodeFactor", "NomRiskFactor"])
                    break
                except Exception:
                    pass

        rf_labels = []
        for code in sorted(_auto_rfs):
            if not rf_df.empty:
                row = rf_df[rf_df["CodeFactor"] == code]
                label = row.iloc[0]["NomRiskFactor"] if len(row) else f"RF:{code:04d}"
            else:
                label = f"RF:{code:04d}"
            rf_labels.append(f"RF:{code:04d} — {label}")

        st.caption("RF activate automat din profilul pacientului:")
        st.info("  |  ".join(rf_labels))

    # ── Incarca mal_women_map pentru filtrul de sex ──────────────────────────
    _mal_women_map = {}
    try:
        from .NOSO_loader import load_catalogs as _lc
        _cats = _lc(root)
        _mal_women_map = _cats.get("mal_women_map", {})
    except Exception:
        pass

    # ── Incarca Tabel2 pentru RF per boala ────────────────────────────────────
    _t2_rf = {}  # {code_maladie: set(rf_codes)}
    _t2_rf_score = {}  # {code_maladie: {rf_code: score}}
    _t2_load_error = ""
    _t2_path_cfg = None
    try:
        from .config import DEFAULT_TABEL2
        _t2_path_cfg = DEFAULT_TABEL2
    except Exception:
        pass

    _t2_candidates = [
        _t2_path_cfg,
        Path(root) / "data_clean" / "Tabel2_Titus.xlsx",
        Path(root) / "Tabel2_Titus.xlsx",
        Path(__file__).resolve().parent.parent / "data_clean" / "Tabel2_Titus.xlsx",
        Path(__file__).resolve().parent.parent / "Tabel2_Titus.xlsx",
    ]
    for _cand in _t2_candidates:
        if _cand is None:
            continue
        try:
            _cp = Path(str(_cand))
            if not _cp.exists():
                continue
            _t2 = pd.read_excel(str(_cp), usecols=["CodeMaladie","CodeElement","NatureLien","Score"])
            _t2_riskf = _t2[_t2["NatureLien"] == "RiskF"]
            for cm, grp in _t2_riskf.groupby("CodeMaladie"):
                _t2_rf[int(cm)] = set(grp["CodeElement"].astype(int).tolist())
                _t2_rf_score[int(cm)] = {int(r["CodeElement"]): int(r["Score"]) for _, r in grp.iterrows()}
            break
        except Exception as _e:
            _t2_load_error = str(_e)

    if not _t2_rf:
        st.warning(f"⚠️ Tabel2 RF: nu s-a putut incarca ({_t2_load_error or 'cale negasita'}). RF clinic dezactivat.")

    # ── Mapare CodeCategorie RF → scor pacient ────────────────────────────────
    _CAT_SCORE = {3:150, 4:100, 2:100, 1:100, 6:100, 11:100, 8:100, 5:100, 7:50, 9:50, 23:50}
    _rf_patient_score = {}  # {rf_code: scor_P}
    try:
        _rf_df_cat = pd.read_excel(str(Path(root) / "data_clean" / "Riskf.xlsx"),
                                   usecols=["CodeFactor","CodeCategorie"])
        for _, row in _rf_df_cat.iterrows():
            c   = int(row["CodeFactor"])
            cat = int(row["CodeCategorie"]) if pd.notna(row["CodeCategorie"]) else 23
            _rf_patient_score[c] = _CAT_SCORE.get(cat, 100)
    except Exception:
        # Fallback: cauta Riskf.xlsx in mai multe locatii
        for _rp in [Path(root) / "Riskf.xlsx",
                    Path(__file__).resolve().parent.parent / "data_clean" / "Riskf.xlsx"]:
            if _rp.exists():
                try:
                    _rf_df_cat = pd.read_excel(str(_rp), usecols=["CodeFactor","CodeCategorie"])
                    for _, row in _rf_df_cat.iterrows():
                        c   = int(row["CodeFactor"])
                        cat = int(row["CodeCategorie"]) if pd.notna(row["CodeCategorie"]) else 23
                        _rf_patient_score[c] = _CAT_SCORE.get(cat, 100)
                    break
                except Exception:
                    pass



    # RF pacient: auto din profil + RF confirmate explicit în Review & Finalize
    _patient_rf = set(_auto_rfs)
    for code in ss.get("confirmed_rf_codes", []):
        try:
            _patient_rf.add(int(code))
        except Exception:
            pass

    # Setul valid de coduri RF — din toate valorile _t2_rf
    _all_rf_codes = set()
    for s in _t2_rf.values():
        _all_rf_codes.update(s)

    # RF CLINICE — codurile confirmate care sunt RF reali (există în Tabel2 ca RiskF)
    _patient_rf_clinical = set()
    # Scoruri reale din MedDiagInput (salvate la Confirma)
    _confirmed_rf_scores = ss.get("confirmed_rf_scores", {})
    for code in ss.get("confirmed_rf_codes", []):
        try:
            c = int(code)
            if c in _all_rf_codes:
                _patient_rf_clinical.add(c)
                # Suprascrie scorul din categorie cu scorul real din MedDiagInput
                if c in _confirmed_rf_scores:
                    _rf_patient_score[c] = int(_confirmed_rf_scores[c])
        except Exception:
            pass
    # Fallback: preia RF din editor_rows (ANAM automat fara Confirma)
    if not _patient_rf_clinical:
        for row in ss.get("editor_rows", []):
            try:
                if str(row.get("Nature", "")) == "RiskF":
                    c = int(row.get("Code", 0))
                    if c in _all_rf_codes:
                        _patient_rf_clinical.add(c)
                        w = row.get("Weight", None)
                        if w:
                            _rf_patient_score[c] = int(w)
            except Exception:
                pass

    # Constante bonus/penalizare — vezi Regula RF în bucla de filtrare
    # alpha=0.20 (bonus padding_head), beta=0.15 (penalizare multiplicativa)

    # ── Incarca AgeMetadata pentru demographics_v2 ────────────────────────────
    _age_meta = {}
    _age_candidates = [
        Path(root) / "Order_AgeMetadata_FINAL.xlsx",
        Path(root) / "data" / "Order_AgeMetadata_FINAL.xlsx",
        Path(__file__).resolve().parent.parent / "Order_AgeMetadata_FINAL.xlsx",
    ]
    for _p in _age_candidates:
        if _p.exists():
            try:
                _am = pd.read_excel(str(_p))
                for _, _r in _am.iterrows():
                    _age_meta[int(_r["CodeMaladie"])] = _r.to_dict()
                break
            except Exception:
                pass

    filtered = []
    excluded = []

    for dis in ranking:
        code  = int(dis.get("code", 0))
        cr    = dis.get("cr", 0)
        name  = _get_name(dis, code, root)

        reasons_excl = []
        boost_factor = 1.0

        # Filtru vârstă (dacă motorul expune agemin/agemax)
        agemin = dis.get("agemin", 0)
        agemax = dis.get("agemax", 9999)
        if varsta_luni > 0:
            if varsta_luni < int(agemin):
                reasons_excl.append(f"Vârsta {varsta_luni//12}a sub min {int(agemin)//12}a")
            elif varsta_luni > int(agemax):
                reasons_excl.append(f"Vârsta {varsta_luni//12}a peste max {int(agemax)//12}a")

        # Filtru sex — excludere dura
        women_flag = dis.get("women", None)
        if women_flag is None and _mal_women_map:
            women_flag = _mal_women_map.get(code, None)
        if sex == "Masculin" and women_flag is not None and str(women_flag).strip() not in ("", "nan") and int(float(str(women_flag))) == 100:
            reasons_excl.append("Boală exclusiv feminină")
        elif sex == "Feminin" and women_flag is not None and str(women_flag).strip() not in ("", "nan") and int(float(str(women_flag))) == 0:
            reasons_excl.append("Boală exclusiv masculină")

        # Graviditate — excludere dura
        if ss.get("ctx_gravida") and dis.get("pregnancy") == "N":
            reasons_excl.append("Incompatibil cu sarcina")

        # ── Calcul CR ajustat — ordine: RF → sex → vârstă ────────────────────

        # ── Stratul 1: RF integrat în CR — Soluția 1 pură ────────────────────
        # M_P = M_P_SS + M_P_RF (masa pacient fixă, RF inclus)
        # CR_nou = (overlap_SS + overlap_RF) / M_P
        # overlap_RF = sum(min(scor_P_rf, scor_B_rf)) pentru RF comuni
        cr_rf    = cr
        rf_label = ""
        dis_rf_scores = _t2_rf_score.get(code, {})

        rf_overlap_clin = _patient_rf_clinical & set(dis_rf_scores.keys())
        rf_overlap_geo  = (_patient_rf - _patient_rf_clinical) & set(dis_rf_scores.keys())

        # Masa RF pacient — doar RF clinice confirmate (nu geo/auto)
        # RF geo nu intra in M_P_rf pentru a nu penaliza boli fara context geografic
        M_P_rf = 0.0
        for rfc in _patient_rf_clinical:
            M_P_rf += _rf_patient_score.get(rfc, 100)

        if M_P_rf > 0:
            # Overlap RF: min(scor_P, scor_B) pentru fiecare RF comun
            overlap_rf = 0.0
            for rfc in rf_overlap_clin:
                scor_p = _rf_patient_score.get(rfc, 100)
                scor_b = dis_rf_scores.get(rfc, 100)
                overlap_rf += min(scor_p, scor_b)
            for rfc in rf_overlap_geo:
                scor_p = _rf_patient_score.get(rfc, 50)
                scor_b = dis_rf_scores.get(rfc, 50)
                overlap_rf += min(scor_p, scor_b) * 0.5

            # CR_nou = (overlap_ss + overlap_rf) / (M_P_ss + M_P_rf)
            # M_P_ss: din session_state (calculat la Confirma) sau din Titus_inference
            # overlap_ss = cr × M_P_ss (CR semiologic = overlap_ss / M_P_ss prin definitie)
            M_P_ss_sess = ss.get("M_P_ss", None)
            M_P_ss_tit  = dis.get("M_P_ss", None)
            M_P_ss      = M_P_ss_sess or M_P_ss_tit or 750
            overlap_ss  = dis.get("overlap_ss", None)
            if overlap_ss is None:
                overlap_ss = cr * M_P_ss
            cr_nou = (overlap_ss + overlap_rf) / (M_P_ss + M_P_rf)
            cr_rf  = round(cr_nou, 4)
            delta  = round(cr_rf - cr, 3)
            if abs(delta) >= 0.001:
                rf_label = f"RF+{delta}" if delta >= 0 else f"RF{delta}"
        # RF2 PENALIZARE eliminată — absența overlap nu penalizează

        # Stratul 2: sex — excludere hard pentru boli sex-exclusive, boost pentru compatibile
        sex_factor = 1.0
        sex_excl   = False
        # women_flag deja corectat din _mal_women_map mai sus
        if women_flag is not None and str(women_flag).strip() not in ("", "nan"):
            wf = int(float(str(women_flag)))
            if sex == "Feminin" and wf == 0:
                sex_factor = 0.0
                sex_excl   = True
                reasons_excl.append("Exclus sex: boala exclusiv masculina")
            elif sex == "Masculin" and wf == 100:
                sex_factor = 0.0
                sex_excl   = True
                reasons_excl.append("Exclus sex: boala exclusiv feminina")
            elif sex == "Feminin" and wf > 60:
                sex_factor = 1.1
            elif sex == "Masculin" and wf < 40:
                sex_factor = 1.1
        cr_sex = round(cr_rf * sex_factor, 4)

        # Stratul 3: vârstă — AgeFactor din demographics_v2
        age_factor = 1.0
        age_layer  = "no_age"
        if varsta_luni > 0 and _age_meta:
            row_meta = _age_meta.get(code, {})
            if row_meta:
                from .demographics_v2 import compute_age_factor_v2
                age_result = compute_age_factor_v2(float(varsta_luni), row_meta)
                if age_result.get("HardExclusion"):
                    reasons_excl.append(age_result.get("F12Detail") or "Exclus vârstă")
                else:
                    age_factor = age_result.get("AgeFactor", 1.0)
                    age_layer  = age_result.get("Layer", "interval")
        cr_adjusted = round(cr_sex * age_factor, 4)
        boost_factor = round(cr_adjusted / cr, 4) if cr > 0 else 1.0
        # ─────────────────────────────────────────────────────────────────────

        entry = {**dis, "name_display": name, "cr_adjusted": cr_adjusted,
                 "boost": boost_factor, "rf_label": rf_label,
                 "age_layer": age_layer}

        if reasons_excl:
            excluded.append({**entry, "excluded_reason": "; ".join(reasons_excl)})
        else:
            filtered.append(entry)

    # Sortare după CR ajustat
    filtered.sort(key=lambda x: x["cr_adjusted"], reverse=True)

    # Ranking original sortat după CR brut
    ranking_orig = sorted(filtered + excluded, key=lambda x: x.get("cr", 0), reverse=True)
    ranking_orig = [d for d in ranking_orig if d.get("cr", 0) >= 0.20]

    # ── Încarcă date auxiliare pentru profilul bolii ─────────────────────────
    _mal_desc = {}  # {code: descriere_ro}
    _t2_profile = {}  # {code: {ss: [], rf: []}}
    try:
        _mal_path_candidates = [
            Path(root) / "Maladies.xlsx",
            Path(root) / "data_clean" / "Maladies.xlsx",
            Path(__file__).resolve().parent.parent / "Maladies.xlsx",
        ]
        for _mp in _mal_path_candidates:
            if _mp.exists():
                _mal = pd.read_excel(str(_mp), usecols=["CodeMaladie","NomMaladie","DescriereRO_CLEAN"])
                for _, _r in _mal.iterrows():
                    _mal_desc[int(_r["CodeMaladie"])] = str(_r["DescriereRO_CLEAN"]) if pd.notna(_r["DescriereRO_CLEAN"]) else ""
                break
    except Exception:
        pass

    try:
        # Reutilizează aceeași listă de candidați și aceeași logică de fallback
        # ca la încărcarea _t2_rf (mai sus) — _t2_path nu exista ca variabilă,
        # cauza pentru care "Elemente semiologice" / "Factori de risc" apăreau
        # mereu goale în card, indiferent de conținutul real al Tabel2.
        _t2_full = None
        for _cand in _t2_candidates:
            if _cand is None:
                continue
            _cp = Path(str(_cand))
            if not _cp.exists():
                continue
            _t2_full = pd.read_excel(
                str(_cp),
                usecols=["CodeMaladie","CodeElement","NomElement","NomElementRO","NatureLien","Score"],
            )
            break

        if _t2_full is not None:
            for cm, grp in _t2_full.groupby("CodeMaladie"):
                ss_items = grp[grp["NatureLien"].isin(["Sympt","Signe"])].sort_values("Score", ascending=False)
                rf_items = grp[grp["NatureLien"] == "RiskF"].sort_values("Score", ascending=False)
                _t2_profile[int(cm)] = {
                    "ss": [
                        (int(r["CodeElement"]), str(r["NatureLien"]), str(r["NomElementRO"]) or str(r["NomElement"]), int(r["Score"]))
                        for _, r in ss_items.iterrows()
                    ],
                    "rf": [
                        (int(r["CodeElement"]), str(r["NatureLien"]), str(r["NomElementRO"]) or str(r["NomElement"]), int(r["Score"]))
                        for _, r in rf_items.iterrows()
                    ],
                }
    except Exception:
        pass

    # ── Masa pacient + map (code, nature) -> scor_pacient, pentru contribuție ──
    # Aceeași sursă ca în NOSO_ranking.py — lista de elemente confirmate ale
    # pacientului curent, cu scorurile lor individuale.
    _elements_ready = ss.get("noso_elements_ready", [])
    _patient_score_map = {(int(c), str(n)): int(s) for c, n, s in _elements_ready}
    _M_P_ss_for_contrib = ss.get("M_P_ss") or (sum(s for c, n, s in _elements_ready if n in ("Sympt", "Signe")) or 1)


    def _score_badge(score):
        if score >= 150: return "🔴"
        if score >= 100: return "🟠"
        return "🟡"

    def _render_disease_card(i, dis, cr_display, delta_str, rf_str, show_reco):
        code = int(dis.get("code", 0))
        name = dis.get("name_display", "")
        fill = "█" * int(cr_display * 20) + "░" * (20 - int(cr_display * 20))
        header = f"**#{i+1}** {name}  \n`CR = {cr_display:.3f}`{delta_str}{rf_str} [{fill}]"
        st.markdown(header)

        with st.expander("📋 Profil & detalii"):
            prof = _t2_profile.get(code, {})
            ss_list = prof.get("ss", [])
            rf_list = prof.get("rf", [])

            def _render_element_line(elem_code, nature, nom, score_boala):
                score_pacient = _patient_score_map.get((elem_code, nature), 0)
                has_match = score_pacient > 0
                overlap = min(score_pacient, score_boala) if has_match else 0
                contributie = round(overlap / _M_P_ss_for_contrib * 100) if _M_P_ss_for_contrib else 0
                match_icon = "✅" if has_match else "▫️"
                contrib_txt = f" — **{contributie}%**" if has_match else " — 0%"
                st.markdown(f"{match_icon} {_score_badge(score_boala)} {nom}{contrib_txt}")

            col_ss, col_rf2 = st.columns(2)
            with col_ss:
                st.markdown("**Elemente semiologice**")
                if ss_list:
                    for elem_code, nature, nom, score in ss_list:
                        _render_element_line(elem_code, nature, nom, score)
                else:
                    st.caption("—")
            with col_rf2:
                st.markdown("**Factori de risc**")
                if rf_list:
                    for elem_code, nature, nom, score in rf_list:
                        _render_element_line(elem_code, nature, nom, score)
                else:
                    st.caption("—")

            desc = _mal_desc.get(code, "")
            if desc and desc != "nan":
                st.markdown("---")
                st.markdown("**Descriere**")
                st.markdown(desc[:600] + ("..." if len(desc) > 600 else ""))

            if show_reco:
                st.markdown("---")
                st.markdown("**Recomandări**")
                prof_ss_text = ", ".join([nom for _, _, nom, _ in ss_list[:6]])
                prof_rf_text = ", ".join([nom for _, _, nom, _ in rf_list[:4]])
                reco_key = f"reco_{code}"
                if reco_key not in ss.get("reco_cache", {}):
                    if st.button(f"🤖 Generează recomandări", key=f"btn_reco_{code}"):
                        with st.spinner("Se generează..."):
                            import requests, json
                            prompt = (
                                f"Ești medic clinician. Boala: {name}.\n"
                                f"Elemente semiologice: {prof_ss_text}.\n"
                                f"Factori de risc: {prof_rf_text}.\n"
                                f"Oferă în română, concis (max 150 cuvinte):\n"
                                f"1. Investigații paraclinice recomandate\n"
                                f"2. Specialitate de trimitere\n"
                                f"3. Urgență (da/nu și motivul)\n"
                                f"4. Test de confirmare diagnostic"
                            )
                            try:
                                _api_key = "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"
                                try:
                                    resp = requests.post(
                                        "https://api.anthropic.com/v1/messages",
                                        headers={
                                            "Content-Type": "application/json",
                                            "x-api-key": _api_key,
                                            "anthropic-version": "2023-06-01",
                                        },
                                        json={
                                            "model": "claude-sonnet-4-20250514",
                                            "max_tokens": 400,
                                            "messages": [{"role": "user", "content": prompt}]
                                        },
                                        timeout=30
                                    )
                                finally:
                                    _api_key = None
                                    del _api_key
                                data = resp.json()
                                reco_text = data["content"][0]["text"] if data.get("content") else "Eroare API"
                                if "reco_cache" not in ss:
                                    ss["reco_cache"] = {}
                                ss["reco_cache"][reco_key] = reco_text
                                st.rerun()
                            except Exception as e:
                                st.error(f"Eroare: {e}")
                else:
                    st.markdown(ss["reco_cache"][reco_key])

    # ── Rezultate — două clasamente ────────────────────────────────────────────
    st.markdown(
        f"**{len(filtered)}** diagnostice după filtrare  |  "
        f"**{len(excluded)}** excluse contextual"
    )
    st.divider()

    # ── Selector k ────────────────────────────────────────────────────────────
    k = st.slider("Top k diagnostice afișate", min_value=1, max_value=20, value=5, step=1)

    col_norf, col_rf = st.columns(2)

    # ── Clasament semiologic ───────────────────────────────────────────────────
    with col_norf:
        st.markdown("#### 🩺 Ranking semiologic")
        st.caption("CR NOSO pur — fără ajustări contextuale")
        for i, dis in enumerate(ranking_orig[:k]):
            cr_orig = dis.get("cr", 0)
            name    = dis.get("name_display", "")
            fill    = "█" * int(cr_orig * 20) + "░" * (20 - int(cr_orig * 20))
            excl    = ""  # Ranking semiologic brut — fara marcaje de excludere
            st.markdown(f"**#{i+1}** {name}{excl}  \n`CR = {cr_orig:.3f}` [{fill}]")

    # ── Clasament contextual ───────────────────────────────────────────────────
    with col_rf:
        st.markdown("#### 🔬 Ranking contextual")
        st.caption("CR ajustat: RF + Sex + Vârstă")
        for i, dis in enumerate(filtered[:k]):
            cr_orig = dis.get("cr", 0)
            cr_adj  = dis.get("cr_adjusted", cr_orig)
            name    = dis.get("name_display", "")
            fill    = "█" * int(cr_adj * 20) + "░" * (20 - int(cr_adj * 20))
            rf_lbl  = dis.get("rf_label", "")
            delta   = cr_adj - cr_orig
            arrow   = f" ↑ +{delta:.3f}" if delta > 0.001 else (f" ↓ {delta:.3f}" if delta < -0.001 else "")
            rf_str  = f"  `{rf_lbl}`" if rf_lbl else ""
            st.markdown(f"**#{i+1}** {name}  \n`CR = {cr_adj:.3f}`{arrow}{rf_str} [{fill}]")

    st.divider()

    # ── Carduri detaliate — primele 3 contextual ───────────────────────────────
    st.markdown("### 📊 Detalii diagnostice principale")
    for i, dis in enumerate(filtered[:3]):
        cr_orig = dis.get("cr", 0)
        cr_adj  = dis.get("cr_adjusted", cr_orig)
        rf_lbl  = dis.get("rf_label", "")
        delta   = cr_adj - cr_orig
        arrow   = f" ↑ +{delta:.3f}" if delta > 0.001 else (f" ↓ {delta:.3f}" if delta < -0.001 else "")
        rf_str  = f"  `{rf_lbl}`" if rf_lbl else ""
        _render_disease_card(i, dis, cr_adj, arrow, rf_str, show_reco=True)

    if excluded:
        with st.expander(f"Excluse contextual — {len(excluded)}"):
            for dis in excluded:
                st.markdown(
                    f"~~{dis.get('name_display','')}~~  "
                    f"CR={dis.get('cr',0):.3f}  "
                    f"— *{dis.get('excluded_reason','')}*"
                )


def _get_name(dis: dict, code: int, root: str) -> str:
    for key in ("name_en","name_ro","name","nom","NomMaladie"):
        val = dis.get(key,"")
        if val and str(val).strip():
            return str(val).strip()
    return get_disease_name(code, root)