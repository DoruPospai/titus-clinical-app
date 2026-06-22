from pathlib import Path
import pandas as pd
import streamlit as st

from .editor import (
    append_editor_rows,
    editor_df_to_patient_map,
    get_editor_df,
    parse_code_block,
    set_editor_from_rows,
)
from .search import extract_candidates_from_text
from .ui_common import kpi_card, note, panel_header
from .utils import months_between
from .audio_tools import try_transcribe_audio
from .ui_filters import get_filtered_catalog

def render_keyword_mode(*, catalog_df, default_weight: int, key_prefix: str, source_label: str):
    note(
        "Enter a keyword from the element name, synonyms or descriptions. "
        "Validate the keyword first, then choose one matching element from the dropdown list."
    )

    keyword = st.text_input(
        "Keyword",
        value="",
        placeholder="Type a keyword, then validate the search",
        key=f"{key_prefix}_keyword",
    )
    top_k = st.slider("Maximum matches", min_value=5, max_value=50, value=15, step=1, key=f"{key_prefix}_max_matches")
    min_score = st.slider("Minimum match score", min_value=0.5, max_value=6.0, value=2.0, step=0.5, key=f"{key_prefix}_min_score")
    weight = st.selectbox("Weight", [50, 100, 150], index=[50, 100, 150].index(default_weight), key=f"{key_prefix}_weight")

    if st.button("Validate keyword", key=f"{key_prefix}_validate"):
        if not keyword.strip():
            st.warning("Please enter a keyword first.")
        else:
            st.session_state[f"{key_prefix}_results_df"] = extract_candidates_from_text(
                user_text=keyword,
                catalog_df=catalog_df,
                top_k=top_k,
                min_score=min_score,
            )

    results_df = st.session_state.get(f"{key_prefix}_results_df", pd.DataFrame())
    if isinstance(results_df, pd.DataFrame) and not results_df.empty:
        lookup = results_df.set_index("Key").to_dict("index")
        selected_key = st.selectbox(
            "Matching elements",
            options=results_df["Key"].tolist(),
            format_func=lambda k: f"{lookup[k]['DisplayName']}  |  {lookup[k]['CategoryLabel']}  |  {k}  |  score={lookup[k]['MatchScore']}",
            key=f"{key_prefix}_selected_key",
        )

        info = lookup[selected_key]
        note(
            f"<b>Selected element</b><br>"
            f"Name: <b>{info['DisplayName']}</b><br>"
            f"Category: <b>{info['CategoryLabel']}</b><br>"
            f"Key: <b>{selected_key}</b><br>"
            f"Match score: <b>{info['MatchScore']}</b>"
        )

        c1, c2 = st.columns(2)
        rows = [{
            "Key": selected_key,
            "Nature": selected_key.split(":")[0],
            "Code": int(selected_key.split(":")[1]),
            "Label": "",
            "Weight": int(weight),
            "Source": source_label,
        }]

        with c1:
            if st.button("Add selected element", key=f"{key_prefix}_add", use_container_width=True):
                append_editor_rows(rows, catalog_df)
                st.success("Element added to the editor.")
        with c2:
            if st.button("Replace editor with selected element", key=f"{key_prefix}_replace", use_container_width=True):
                set_editor_from_rows(rows, catalog_df)
                st.success("Editor replaced with the selected element.")
    else:
        st.markdown('<div class="dor-mini-muted">No validated result yet.</div>', unsafe_allow_html=True)

