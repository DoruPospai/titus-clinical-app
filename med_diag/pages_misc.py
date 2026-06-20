import streamlit as st
from .ui_common import panel_header

def page_settings():
    panel_header(
        "Settings",
        "This page is intentionally light. Operational parameters are already available from the left sidebar."
    )
    st.markdown(
        """
        <div class="dor-footer-note">
            The ranking shown in this application is the latest latent inference with CR filtering,
            followed by a demographic adjustment layer.
        </div>
        """,
        unsafe_allow_html=True,
    )

def page_about():
    panel_header(
        "About",
        "A modularized clinical workspace aligned to the latest ranking logic."
    )
    st.markdown(
        """
        <div class="dor-footer-note">
            This version keeps the overall clinical workflow:
            <br>• patient profile
            <br>• symptom intake
            <br>• clinical sign intake
            <br>• final review editor
            <br>• dedicated ranking page
            <br><br>
            The ranking page follows the latest inference logic: full-catalog latent ranking,
            CR computation, CR filter, demographic adjustment, then Top-K display.
        </div>
        """,
        unsafe_allow_html=True,
    )
