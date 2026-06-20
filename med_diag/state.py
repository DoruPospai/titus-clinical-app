import pandas as pd
import streamlit as st


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("menu", "Input")
    ss.setdefault("top_k", 10)
    ss.setdefault("editor_rows", [])

    # Rezultate TITUS
    ss.setdefault("titus_ranking_df",  pd.DataFrame())
    ss.setdefault("titus_waiting_df",  pd.DataFrame())
    ss.setdefault("titus_raw_output",  None)   # dict complet din diagnose()
    ss.setdefault("titus_demo_applied", False)  # True daca factorul demografic e activ
    ss.setdefault("titus_demo_df",      None)   # DataFrame ranking ajustat demografic

    ss.setdefault("voice_transcript_sympt", "")
    ss.setdefault("voice_transcript_signe", "")

    ss.setdefault("profile_validated", False)  # True dupa Apply profile changes
    ss.setdefault("profile_summary", "")       # Sumar afisat in Review & Finalize
    ss.setdefault("ranking_done", False)       # True dupa primul ranking calculat

    ss.setdefault(
        "patient_profile",
        {
            "user_id"      : 1,
            "dob"          : pd.Timestamp("1990-01-01").date(),
            "gender"       : "Female",
            "living_in"    : "Europe South",
            "ethnics"      : "Caucasian",
            "pregnancy"    : "No",
            "weeks_pregnant": None,
            "age_in_months": 0,
        },
    )
