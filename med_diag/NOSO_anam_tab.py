# NOSO_anam_tab.py
# Importa dinamic NlpRO la runtime.
# DEFAULT_WORKBOOK si DEFAULT_PIPELINE_SCRIPT sunt citite din NlpRO insusi.

import importlib.util
import time
from pathlib import Path
import streamlit as st


def _load_nlpro_module(script_path: str):
    """Incarca NlpRO ca modul. Cache manual cu detectie mtime."""
    key = f"nlpro_mod_{script_path}"
    try:
        mtime = Path(script_path).stat().st_mtime
    except OSError:
        mtime = 0

    if (st.session_state.get(f"{key}_mtime") == mtime and
            st.session_state.get(key) is not None):
        return st.session_state[key]

    spec = importlib.util.spec_from_file_location(
        f"nlpro_{int(time.time()*1000)}", script_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    st.session_state[key]             = mod
    st.session_state[f"{key}_mtime"] = mtime
    return mod


def render_anam_nlpro(root: str = ""):
    ss = st.session_state
    default_root = Path(root) if root else Path(".")

    # Calea NlpRO din sidebar (utilizatorul o seteaza o singura data)
    script_path = ss.get("sidebar_nlpro_script", str(default_root / "NlpRO.py"))
    st.warning(f"NlpRO încărcat din: {script_path}")

    if not Path(script_path).exists():
        st.warning(f"Script NlpRO negasit: `{script_path}`")
        st.info("Setati calea in sidebar → **NlpRO script**.")
        return

    try:
        mod = _load_nlpro_module(script_path)

        # Afiseaza DEFAULT_WORKBOOK si DEFAULT_PIPELINE_SCRIPT din NlpRO
        wb   = getattr(mod, "DEFAULT_WORKBOOK",       "?")
        pipe = getattr(mod, "DEFAULT_PIPELINE_SCRIPT","?")
        with st.expander("Configurare NlpRO (din script)", expanded=False):
            st.caption(f"**Workbook:** `{wb}`")
            st.caption(f"**Pipeline:**  `{pipe}`")

        if hasattr(mod, "render_main_page"):
            mod.render_main_page()
        else:
            st.error(
                f"`render_main_page()` lipseste din `{Path(script_path).name}`.\n\n"
                "Adauga in NlpRO.py:\n"
                "```python\n"
                "def render_main_page():\n"
                "    # tot codul curent\n"
                "    ...\n\n"
                "if __name__ == '__main__':\n"
                "    render_main_page()\n"
                "```"
            )
    except Exception as ex:
        st.error(f"Eroare la incarcarea NlpRO: {ex}")
        import traceback
        st.code(traceback.format_exc())