def render_category_mode(*, catalog_df, default_weight: int, key_prefix: str, source_label: str):
    note("Select a category first. The matching elements then appear in a spacious multi-selection list.")
    categories = sorted([x for x in catalog_df["CategoryLabel"].dropna().astype(str).unique().tolist() if x.strip()])
    if not categories:
        st.info("No category information is available for this catalog.")
        return

    cat = st.selectbox("Category", categories, key=f"{key_prefix}_category")
    candidates = catalog_df[catalog_df["CategoryLabel"] == cat].sort_values(["DisplayName", "Code"]).copy()
    lookup = candidates.set_index("Key").to_dict("index")
    selected_keys = st.multiselect(
        "Elements in category",
        options=candidates["Key"].tolist(),
        format_func=lambda k: f"{lookup[k]['DisplayName']}  [{k}]",
        key=f"{key_prefix}_category_multiselect",
    )
    weight = st.selectbox("Weight", [50, 100, 150], index=[50, 100, 150].index(default_weight), key=f"{key_prefix}_category_weight")

    if st.button("Append selected category elements", key=f"{key_prefix}_category_append", use_container_width=True):
        rows = []
        for key in selected_keys:
            nature, code = key.split(":")
            rows.append(
                {
                    "Key": key,
                    "Nature": nature,
                    "Code": int(code),
                    "Label": "",
                    "Weight": int(weight),
                    "Source": source_label,
                }
            )
        append_editor_rows(rows, catalog_df)
        st.success(f"Appended {len(rows)} element(s).")

def render_code_mode(*, nature: str, catalog_df, default_value: str, default_weight: int, key_prefix: str):
    note("Use this mode when the codes are already known. You can enter code-only or code=weight pairs.")
    raw_codes = st.text_area(
        "Codes",
        value=default_value,
        height=160,
        key=f"{key_prefix}_codes_area",
        help="Examples: 109=150,13=150 or 109:150;13:150 or 109,13",
    )
    weight = st.selectbox("Default weight for code-only entries", [50, 100, 150], index=[50, 100, 150].index(default_weight), key=f"{key_prefix}_codes_weight")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Replace editor with coded elements", key=f"{key_prefix}_codes_replace", use_container_width=True):
            rows = parse_code_block(raw_codes, nature, default_weight=int(weight))
            set_editor_from_rows(rows, catalog_df)
            st.success(f"Loaded {len(rows)} coded element(s).")
    with c2:
        if st.button("Append coded elements", key=f"{key_prefix}_codes_append", use_container_width=True):
            rows = parse_code_block(raw_codes, nature, default_weight=int(weight))
            append_editor_rows(rows, catalog_df)
            st.success(f"Appended {len(rows)} coded element(s).")

def render_description_mode(*, catalog_df, default_weight: int, key_prefix: str, source_label: str, default_text: str):
    note("Paste a longer clinical description. The application searches the names, synonyms and descriptive fields to propose matching elements.")
    free_text = st.text_area(
        "Description",
        value=default_text,
        height=200,
        key=f"{key_prefix}_description_text",
    )
    top_k = st.slider("Maximum extracted candidates", min_value=5, max_value=50, value=20, step=1, key=f"{key_prefix}_description_topk")
    min_score = st.slider("Minimum extraction score", min_value=0.5, max_value=6.0, value=2.0, step=0.5, key=f"{key_prefix}_description_score")
    weight = st.selectbox("Weight", [50, 100, 150], index=[50, 100, 150].index(default_weight), key=f"{key_prefix}_description_weight")

    if st.button("Extract candidates from description", key=f"{key_prefix}_description_extract", use_container_width=True):
        st.session_state[f"{key_prefix}_description_df"] = extract_candidates_from_text(
            user_text=free_text,
            catalog_df=catalog_df,
            top_k=top_k,
            min_score=min_score,
        )

    res = st.session_state.get(f"{key_prefix}_description_df", pd.DataFrame())
    if isinstance(res, pd.DataFrame) and not res.empty:
        lookup = res.set_index("Key").to_dict("index")
        selected_keys = st.multiselect(
            "Choose extracted candidates",
            options=res["Key"].tolist(),
            format_func=lambda k: f"{lookup[k]['DisplayName']}  |  {lookup[k]['CategoryLabel']}  |  score={lookup[k]['MatchScore']}",
            default=res["Key"].tolist()[: min(8, len(res))],
            key=f"{key_prefix}_description_multiselect",
        )
        st.dataframe(res, use_container_width=True, hide_index=True)
        if st.button("Append selected description candidates", key=f"{key_prefix}_description_append", use_container_width=True):
            rows = []
            for key in selected_keys:
                nature, code = key.split(":")
                rows.append(
                    {
                        "Key": key,
                        "Nature": nature,
                        "Code": int(code),
                        "Label": "",
                        "Weight": int(weight),
                        "Source": source_label,
                    }
                )
            append_editor_rows(rows, catalog_df)
            st.success(f"Appended {len(rows)} description-derived element(s).")

