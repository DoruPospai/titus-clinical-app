"""
i18n.py — TITUS
Localizare UI în română, franceză și engleză.
Termenii medicali rămân în engleză (standard internațional).
"""
from __future__ import annotations

LANGUAGES = {"🇷🇴 Română": "ro", "🇫🇷 Français": "fr", "🇬🇧 English": "en"}

# ── Dicționar principal ───────────────────────────────────────────────────────
T: dict[str, dict[str, str]] = {

    # ── Navigare ──────────────────────────────────────────────────────────────
    "nav_batch"   : {"ro": "📊 Analiză Batch",    "fr": "📊 Analyse Batch",   "en": "📊 Batch Analysis"},
    "nav_consult" : {"ro": "🩺 Consultație",       "fr": "🩺 Consultation",    "en": "🩺 Consultation"},
    "nav_anam"    : {"ro": "🎙️ Anamneză",          "fr": "🎙️ Anamnèse",        "en": "🎙️ Anamnesis"},
    "nav_about"   : {"ro": "ℹ️ Despre",            "fr": "ℹ️ À propos",        "en": "ℹ️ About"},
    "nav_tralala" : {"ro": "🎵 Altele",            "fr": "🎵 Divers",          "en": "🎵 Miscellaneous"},

    # ── Sidebar ───────────────────────────────────────────────────────────────
    "sidebar_params"     : {"ro": "Parametri ranking",  "fr": "Paramètres ranking", "en": "Ranking parameters"},
    "sidebar_topk"       : {"ro": "Top-K rezultate",    "fr": "Top-K résultats",    "en": "Top-K results"},
    "sidebar_threshold"  : {"ro": "Prag CR",            "fr": "Seuil CR",           "en": "CR threshold"},
    "sidebar_clear_cache": {"ro": "🔄 Resetează motorul","fr": "🔄 Réinitialiser",  "en": "🔄 Clear cache"},
    "sidebar_language"   : {"ro": "Limbă",              "fr": "Langue",             "en": "Language"},

    # ── Ranking tabs ──────────────────────────────────────────────────────────
    "tab_ranking"   : {"ro": "📊 Ranking",          "fr": "📊 Classement",      "en": "📊 Ranking"},
    "tab_wr"        : {"ro": "⏳ Anticameră",        "fr": "⏳ Salle d'attente", "en": "⏳ Waiting Room"},
    "tab_explain"   : {"ro": "🔍 Explicație",        "fr": "🔍 Explication",     "en": "🔍 Explain"},
    "tab_suggest"   : {"ro": "💡 Sugestii",          "fr": "💡 Suggestions",     "en": "💡 Suggest"},
    "tab_why"       : {"ro": "⚖️ De ce?",            "fr": "⚖️ Pourquoi?",       "en": "⚖️ Why"},
    "tab_comorbid"  : {"ro": "🔗 Comorbiditate",     "fr": "🔗 Comorbidité",     "en": "🔗 Comorbid"},
    "tab_rf_impact" : {"ro": "⚡ Impact RF",          "fr": "⚡ Impact FR",        "en": "⚡ RF Impact"},
    "tab_demo"      : {"ro": "🧬 Demografic",        "fr": "🧬 Démographique",   "en": "🧬 Demographic"},
    "tab_demo_apply": {"ro": "✅ Aplică demografic", "fr": "✅ Appliquer démo",  "en": "✅ Apply demo"},
    "tab_demo_on"   : {"ro": "☑ Demografic activ",  "fr": "☑ Démo actif",       "en": "☑ Demo active"},
    "tab_export"    : {"ro": "💾 Export",             "fr": "💾 Export",          "en": "💾 Export"},

    # ── Butoane ranking ───────────────────────────────────────────────────────
    "btn_run"         : {"ro": "▶ Rulează ranking",    "fr": "▶ Lancer classement","en": "▶ Run ranking"},
    "btn_cancel_demo" : {"ro": "✕ Anulare demografic", "fr": "✕ Annuler démo",    "en": "✕ Cancel demo"},
    "btn_calc_demo"   : {"ro": "🧬 Calculează factor demografic",
                         "fr": "🧬 Calculer facteur démographique",
                         "en": "🧬 Calculate demographic factor"},
    "btn_apply_demo"  : {"ro": "✅ Aplică factor demografic",
                         "fr": "✅ Appliquer facteur démographique",
                         "en": "✅ Apply demographic factor"},
    "btn_recalc"      : {"ro": "🔄 Recalculează",      "fr": "🔄 Recalculer",     "en": "🔄 Recalculate"},
    "btn_explain"     : {"ro": "Explică",              "fr": "Expliquer",         "en": "Explain"},
    "btn_analyze"     : {"ro": "Analizează",           "fr": "Analyser",          "en": "Analyze"},
    "btn_calc_suggest": {"ro": "Calculează sugestii",  "fr": "Calculer suggestions","en": "Calculate suggestions"},
    "btn_search_combo": {"ro": "Caută comorbiditate",  "fr": "Chercher comorbidité","en": "Search comorbidity"},
    "btn_download_json": {"ro": "⬇ Descarcă JSON",    "fr": "⬇ Télécharger JSON","en": "⬇ Download JSON"},
    "btn_download_txt" : {"ro": "⬇ Descarcă TXT",     "fr": "⬇ Télécharger TXT", "en": "⬇ Download TXT"},

    # ── KPI labels ────────────────────────────────────────────────────────────
    "kpi_elements"   : {"ro": "Elemente",        "fr": "Éléments",       "en": "Elements"},
    "kpi_mass"       : {"ro": "Masă pacient",    "fr": "Masse patient",  "en": "Patient mass"},
    "kpi_threshold"  : {"ro": "Prag CR",         "fr": "Seuil CR",       "en": "CR threshold"},
    "kpi_topk"       : {"ro": "Top-K",           "fr": "Top-K",          "en": "Top-K"},
    "kpi_sex"        : {"ro": "Sex",             "fr": "Sexe",           "en": "Sex"},
    "kpi_age"        : {"ro": "Vârstă pacient",  "fr": "Âge patient",    "en": "Patient age"},
    "kpi_months"     : {"ro": "luni",            "fr": "mois",           "en": "months"},

    # ── Mesaje ranking ────────────────────────────────────────────────────────
    "msg_run_first"      : {"ro": "Apasă 'Rulează ranking' pentru a vedea rezultatele.",
                            "fr": "Cliquez sur 'Lancer classement' pour voir les résultats.",
                            "en": "Press 'Run ranking' to see results."},
    "msg_no_candidates"  : {"ro": "Niciun candidat cu CR ≥ prag.",
                            "fr": "Aucun candidat avec CR ≥ seuil.",
                            "en": "No candidates with CR ≥ threshold."},
    "msg_wr_empty"       : {"ro": "Anticameră goală.",
                            "fr": "Salle d'attente vide.",
                            "en": "Waiting Room empty."},
    "msg_rank_complete"  : {"ro": "Ranking complet.",
                            "fr": "Classement complet.",
                            "en": "Ranking complete."},
    "msg_rf_active"      : {"ro": "{n} RF activi — impactul este reflectat în tabel.",
                            "fr": "{n} FR actifs — impact reflété dans le tableau.",
                            "en": "{n} active RF — impact reflected in table."},
    "msg_demo_applied"   : {"ro": "🧬 Factor demografic aplicat — ranking ordonat după CR×AgeFactor.",
                            "fr": "🧬 Facteur démographique appliqué — classement selon CR×AgeFactor.",
                            "en": "🧬 Demographic factor applied — ranking sorted by CR×AgeFactor."},
    "msg_profile_changed": {"ro": "⚠ Profilul s-a schimbat. Rulează din nou ranking-ul.",
                            "fr": "⚠ Le profil a changé. Relancez le classement.",
                            "en": "⚠ Profile changed. Re-run ranking."},
    "msg_stale_rf"       : {"ro": "⚠ Profilul are {n} RF dar rezultatele nu reflectă impactul lor. Apasă ▶ Run ranking.",
                            "fr": "⚠ Le profil a {n} FR mais les résultats ne reflètent pas leur impact. Cliquez ▶.",
                            "en": "⚠ Profile has {n} RF but results don't reflect their impact. Press ▶ Run ranking."},

    # ── Ranking column headers ────────────────────────────────────────────────
    "col_rank"    : {"ro": "Rang",      "fr": "Rang",      "en": "Rank"},
    "col_class"   : {"ro": "Clasă",    "fr": "Classe",    "en": "Class"},
    "col_cr"      : {"ro": "CR",       "fr": "CR",        "en": "CR"},
    "col_disease" : {"ro": "Boală",    "fr": "Maladie",   "en": "Disease"},
    "col_cr_semio": {"ro": "CR semio", "fr": "CR sémio",  "en": "CR semio"},
    "col_rf_net"  : {"ro": "RF net",   "fr": "FR net",    "en": "RF net"},
    "col_type"    : {"ro": "Tip",      "fr": "Type",      "en": "Type"},

    # ── Explain tab ───────────────────────────────────────────────────────────
    "explain_title"        : {"ro": "Explicație diagnostic",
                              "fr": "Explication diagnostic",
                              "en": "Diagnostic explanation"},
    "explain_choose"       : {"ro": "Alege diagnosticul",
                              "fr": "Choisir le diagnostic",
                              "en": "Choose diagnostic"},
    "explain_confirmed"    : {"ro": "Simptome cardinale confirmate",
                              "fr": "Symptômes cardinaux confirmés",
                              "en": "Confirmed cardinal symptoms"},
    "explain_secondary"    : {"ro": "Simptome secundare confirmate",
                              "fr": "Symptômes secondaires confirmés",
                              "en": "Confirmed secondary symptoms"},
    "explain_absent"       : {"ro": "Simptome ale bolii neconfirmate încă",
                              "fr": "Symptômes de la maladie non encore confirmés",
                              "en": "Unconfirmed disease symptoms"},
    "explain_penalized"    : {"ro": "Simptome ale pacientului absente din boală — penalizate",
                              "fr": "Symptômes du patient absents de la maladie — pénalisés",
                              "en": "Patient symptoms absent from disease — penalized"},
    "explain_no_penalty"   : {"ro": "Nicio penalizare — toate simptomele pacientului sunt compatibile.",
                              "fr": "Aucune pénalité — tous les symptômes du patient sont compatibles.",
                              "en": "No penalty — all patient symptoms are compatible."},
    "explain_strengthen"   : {"ro": "Prezența lor ar întări diagnosticul:",
                              "fr": "Leur présence renforcerait le diagnostic:",
                              "en": "Their presence would strengthen the diagnosis:"},

    # ── Consultație ───────────────────────────────────────────────────────────
    "cons_title"     : {"ro": "Consultație TITUS",
                        "fr": "Consultation TITUS",
                        "en": "TITUS Consultation"},
    "cons_subtitle"  : {"ro": "Motorul ghidează. Medicul confirmă. Diagnosticul evoluează pas cu pas.",
                        "fr": "Le moteur guide. Le médecin confirme. Le diagnostic évolue pas à pas.",
                        "en": "Engine guides. Doctor confirms. Diagnosis evolves step by step."},
    "cons_new"       : {"ro": "🔄 Consultație nouă", "fr": "🔄 Nouvelle consultation", "en": "🔄 New consultation"},
    "cons_age"       : {"ro": "Câți ani are pacientul?", "fr": "Quel âge a le patient?", "en": "How old is the patient?"},
    "cons_sex"       : {"ro": "Bărbat sau femeie?",    "fr": "Homme ou femme?",          "en": "Male or female?"},
    "cons_male"      : {"ro": "Masculin",              "fr": "Masculin",                 "en": "Male"},
    "cons_female"    : {"ro": "Feminin",               "fr": "Féminin",                  "en": "Female"},
    "cons_pregnant"  : {"ro": "Pacienta este însărcinată?",
                        "fr": "La patiente est-elle enceinte?",
                        "en": "Is the patient pregnant?"},
    "cons_yes"       : {"ro": "Da",  "fr": "Oui", "en": "Yes"},
    "cons_no"        : {"ro": "Nu",  "fr": "Non", "en": "No"},
    "cons_weeks"     : {"ro": "Săptămâni de sarcină:",
                        "fr": "Semaines de grossesse:",
                        "en": "Weeks of pregnancy:"},
    "cons_start"     : {"ro": "▶ Începe consultația",
                        "fr": "▶ Commencer la consultation",
                        "en": "▶ Start consultation"},
    "cons_skip_scr"  : {"ro": "→ Treci la examinare clinică",
                        "fr": "→ Passer à l'examen clinique",
                        "en": "→ Skip to clinical examination"},
    "cons_to_result" : {"ro": "📊 Vezi diagnosticul",
                        "fr": "📊 Voir le diagnostic",
                        "en": "📊 See diagnosis"},
    "cons_to_rf"     : {"ro": "⚠️ Adaugă factori de risc",
                        "fr": "⚠️ Ajouter facteurs de risque",
                        "en": "⚠️ Add risk factors"},
    "cons_back"      : {"ro": "← Continuă consultația",
                        "fr": "← Continuer la consultation",
                        "en": "← Continue consultation"},
    "btn_da"         : {"ro": "✓  Da",       "fr": "✓  Oui",    "en": "✓  Yes"},
    "btn_nu"         : {"ro": "✗  Nu",       "fr": "✗  Non",    "en": "✗  No"},
    "btn_ns"         : {"ro": "?  Nu știu",  "fr": "?  NSP",    "en": "?  Don't know"},
    "cons_screening_title": {"ro": "🤒 Simptome principale",
                             "fr": "🤒 Symptômes principaux",
                             "en": "🤒 Main symptoms"},
    "cons_q_progress"     : {"ro": "Întrebarea {i} din {n}",
                             "fr": "Question {i} sur {n}",
                             "en": "Question {i} of {n}"},
    "cons_ranking_now"    : {"ro": "📊 Ranking curent",
                             "fr": "📊 Classement actuel",
                             "en": "📊 Current ranking"},
    "cons_targeted_title" : {"ro": "🔬 Examinare clinică țintită",
                             "fr": "🔬 Examen clinique ciblé",
                             "en": "🔬 Targeted clinical examination"},
    "cons_probable"       : {"ro": "Diagnostice probabile până acum:",
                             "fr": "Diagnostics probables jusqu'ici:",
                             "en": "Probable diagnoses so far:"},
    "cons_rf_title"       : {"ro": "### ⚠️ Factori de risc cunoscuți",
                             "fr": "### ⚠️ Facteurs de risque connus",
                             "en": "### ⚠️ Known risk factors"},
    "cons_rf_hint"        : {"ro": "Boli cronice, obiceiuri, antecedente familiale.",
                             "fr": "Maladies chroniques, habitudes, antécédents familiaux.",
                             "en": "Chronic diseases, habits, family history."},
    "cons_rf_search"      : {"ro": "De exemplu: diabet, fumat, obezitate...",
                             "fr": "Par exemple: diabète, tabac, obésité...",
                             "en": "For example: diabetes, smoking, obesity..."},
    "cons_result_title"   : {"ro": "## 📊 Diagnostic final",
                             "fr": "## 📊 Diagnostic final",
                             "en": "## 📊 Final diagnosis"},
    "cons_main_diag"      : {"ro": "### Diagnostice principale",
                             "fr": "### Diagnostics principaux",
                             "en": "### Main diagnoses"},
    "cons_no_diag"        : {"ro": "Niciun diagnostic cu scor suficient. Adaugă mai multe date.",
                             "fr": "Aucun diagnostic avec score suffisant. Ajoutez plus de données.",
                             "en": "No diagnosis with sufficient score. Add more data."},
    "cons_wr_rf"          : {"ro": "### ⏳ Posibil — lipsesc factori de risc",
                             "fr": "### ⏳ Possible — facteurs de risque manquants",
                             "en": "### ⏳ Possible — missing risk factors"},
    "cons_journal_title"  : {"ro": "### 📋 Evoluție consultație",
                             "fr": "### 📋 Évolution de la consultation",
                             "en": "### 📋 Consultation evolution"},
    "cons_confirmed_label": {"ro": "Confirmate",  "fr": "Confirmés",  "en": "Confirmed"},
    "cons_denied_label"   : {"ro": "Negate",      "fr": "Niés",       "en": "Denied"},
    "cons_diag_label"     : {"ro": "Diagnostice", "fr": "Diagnostics","en": "Diagnoses"},
    "cons_patient_label"  : {"ro": "Pacient",     "fr": "Patient",    "en": "Patient"},
    "cons_pregnant_short" : {"ro": ", gravidă",   "fr": ", enceinte", "en": ", pregnant"},
    "cons_journal_pas"    : {"ro": "Pas",         "fr": "Étape",      "en": "Step"},
    "cons_journal_elem"   : {"ro": "Elem.",        "fr": "Élém.",      "en": "Elem."},

    # ── Screening questions template ──────────────────────────────────────────
    "q_sympt_template" : {"ro": "Prezintă {name}?",
                          "fr": "Présente-t-il {name}?",
                          "en": "Does the patient have {name}?"},
    "q_signe_template" : {"ro": "La examinare: {name}?",
                          "fr": "À l'examen: {name}?",
                          "en": "On examination: {name}?"},

    # ── Waiting Room ──────────────────────────────────────────────────────────
    "wr_semio_title" : {"ro": "Anticameră semiologică",
                        "fr": "Salle d'attente sémiologique",
                        "en": "Semiologic Waiting Room"},
    "wr_rf_title"    : {"ro": "Anticameră RF",
                        "fr": "Salle d'attente FR",
                        "en": "RF Waiting Room"},
    "wr_rf_note"     : {"ro": "Boli cu CR semiologic ≥ prag dar care nu conțin toți RF pacientului.",
                        "fr": "Maladies avec CR sémiologique ≥ seuil mais sans tous les FR du patient.",
                        "en": "Diseases with semiologic CR ≥ threshold but missing patient RF."},
    "wr_rf_absent"   : {"ro": "RF absenti",  "fr": "FR absents",  "en": "Missing RF"},

    # ── Input tabs ────────────────────────────────────────────────────────────
    "input_tab_profile" : {"ro": "Profil Pacient",    "fr": "Profil Patient",    "en": "Patient Profile"},
    "input_tab_sympt"   : {"ro": "Simptome",          "fr": "Symptômes",         "en": "Symptoms"},
    "input_tab_signe"   : {"ro": "Semne clinice",     "fr": "Signes cliniques",  "en": "Clinical Signs"},
    "input_tab_riskf"   : {"ro": "Factori de risc",  "fr": "Facteurs de risque","en": "Risk Factors"},
    "input_tab_review"  : {"ro": "Revizuire & Finalizare",
                           "fr": "Révision & Finalisation",
                           "en": "Review & Finalize"},
}


