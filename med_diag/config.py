from pathlib import Path

APP_NAME     = "TITUS"
APP_SUBTITLE = "Clinical diagnostic workspace — CR-based analytical ranking"

# Radacina proiectului = directorul care contine app.py (parintele pachetului med_diag)
DEFAULT_ROOT       = Path(__file__).parent.parent.resolve()
DEFAULT_TABEL2     = DEFAULT_ROOT / "data_clean"  / "Tabel2_Titus.xlsx"
DEFAULT_MALADIES   = DEFAULT_ROOT / "data_clean"  / "Maladies.xlsx"
DEFAULT_SYMPTOMES  = DEFAULT_ROOT / "data_clean"  / "Symptomes.xlsx"
DEFAULT_SIGNE      = DEFAULT_ROOT / "data_clean"  / "Signe.xlsx"
DEFAULT_CATSYMPT   = DEFAULT_ROOT / "data_clean"  / "catsympt.xlsx"
DEFAULT_CATSIGNE   = DEFAULT_ROOT / "data_clean"  / "catsigne.xlsx"
DEFAULT_W_MATRIX   = DEFAULT_ROOT / "out_w_matrix" / "Titus_w_matrix.npz"
DEFAULT_RARITATE   = DEFAULT_ROOT / "data_clean"  / "Titus_raritate.csv"
DEFAULT_RISKF      = DEFAULT_ROOT / "data_clean"  / "Riskf.xlsx"
DEFAULT_CATRISKF   = DEFAULT_ROOT / "data_clean"  / "catriskf.xlsx"
DEFAULT_OUTPUT_DIR  = DEFAULT_ROOT / "out_inference_streamlit_titus"
DEFAULT_AGE_META    = DEFAULT_ROOT / "data_clean" / "Order_AgeMetadata_FINAL.xlsx"
DEFAULT_MALADIES_PY = DEFAULT_ROOT / "data_clean" / "Maladies.xlsx"

DEFAULT_CR_THRESHOLD         = 0.40
DEFAULT_PATIENT_SCORE_SCALE  = 150.0
DEFAULT_TOP_K                = 10
DEFAULT_TOP_K_WAITING        = 10   # RARE + COMMON afisate in WaitingRoom

SEMIO_TYPES = {"Sympt", "Signe"}