def render_free_expression_mode(*, catalog_df, default_weight: int,
                                 key_prefix: str, source_label: str, nature: str):
    from .NOSO_free_expr import render_free_expression
    render_free_expression(
        key_prefix=key_prefix,
        nature=nature,
        default_weight=default_weight,
        source_label=source_label,
        catalog_df=catalog_df,
    )



def render_voice_mode(*, catalog_df, default_weight: int, key_prefix: str, source_label: str, openai_api_key: str):
    note("Record an oral description. The app transcribes it first, then searches the catalog and lets you decide what enters the editor.")
    audio_file = st.audio_input("Record clinical description", key=f"{key_prefix}_audio")
    top_k = st.slider("Maximum voice candidates", min_value=5, max_value=50, value=15, step=1, key=f"{key_prefix}_voice_topk")
    min_score = st.slider("Minimum voice extraction score", min_value=0.5, max_value=6.0, value=2.0, step=0.5, key=f"{key_prefix}_voice_score")
    weight = st.selectbox("Weight", [50, 100, 150], index=[50, 100, 150].index(default_weight), key=f"{key_prefix}_voice_weight")

    if st.button("Transcribe and extract", key=f"{key_prefix}_voice_extract", use_container_width=True):
        if audio_file is None:
            st.warning("Please record audio first.")
        else:
            try:
                transcript = try_transcribe_audio(audio_file.getvalue(), openai_api_key)
                st.session_state[f"{key_prefix}_voice_transcript"] = transcript
                st.session_state[f"{key_prefix}_voice_df"] = extract_candidates_from_text(
                    user_text=transcript,
                    catalog_df=catalog_df,
                    top_k=top_k,
                    min_score=min_score,
                )
            except Exception as e:
                st.error(f"Voice transcription/extraction failed: {e}")

    transcript = st.session_state.get(f"{key_prefix}_voice_transcript", "")
    if transcript:
        st.text_area("Transcript", value=transcript, height=150, key=f"{key_prefix}_voice_transcript_box")

    res = st.session_state.get(f"{key_prefix}_voice_df", pd.DataFrame())
    if isinstance(res, pd.DataFrame) and not res.empty:
        lookup = res.set_index("Key").to_dict("index")
        selected_keys = st.multiselect(
            "Choose voice-derived candidates",
            options=res["Key"].tolist(),
            format_func=lambda k: f"{lookup[k]['DisplayName']}  |  {lookup[k]['CategoryLabel']}  |  score={lookup[k]['MatchScore']}",
            default=res["Key"].tolist()[: min(8, len(res))],
            key=f"{key_prefix}_voice_multiselect",
        )
        st.dataframe(res, use_container_width=True, hide_index=True)
        if st.button("Append selected voice-derived elements", key=f"{key_prefix}_voice_append", use_container_width=True):
            rows = []
            for key in selected_keys:
                nature, code = key.split(":")
                rows.append(
                    {
                        "Key": key,
                        "Nature": nature,
                        "Code": int(code),
                        "Label": "",
                        "Weight": int(weight),
                        "Source": source_label,
                    }
                )
            append_editor_rows(rows, catalog_df)
            st.success(f"Appended {len(rows)} voice-derived element(s).")