def t(key: str, lang: str = "ro", **kwargs) -> str:
    """Returnează traducerea pentru cheia dată în limba specificată."""
    entry = T.get(key, {})
    text  = entry.get(lang, entry.get("en", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def get_lang() -> str:
    """Returnează codul limbii selectate din session state."""
    import streamlit as st
    return st.session_state.get("lang", "ro")


def lang_selector() -> str:
    """Afișează selectorul de limbă în sidebar și returnează codul limbii."""
    import streamlit as st
    lang_label = st.sidebar.selectbox(
        "🌐 " + t("sidebar_language", "ro"),
        list(LANGUAGES.keys()),
        index=0,
        key="lang_selector"
    )
    lang = LANGUAGES[lang_label]
    st.session_state["lang"] = lang
    return lang


# ── Traducere nume boli ───────────────────────────────────────────────────────
import json as _json2, os as _os2

_TRANS_CACHE = None

def _get_trans():
    global _TRANS_CACHE
    if _TRANS_CACHE is None:
        path = _os2.path.join(_os2.path.dirname(__file__), 'translations.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _TRANS_CACHE = _json2.load(f)
        except Exception:
            _TRANS_CACHE = {}
    return _TRANS_CACHE

def disease_name(code: int, lang: str = "ro") -> str:
    """Returnează numele bolii în limba selectată."""
    T2 = _get_trans()
    v  = T2.get("disease", {}).get(str(code), {})
    return v.get(lang) or v.get("ro") or v.get("en", str(code))

def disease_display(code: int, name_en: str, lang: str = "ro") -> str:
    """
    Afișează: Nume_tradus (Nume_EN) sau Nume_EN dacă traducerea e identică.
    """
    T2    = _get_trans()
    v     = T2.get("disease", {}).get(str(code), {})
    trans = v.get(lang) or v.get("ro") or name_en
    if trans.lower().strip() == name_en.lower().strip():
        return name_en
    return f"{trans} ({name_en})"

def term_display(code: int, nature: str, lang: str = "ro") -> str:
    """Returnează denumirea unui simptom/semn/RF în limba selectată."""
    T2  = _get_trans()
    key = {"Sympt":"sympt","Signe":"signe","RiskF":"riskf"}.get(nature, "sympt")
    v   = T2.get(key, {}).get(str(code), {})
    return v.get(lang) or v.get("ro") or v.get("en", f"{nature}:{code}")
