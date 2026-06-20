import os
import streamlit as st
from pathlib import Path

from .config import (
    DEFAULT_ROOT, DEFAULT_TABEL2, DEFAULT_MALADIES,
    DEFAULT_SYMPTOMES, DEFAULT_SIGNE,
    DEFAULT_RISKF, DEFAULT_CATRISKF,
    DEFAULT_CATSYMPT, DEFAULT_CATSIGNE,
    DEFAULT_W_MATRIX, DEFAULT_RARITATE,
    DEFAULT_OUTPUT_DIR, DEFAULT_CR_THRESHOLD, DEFAULT_TOP_K,
)
from .ui_common import hero, inject_css
from .state import init_state
from .pages_input import page_input
from .NOSO_ranking import render_ranking
from .NOSO_interview import render_interview
from .NOSO_context import render_context
from .NOSO_review import init_review_state


def render_sidebar():
    with st.sidebar:
        st.markdown("## ⚙️ TITUS")
        st.divider()

        menu_items = ["📋 Introducere date"]
        if st.session_state.get("ranking_done", False):
            menu_items += ["📊 Ranking semiologic", "🔬 Strat contextual", "🎤 Interviu"]
        menu_items.append("📖 Despre")

        menu = st.radio(
            "Navigatie",
            menu_items,
            label_visibility="collapsed",
            key="main_menu",
        )

        st.divider()
        st.markdown("**Parametri NOSO**")
        cr_threshold = st.number_input(
            "Prag CR", min_value=0.05, max_value=0.99,
            value=float(DEFAULT_CR_THRESHOLD), step=0.05,
            key="sidebar_cr",
        )
        top_k = st.number_input(
            "Top N boli", min_value=5, max_value=50,
            value=int(DEFAULT_TOP_K), step=5,
            key="sidebar_topk",
        )
        st.divider()
        api_key = st.text_input(
            "Cheie API Claude",
            value="", type="password",
            key="sidebar_api_key",
        )
        st.divider()
        st.markdown("**NlpRO**")
        nlpro_script = st.text_input(
            "NlpRO script",
            value=str(DEFAULT_ROOT / "NlpRO.py"),
            key="sidebar_nlpro_script",
            help="Calea spre scriptul NlpRO (orice versiune)",
        )

        st.divider()
        if st.button("🔄 Reset complet", use_container_width=True):
            for k in list(st.session_state.keys()):
                if any(k.startswith(p) for p in
                       ("noso_", "anam_", "iv_", "nlpro_", "workspace_")):
                    del st.session_state[k]

            # Reset explicit pentru pipeline-ul semantic/narrative.
            for k in ("_sem_matcher", "_engine_initialized"):
                if k in st.session_state:
                    del st.session_state[k]

            st.cache_resource.clear()
            st.rerun()

    return menu, float(cr_threshold), int(top_k), api_key


@st.cache_resource(show_spinner="Inițializare motor semantic...")
def _load_semantic_pipeline(workbook_path_str: str):
    """
    Încarcă Lexiconul + SemanticMatcher o singură dată per sesiune server.
    @st.cache_resource — supraviețuiește rerun-urilor și reconectărilor browserului.
    Invalidat explicit doar prin st.cache_resource.clear() (butonul Reset).
    """
    import pandas as pd
    from .semantic_layer import SemanticMatcher
    from .narrative_engine import init_engine

    workbook_path = Path(workbook_path_str)
    lexicon_df    = pd.read_excel(str(workbook_path), sheet_name="Lexicon")
    matcher       = SemanticMatcher(workbook_path, lexicon_df)
    init_engine(lexicon_df=lexicon_df, semantic_matcher=matcher)
    return matcher


def _init_semantic_pipeline_once() -> None:
    """
    Injectează matcher-ul din cache_resource în session_state.
    Guard pe session_state: evită reinjectarea la fiecare rerun al aceluiași user.
    """
    if st.session_state.get("_engine_initialized", False):
        return

    workbook_path = DEFAULT_ROOT / "ClinicalPipeline_RO_SINGLE_v14_RUNTIME_AUDIT.xlsx"

    if not workbook_path.exists():
        st.session_state["_sem_matcher"]        = None
        st.session_state["_engine_initialized"] = True
        st.warning(f"Workbook TITUS lipsă: {workbook_path}")
        return

    try:
        matcher = _load_semantic_pipeline(str(workbook_path))
        st.session_state["_sem_matcher"]        = matcher
        st.session_state["_engine_initialized"] = True
    except Exception as exc:
        st.session_state["_sem_matcher"]        = None
        st.session_state["_engine_initialized"] = True
        st.error("Eroare la inițializarea SemanticMatcher / narrative_engine")
        st.exception(exc)



def _render_semantic_status() -> None:
    """Afișează permanent statusul semantic în sidebar, după inițializare."""
    matcher = st.session_state.get("_sem_matcher", None)
    available = getattr(matcher, "available", None)
    with st.sidebar:
        st.divider()
        st.markdown("**Semantic Layer**")
        if matcher is None:
            st.caption("SemanticMatcher: missing")
        elif available is True:
            st.caption("SemanticMatcher: active | annotations=EMBED")
        elif available is False:
            st.caption("SemanticMatcher: loaded but unavailable")
        else:
            st.caption(f"SemanticMatcher: exists | available={available}")