def render_intake_page(*, title: str, subtitle: str, nature: str, catalog_df, default_code_value: str, default_description_text: str, default_weight: int, key_prefix: str, openai_api_key: str):
    panel_header(title, subtitle)
    mode_tabs = st.tabs(
        [
            "Search by keyword",
            "Select by category",
            "Select by code",
            "Expresie liberă",
            "Voice description",
        ]
    )

    with mode_tabs[0]:
        render_keyword_mode(catalog_df=catalog_df, default_weight=default_weight, key_prefix=f"{key_prefix}_kw", source_label=f"{key_prefix}_keyword")
    with mode_tabs[1]:
        render_category_mode(catalog_df=catalog_df, default_weight=default_weight, key_prefix=f"{key_prefix}_cat", source_label=f"{key_prefix}_category")
    with mode_tabs[2]:
        render_code_mode(nature=nature, catalog_df=catalog_df, default_value=default_code_value, default_weight=default_weight, key_prefix=f"{key_prefix}_code")
    with mode_tabs[3]:
        # ── Lazy load: NlpRO.py reimportă SemanticMatcher la prima execuție
        # (cost unic ~15-20s per sesiune server). Se execută doar după click
        # explicit, nu la randarea tab-ului.
        _flag_key = f"{key_prefix}_free_loaded"
        if not st.session_state.get(_flag_key, False):
            st.info("Acest mod inițializează lexiconul NlpRO și poate dura câteva secunde la prima utilizare.")
            if st.button("▶️ Încarcă Expresie liberă", key=f"{key_prefix}_free_load_btn"):
                st.session_state[_flag_key] = True
                st.rerun()
        else:
            render_free_expression_mode(catalog_df=catalog_df, default_weight=default_weight, key_prefix=f"{key_prefix}_free", source_label=f"{key_prefix}_free_expr", nature=nature)
    with mode_tabs[4]:
        render_voice_mode(catalog_df=catalog_df, default_weight=default_weight, key_prefix=f"{key_prefix}_voice", source_label=f"{key_prefix}_voice", openai_api_key=openai_api_key)

def page_input(name_catalog, sympt_catalog, signe_catalog, riskf_catalog, openai_api_key: str):
    panel_header(
        "Input workspace",
        "Each intake mode has its own full-width display area. Build the patient step by step, then validate everything in the final editor."
    )

    if not st.session_state.get("profile_validated", False):
        # ── Profil nevalidat: doar tab-ul Profil Pacient ───────────────────
        tabs = st.tabs(["👤 Profil Pacient"])
    else:
        # ── Profil validat: toate tab-urile ───────────────────────────────
        tabs = st.tabs(["👤 Profil Pacient", "Simptome", "Semne clinice",
                        "Factori de risc", "Anamneze", "Review & Finalize"])

    with tabs[0]:
        pp = st.session_state["patient_profile"]
        note("Date of birth is the primary input. Age in months is calculated automatically.")
        st.write("patient profile")
        c1, c2, c3 = st.columns(3)
        with c1:
            user_id = st.number_input("User ID", min_value=1, value=int(pp.get("user_id", 1)))
        
            # Normalizare dob din session_state: poate fi string, date, sau None
            dob_raw = pp.get("dob")
            if isinstance(dob_raw, str):
                try:
                    dob_raw = pd.Timestamp(dob_raw).date()
                except Exception:
                    dob_raw = None

            dob = st.date_input(
                "Date of birth",
                value=dob_raw,
                min_value=pd.Timestamp("1900-01-01").date(),
                max_value=pd.Timestamp.today().date(),
            )

            if dob is not None:
                age_m = months_between(dob, pd.Timestamp.today().date())
                st.text_input("Age (months)", value=str(int(age_m)), disabled=True)
                # Warning dacă dob s-a schimbat față de profilul salvat
                saved_age = pp.get("age_in_months", 0)
                if int(age_m) != int(saved_age):
                    st.warning(
                        f"⚠️ Vârsta s-a schimbat ({int(age_m)} luni). "
                        "Apasă **Apply profile changes** pentru a salva."
                    )
            else:
                age_m = 0
                st.text_input(
                    "Age (months)", value="—", disabled=True,
                    help="Introduceți data de naștere pentru calcul automat.",
                )

        with c2:
            gender = st.selectbox("Sex", ["Female", "Male"], index=0 if pp.get("gender", "Female") == "Female" else 1)
            living_options = ["America North", "America South", "Europe North", "Europe South", "Asia North", "Asia South", "Australia", "Africa North", "Africa South", "Africa Central", "Africa West"]
            living_in = st.selectbox("Living in", living_options, index=living_options.index(pp.get("living_in")) if pp.get("living_in") in living_options else 0)

        with c3:
            ethn_options = ["Caucasian", "Black", "White", "Asian", "Hispanic"]
            ethnics = st.selectbox("Ethnics", ethn_options, index=ethn_options.index(pp.get("ethnics")) if pp.get("ethnics") in ethn_options else 0)

            if gender == "Female":
                pregnancy = st.selectbox("Pregnancy", ["No", "Yes", "Don't know"], index={"No": 0, "Yes": 1, "Don't know": 2}.get(pp.get("pregnancy", "No"), 0))
                weeks = None
                if pregnancy == "Yes":
                    weeks = st.number_input("Pregnancy weeks", min_value=0, max_value=44, value=int(pp.get("weeks_pregnant") or 20), step=1)
            else:
                pregnancy = "No"
                weeks = None

        # ── Condiții speciale ─────────────────────────────────────────────────
        st.markdown("**Condiții speciale**")
        special_options = [
            "Altitudine înaltă",
            "Călătorie recentă în zonă endemică / tropicală",
            "Zonă epidemie activă",
            "Pacient imunodeprimat",
            "Mediu confinat (închisoare, cămin, spital)",
        ]
        special_conds = st.multiselect(
            "Selectați condițiile aplicabile",
            special_options,
            default=pp.get("special_conditions", []),
            label_visibility="collapsed",
        )

        if st.button("Apply profile changes", type="primary"):
            profile_data = {
                "user_id": int(user_id),
                "dob": dob,
                "gender": gender,
                "living_in": living_in,
                "ethnics": ethnics,
                "pregnancy": pregnancy,
                "weeks_pregnant": int(weeks) if weeks is not None and pregnancy == "Yes" else None,
                "age_in_months": int(age_m),
                "special_conditions": special_conds,
            }
            st.session_state["patient_profile"] = profile_data
            st.session_state["ctx_profile_loaded"] = False  # forteaza re-import in Strat Contextual
    
            # ── Legea 1: genereaza sumar fișa pacient ──────────────────────
            preg_str = ""
            if gender == "Female" and pregnancy == "Yes":
                preg_str = f" · Însărcinată {int(weeks) if weeks else 0} săptămâni"
            elif gender == "Female" and pregnancy == "No":
                preg_str = " · Neînsărcinată"
            st.write("ok2")
            st.session_state["profile_summary"] = (
                f"👤 **Pacient #{int(user_id)}** · "
                f"{'♀ Feminin' if gender == 'Female' else '♂ Masculin'} · "
                f"{int(age_m)} luni ({int(age_m)//12} ani) · "
                f"Născut: {dob} · "
                f"{living_in} · {ethnics}"
                f"{preg_str}"
            )
            st.session_state["profile_validated"] = True
            # ───────────────────────────────────────────────────────────────
            st.success("Patient profile updated.")
            st.rerun()
        
    if st.session_state.get("profile_validated", False):

        with tabs[1]:
            _profile  = st.session_state.get("patient_profile", {})
            _sympt_f  = get_filtered_catalog(sympt_catalog, "Sympt", _profile)
            render_intake_page(
                title="Symptoms intake",
                subtitle="Search, browse or dictate symptoms in a spacious workspace.",
                nature="Sympt",
                catalog_df=_sympt_f,
                default_code_value="109=150,13=150",
                default_description_text="polyuria, weight loss",
                default_weight=150,
                key_prefix="sympt",
                openai_api_key=openai_api_key,
            )

        with tabs[2]:
            _profile  = st.session_state.get("patient_profile", {})
            _signe_f  = get_filtered_catalog(signe_catalog, "Signe", _profile)
            render_intake_page(
                title="Clinical signs intake",
                subtitle="Search, browse or dictate clinical signs in a separate workspace.",
                nature="Signe",
                catalog_df=_signe_f,
                default_code_value="401=50",
                default_description_text="xanthelasma",
                default_weight=50,
                key_prefix="signe",
                openai_api_key=openai_api_key,
            )

        with tabs[3]:
            _profile  = st.session_state.get("patient_profile", {})
            _riskf_f  = get_filtered_catalog(riskf_catalog, "RiskF", _profile)
            render_intake_page(
                title="Risk Factors intake",
                subtitle="Search, browse or select risk factors relevant for the patient.",
                nature="RiskF",
                catalog_df=_riskf_f,
                default_code_value="1=150,3=150",
                default_description_text="diabetes, obesity",
                default_weight=150,
                key_prefix="riskf",
                openai_api_key=openai_api_key,
            )

        with tabs[4]:
            try:
                from .NOSO_anam_tab import render_anam_nlpro
                render_anam_nlpro(root=str(Path(__file__).resolve().parent.parent))
            except Exception as ex:
                st.error(f"Eroare modul Anamneze: {ex}")

        with tabs[5]:
            panel_header("Review & finalize patient elements", "The editor is the final control point before ranking.")

            # ── Legea 1: sumar fișa pacient ────────────────────────────────
            summary = st.session_state.get("profile_summary", "")
            if summary:
                st.info(summary)
            # ───────────────────────────────────────────────────────────────

            editor_df = get_editor_df()
            edited_df = st.data_editor(
            editor_df,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "Key": st.column_config.TextColumn("Key", disabled=True),
                "Nature": st.column_config.TextColumn("Nature", disabled=True),
                "Code": st.column_config.NumberColumn("Code", disabled=True),
                "Label": st.column_config.TextColumn("Label", disabled=True),
                "Weight": st.column_config.NumberColumn("Weight", min_value=0, max_value=400, step=10),
                "Source": st.column_config.TextColumn("Source", disabled=True),
            },
            key="workspace_editor_data_editor",
            )
            st.session_state["editor_rows"] = edited_df.to_dict(orient="records") if not edited_df.empty else []

            patient_map = editor_df_to_patient_map(pd.DataFrame(st.session_state["editor_rows"]))

            # Masa si count DOAR pentru SS (RF nu intra in formula CR)
            ss_map = {k: v for k, v in patient_map.items()
                      if k.startswith("Sympt:") or k.startswith("Signe:")}
            rf_map = {k: v for k, v in patient_map.items() if k.startswith("RiskF:")}

            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("Elemente SS", str(len(ss_map)))
            with c2:
                kpi_card("Patient mass (SS)", f"{sum(ss_map.values()):.1f}")
            with c3:
                n_sym = sum(1 for k in ss_map if k.startswith("Sympt:"))
                n_sig = sum(1 for k in ss_map if k.startswith("Signe:"))
                kpi_card("Sympt / Signe", f"{n_sym} / {n_sig}")

            if rf_map:
                st.caption(f"RF în editor (exclus din CR): {', '.join(rf_map.keys())}")

            c4, c5, c6 = st.columns(3)
            with c4:
                if st.button("🗑️ Anulare", use_container_width=True):
                    st.session_state["editor_rows"] = []
                    st.session_state["noso_elements_ready"] = []
                    st.rerun()
            with c5:
                note("Modificați ponderile direct în tabel.")
            with c6:
                if st.button("✅ Confirmă", type="primary", use_container_width=True):
                    rows = st.session_state.get("editor_rows", [])
                    ss_ready  = []  # Sympt + Signe → pentru NOSO CR
                    rf_ready  = []  # RiskF → exclusiv pentru stratul contextual
                    for r in rows:
                        try:
                            nat  = str(r.get("Nature", "Sympt"))
                            code = int(r.get("Code", 0))
                            wgt  = int(r.get("Weight", 150))
                            if not code: continue
                            if nat in ("Sympt", "Signe"):
                                ss_ready.append((code, nat, wgt))
                            elif nat == "RiskF":
                                rf_ready.append((code, nat, wgt))
                        except Exception:
                            pass
                    # noso_elements_ready = DOAR SS (nu influenteaza M cu RF)
                    st.session_state["noso_elements_ready"] = ss_ready
                    # M_P_ss = suma scoruri SS pacient — FIX pentru toate bolile candidate
                    st.session_state["M_P_ss"] = sum(w for _, _, w in ss_ready) or 750
                    # RF salvat separat pentru stratul contextual
                    st.session_state["confirmed_rf_codes"]  = [c for c, n, w in rf_ready]
                    # confirmed_rf_scores: cod → weight real din editor (necesar in NOSO_context)
                    st.session_state["confirmed_rf_scores"] = {c: w for c, n, w in rf_ready}
                    st.success(
                        f"✓ {len(ss_ready)} SS confirmate"
                        f"{'  |  ' + str(len(rf_ready)) + ' RF → Strat contextual' if rf_ready else ''}"
                    )

            note("The current ranking uses the latest latent full-catalog inference with CR filtering.")

            # ── Legea 2: Calculează ranking DIN Review & Finalize ─────────────────
            st.divider()
            st.markdown("**Lansare ranking semiologic**")
            c_rank1, c_rank2 = st.columns([3, 1])
            with c_rank1:
                st.caption("Confirmați elementele mai sus, apoi calculați rankingul.")
            with c_rank2:
                if st.button("📊 Calculează ranking", type="primary", use_container_width=True):
                    from .NOSO_loader import diagnose
                    # noso_elements_ready = DOAR Sympt+Signe (RF separat la Confirmă)
                    ss_elements = st.session_state.get("noso_elements_ready", [])
                    rf_codes    = st.session_state.get("confirmed_rf_codes", [])
                    # Auto-populare RF din editor_rows dacă nu au fost confirmate manual
                    if not rf_codes:
                        editor_rows = st.session_state.get("editor_rows", [])
                        rf_codes = [
                            int(r.get("Code", 0))
                            for r in editor_rows
                            if str(r.get("Nature", "")) == "RiskF" and r.get("Code")
                        ]
                        if rf_codes:
                            st.session_state["confirmed_rf_codes"] = rf_codes
                    if not ss_elements:
                        st.warning("Confirmați mai întâi elementele clinice (butonul ✅ Confirmă).")
                    else:
                        with st.spinner("Calcul CR..."):
                            try:
                                result = diagnose(
                                    ss_elements,
                                    top_n=20,
                                    cr_threshold=0.20,
                                    root=str(Path(__file__).resolve().parent.parent),
                                )
                                st.session_state["noso_ranking_result"]      = result
                                st.session_state["noso_ranking_for_context"] = result.get("ranking", [])
                                st.session_state["noso_ranking_params"]      = {
                                    "cr_thr": 0.20, "top_n": 20,
                                    "n_elements": len(ss_elements),
                                    "n_rf": len(rf_codes),
                                }
                                st.session_state["ranking_done"]       = True
                                st.session_state["ctx_profile_loaded"] = False
                                n_res = len(result.get("ranking", []))
                                st.success(
                                    f"✓ Ranking calculat — {n_res} diagnostice  "
                                    f"{'| ' + str(len(rf_codes)) + ' RF → Strat contextual' if rf_codes else ''}"
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Eroare: {e}")
            # ─────────────────────────────────────────────────────────────────────