@st.cache_resource(show_spinner="Sincronizare cu Google Drive...")
def _download_drive_once() -> dict:
    """
    Descarcă workbook-urile din Google Drive -> disc local, o singură dată
    per sesiune server. Dacă secțiunea [gdrive] nu există în secrets
    (ex. dezvoltare locală fără sincronizare configurată), nu face nimic
    și nu blochează pornirea aplicației.
    """
    if "gdrive" not in st.secrets:
        return {"_skipped": "no gdrive config in secrets"}

    from .drive_sync import download_all
    return download_all(DEFAULT_ROOT)


def main():
    st.set_page_config(
        page_title="TITUS",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    init_state()
    hero()
    init_review_state()

    # ── Sincronizare Google Drive — o singură dată per sesiune server ───────
    _drive_status = _download_drive_once()
    if any(str(v).startswith("error") for v in _drive_status.values()):
        with st.sidebar:
            st.error("⚠️ Eroare sincronizare Google Drive — vezi detalii")
            with st.expander("Detalii sincronizare"):
                st.json(_drive_status)

    # ── Pre-initializare SemanticMatcher + narrative_engine ─────────────────
    _init_semantic_pipeline_once()

    menu, cr_threshold, top_k, api_key = render_sidebar()
    _render_semantic_status()

    st.session_state["cr_threshold"] = cr_threshold
    st.session_state["top_k"] = top_k
    root = str(DEFAULT_ROOT)

    # Cataloage pentru pages_input
    from .loaders import load_name_catalogs, load_riskf_catalog

    # _mtime: suma mtime-urilor cataloagelor — cache invalidat automat la orice modificare
    _cat_mtime = sum(
        os.path.getmtime(str(p)) if os.path.exists(str(p)) else 0.0
        for p in [DEFAULT_SYMPTOMES, DEFAULT_SIGNE, DEFAULT_CATSYMPT, DEFAULT_CATSIGNE]
    )
    all_catalog, sympt_catalog, signe_catalog = load_name_catalogs(
        str(DEFAULT_SYMPTOMES), str(DEFAULT_SIGNE),
        str(DEFAULT_CATSYMPT), str(DEFAULT_CATSIGNE),
        _mtime=_cat_mtime,
    )
    name_catalog = all_catalog

    _rf_mtime = sum(
        os.path.getmtime(str(p)) if os.path.exists(str(p)) else 0.0
        for p in [DEFAULT_RISKF, DEFAULT_CATRISKF]
    )
    riskf_catalog = load_riskf_catalog(
        str(DEFAULT_RISKF), str(DEFAULT_CATRISKF),
        _mtime=_rf_mtime,
    )

    if menu == "📋 Introducere date":
        page_input(
            name_catalog,
            sympt_catalog,
            signe_catalog,
            riskf_catalog,
            api_key,
        )

    elif menu == "📖 Despre":
        st.markdown("## TITUS — Clinical Diagnostic Workspace")
        st.markdown("""
**Platforma:** TITUS  
**Motor diagnostic:** NOSO (Titus_inference.py)  
**NLP clinic:** ANAM  

Flux:
1. **Introducere date** — Profil Pacient · Simptome · Semne clinice · Factori de risc · Anamneze · Review & Finalize
2. **Ranking semiologic** — calcul CR per boala (motorul NOSO)
3. **Interviu** — conversatie ghidata, extragere entitati
4. **Strat contextual** — filtrare pe varsta, sex, geografie
        """)

    else:
        # ── Legea 1: acces blocat pana la validarea profilului ─────────────
        if not st.session_state.get("profile_validated", False):
            st.warning(
                "⛔ Acces restricționat. "
                "Completați și validați **Profilul Pacient** în "
                "**Introducere date → Profil Pacient → Apply profile changes** "
                "înainte de a accesa această funcționalitate."
            )
            st.info(
                "Sumarul fișei pacientului trebuie să apară în "
                "**Review & Finalize** pentru a debloca accesul."
            )
            st.stop()
        # ───────────────────────────────────────────────────────────────────

        if menu == "📊 Ranking semiologic":
            render_ranking(root=root)

        elif menu == "🎤 Interviu":
            if not st.session_state.get("ranking_done", False):
                st.warning("⛔ Interviul este disponibil doar după calcularea rankingului semiologic.")
                st.info("Accesați **Ranking semiologic** și calculați diagnosticele înainte de a continua.")
                st.stop()
            render_interview(root=root)

        elif menu == "🔬 Strat contextual":
            if not st.session_state.get("ranking_done", False):
                st.warning("⛔ Stratul contextual este disponibil doar după calcularea rankingului semiologic.")
                st.info("Accesați **Ranking semiologic** și calculați diagnosticele înainte de a continua.")
                st.stop()
            render_context(root=root)
