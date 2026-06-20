# DOR_NlpRO_streamlit_app_v16_correct_lexicon_insert_fix.py
# Filename: DOR_NlpRO_streamlit_app_v16_correct_lexicon_insert_fix.py
#
# NlpRO - Romanian Clinical NLP Streamlit Interface
#
# Expected files in the same folder:
#   - ClinicalPipeline_RO_SINGLE_v11_AUTOSUGGEST.xlsx
#   - DOR_clinical_pipeline_singlefile_v12_autosuggest_all.py
#
# Install:
#   pip install streamlit pandas openpyxl
#
# Run:
#   streamlit run DOR_NlpRO_streamlit_app_v01.py

from pathlib import Path
from datetime import datetime
import io
import json
import re
import subprocess
import sys
import time

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WORKBOOK = BASE_DIR / "ClinicalPipeline_RO_SINGLE_v14_RUNTIME_AUDIT.xlsx"

DEFAULT_PIPELINE_SCRIPT = BASE_DIR / "DOR_clinical_pipeline_singlefile_v19_ACTIVE_DIALOG_ONLY.py"


# ── Pre-initializare SemanticMatcher la startup Streamlit ─────────────────
# Construit o singura data cu @st.cache_resource - supravietuieste reruns.
# Pipeline-ul in-process il preia din variabila globala _GLOBAL_SEMANTIC,
# evitand descarcarea modelului de pe HuggingFace in context capturat.
@st.cache_resource
def _init_semantic_matcher():
    try:
        import pandas as pd
        from med_diag.semantic_layer import SemanticMatcher
        _lex = pd.read_excel(DEFAULT_WORKBOOK, sheet_name="Lexicon")
        _m = SemanticMatcher(DEFAULT_WORKBOOK, _lex)
        if _m.available:
            return _m
        return None
    except Exception:
        return None

_GLOBAL_SEMANTIC = _init_semantic_matcher()





def normalize_speaker(raw):
    s = str(raw).strip().lower()
    aliases = {
        "doctor": "doctor",
        "dr": "doctor",
        "medic": "doctor",
        "medicul": "doctor",
        "patient": "patient",
        "pacient": "patient",
        "pacienta": "patient",
        "pacientă": "patient",
        "bolnav": "patient",
        "bolnavul": "patient",
    }
    return aliases.get(s, s)


def parse_transcript_text(text):
    text = text.replace("\ufeff", "")
    lines = text.splitlines()

    dialog_id = ""
    case_title = ""
    turns = []

    current_speaker = None
    current_text_parts = []

    def flush_current():
        nonlocal current_speaker, current_text_parts, turns
        if current_speaker and current_text_parts:
            clean_text = " ".join(x.strip() for x in current_text_parts if x.strip()).strip()
            if clean_text:
                turns.append((current_speaker, clean_text))
        current_speaker = None
        current_text_parts = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue

        m_case = re.match(r"^(CASE|CAZ|TITLE|TITLU)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if m_case:
            case_title = m_case.group(2).strip()
            continue

        m_id = re.match(r"^(DIALOG_ID|ID|DIALOGUE_ID)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if m_id:
            dialog_id = m_id.group(2).strip()
            continue

        m_turn = re.match(
            r"^(Doctor|Dr|Medic|Medicul|Patient|Pacient|Pacienta|Pacientă|Bolnav|Bolnavul)\s*:\s*(.*)$",
            line,
            flags=re.IGNORECASE,
        )
        if m_turn:
            flush_current()
            current_speaker = normalize_speaker(m_turn.group(1))
            first_text = m_turn.group(2).strip()
            if first_text:
                current_text_parts.append(first_text)
            continue

        if current_speaker:
            current_text_parts.append(line)

    flush_current()

    if not dialog_id:
        dialog_id = f"DLG_IMPORTED_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    rows = []
    for i, (speaker, utterance) in enumerate(turns, start=1):
        rows.append({
            "dialog_id": dialog_id,
            "turn_id": i,
            "speaker": speaker,
            "text": utterance,
            "theme": case_title,
            "specialty": "",
            "case_type": "streamlit_loaded_transcript",
            "language": "ro",
            "NormalizedText": "",
        })

    return dialog_id, case_title, pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_workbook(path_str):
    path = Path(path_str)
    if not path.exists():
        return {}

    try:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    except Exception as exc:
        st.error(f"Nu pot citi workbook-ul: {exc}")
        return {}

    return {name: df.fillna("") for name, df in sheets.items()}


def save_workbook(path, sheets):
    preferred = [
        "Lexicon",
        "Dialogues",
        "Annotations",
        "PatientVectors",
        "MedDiagInput",
        "ClinicalSynthesis",
        "Unmatched",
        "Summary",
        "LoaderLog",
    ]

    with pd.ExcelWriter(path, engine="openpyxl", mode="w") as writer:
        written = set()

        for name in preferred:
            if name in sheets:
                sheets[name].to_excel(writer, index=False, sheet_name=name)
                written.add(name)

        for name, df in sheets.items():
            if name not in written:
                df.to_excel(writer, index=False, sheet_name=name)


def append_dialogue_to_workbook(workbook_path, new_dialogue, dialog_id, case_title, replace_existing=True):
    sheets = load_workbook(str(workbook_path)).copy()

    if "Dialogues" not in sheets:
        raise ValueError("Workbook-ul nu conține foaia Dialogues.")

    dialogues = sheets["Dialogues"].copy()

    required_columns = [
        "dialog_id",
        "turn_id",
        "speaker",
        "text",
        "theme",
        "specialty",
        "case_type",
        "language",
        "NormalizedText",
    ]

    for col in required_columns:
        if col not in dialogues.columns:
            dialogues[col] = ""

    new_dialogue = new_dialogue[required_columns]

    if replace_existing:
        before = len(dialogues)
        dialogues = dialogues[dialogues["dialog_id"].astype(str) != dialog_id].copy()
        removed = before - len(dialogues)
    else:
        removed = 0

    dialogues = pd.concat([dialogues, new_dialogue], ignore_index=True)
    sheets["Dialogues"] = dialogues

    log_row = pd.DataFrame([{
        "loaded_at": datetime.now().isoformat(timespec="seconds"),
        "dialog_id": dialog_id,
        "case_title": case_title,
        "turns_loaded": len(new_dialogue),
        "previous_rows_removed_same_dialog_id": removed,
        "source": "NlpRO Streamlit",
    }])

    if "LoaderLog" in sheets:
        sheets["LoaderLog"] = pd.concat([sheets["LoaderLog"], log_row], ignore_index=True)
    else:
        sheets["LoaderLog"] = log_row

    save_workbook(workbook_path, sheets)
    load_workbook.clear()

    return removed, len(new_dialogue)


def run_pipeline(script_path, workbook_path=None, active_dialog_id=None, fast=False):
    """
    Run pipeline on selected workbook.

    V20: apel direct in-process (elimina subprocess + 2x I/O Excel).
    Fallback pe subprocess daca importul esueaza.
    """
    if not script_path.exists():
        raise FileNotFoundError(f"Nu găsesc scriptul pipeline: {script_path}")

    # ── Incercare apel direct in-process ─────────────────────────────────
    try:
        import importlib.util, io, contextlib

        # Injecteaza argumentele in sys.argv (pipeline le citeste din sys.argv)
        _orig_argv = sys.argv[:]
        sys.argv = [str(script_path)]
        if workbook_path is not None:
            sys.argv.append(str(Path(workbook_path).resolve()))
        if active_dialog_id:
            sys.argv.append(str(active_dialog_id))
        if fast:
            sys.argv.append("--fast")

        # Incarca modulul pipeline dinamic
        spec = importlib.util.spec_from_file_location("_pipeline_mod", str(script_path))
        mod  = importlib.util.module_from_spec(spec)

        # Captureaza stdout/stderr
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            spec.loader.exec_module(mod)
            mod.main()

        sys.argv = _orig_argv
        load_workbook.clear()
        return 0, buf_out.getvalue(), buf_err.getvalue()

    except Exception as _e:
        # ── Fallback: subprocess (comportamentul vechi) ───────────────────
        sys.argv = _orig_argv if '_orig_argv' in dir() else sys.argv
        import io as _io

        cmd = [sys.executable, str(script_path)]
        if workbook_path is not None:
            cmd.append(str(Path(workbook_path).resolve()))
        if active_dialog_id:
            cmd.append(str(active_dialog_id))
        if fast:
            cmd.append("--fast")

        result = subprocess.run(
            cmd,
            cwd=str(script_path.parent),
            capture_output=True,
            text=True,
        )
        import time
        time.sleep(0.5)
        load_workbook.clear()
        return result.returncode, result.stdout, result.stderr + f"\n[Fallback subprocess: {_e}]"


def run_pipeline_with_sync(script_path, workbook_path=None, active_dialog_id=None, fast=False):
    """
    Wrapper peste run_pipeline(): după rularea pipeline-ului (succes sau
    fallback subprocess), încarcă workbook-urile actualizate pe Google Drive.

    Upload-ul e best-effort — daca secțiunea [gdrive] nu există în secrets
    (dezvoltare locală fără sincronizare configurată) sau apare orice eroare
    de rețea, NU blochează returnarea rezultatului pipeline-ului. Eroarea
    de sync e doar adăugată la stderr, vizibilă în "Pipeline output".
    """
    returncode, stdout, stderr = run_pipeline(
        script_path, workbook_path=workbook_path,
        active_dialog_id=active_dialog_id, fast=fast,
    )

    try:
        if "gdrive" in st.secrets:
            # Import absolut, nu relativ — NlpRO.py rulează fără context de
            # pachet Python (direct sau via importlib.spec_from_file_location),
            # deci "from .drive_sync import ..." eșuează cu
            # "attempted relative import with no known parent package".
            import sys as _sys
            _med_diag_dir = Path(__file__).resolve().parent / "med_diag"
            if str(_med_diag_dir) not in _sys.path:
                _sys.path.insert(0, str(_med_diag_dir))
            from drive_sync import upload_all
            root = Path(workbook_path).resolve().parent if workbook_path else Path(script_path).resolve().parent
            sync_status = upload_all(root)
            failed = {k: v for k, v in sync_status.items() if str(v).startswith("error")}
            if failed:
                stderr += f"\n[Drive sync - erori]: {failed}"
            else:
                stdout += f"\n[Drive sync] {len(sync_status)} fișiere sincronizate cu Google Drive."
    except Exception as _sync_exc:
        stderr += f"\n[Drive sync - excepție neprevăzută]: {_sync_exc}"

    return returncode, stdout, stderr


def dataframe_download_button(df, filename, label):
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        label=label,
        data=buffer.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def severity_label_from_score(score):
    try:
        s = int(float(score))
    except Exception:
        return ""
    if s >= 3:
        return "puternic"
    if s == 2:
        return "moderat"
    if s == 1:
        return "slab"
    return ""



def _fix_embedded_negation_polarity(annotations_df: pd.DataFrame) -> pd.DataFrame:
    """
    Post-processing: corectează polaritatea pentru expresii unde negația
    face parte din expresia lexicală însăși.
    Ex: "nu mai am energie deloc" → matched_expression conține "nu mai am"
        → pipeline marcheaza "rezolvat" dar trebuie "prezent"
    Ex: "am luat în greutate fără să mănânc" → "fără" e în expresie → prezent
    """
    import unicodedata as _uc

    def _norm(t):
        n = _uc.normalize("NFKD", str(t).lower())
        n = "".join(c for c in n if not _uc.combining(c))
        return re.sub(r"[^a-z0-9\s]+", " ", n).strip()

    # Pattern-uri de negatie care TREBUIE sa fie in expresia lexicala pentru override
    RESOLVED_PATS = [
        r"\bnu mai am\b", r"\bnu mai simt\b", r"\bnu mai prezint\b",
        r"\bnu mai pot\b", r"\bnu mai am\b",
    ]
    ABSENT_PATS = [
        r"\bfara\b", r"\bnu am\b", r"\bn am\b",
        r"\bnu pot\b", r"\bnu simt\b",
    ]

    df = annotations_df.copy()

    if "matched_expression" not in df.columns:
        return df
    if "DetectedPolarity" not in df.columns:
        return df

    for idx, row in df.iterrows():
        pol = str(row.get("DetectedPolarity", "")).strip()
        if pol not in ("rezolvat", "absent"):
            continue

        expr = _norm(str(row.get("matched_expression", "")))
        if not expr:
            continue

        # Daca pattern-ul care a cauzat pol=rezolvat/absent e in expresia insasi → prezent
        if pol == "rezolvat":
            for pat in RESOLVED_PATS:
                if re.search(pat, expr):
                    df.at[idx, "DetectedPolarity"] = "prezent"
                    break
        elif pol == "absent":
            for pat in ABSENT_PATS:
                if re.search(pat, expr):
                    df.at[idx, "DetectedPolarity"] = "prezent"
                    break

    return df

def build_mediag_display_table(active_annotations):
    """
    Build a clinically readable table for the selected dialogue:
      CodeElement + NatureElement + CatalogName + polarity + estimated intensity/severity.
    """
    if active_annotations is None or active_annotations.empty:
        return pd.DataFrame(columns=[
            "Type",
            "Code",
            "Element",
            "Polarity",
            "EstimatedIntensity",
            "TemporalContext",
            "ClinicalContext",
            "MatchedExpression",
        ])

    df = active_annotations.copy()

    for col in [
        "NatureElement", "CodeElement", "CatalogName", "DetectedPolarity",
        "DetectedSeverity", "SeverityScore", "puternicitate",
        "DetectedTemporality", "TemporalContext", "TriggerContext",
        "BodyRegion", "ClinicalIntent", "matched_expression"
    ]:
        if col not in df.columns:
            df[col] = ""

    # Scor numeric pentru intensitate — folosit la deduplicare (max per key)
    _INT_RANK = {"puternic": 3, "severe": 3, "sever": 3, "intens": 3,
                 "moderat": 2, "moderate": 2,
                 "slab": 1, "mild": 1, "": 0}

    def _int_rank(r):
        v = str(r.get("puternicitate", "")).strip().lower()
        if v:
            return _INT_RANK.get(v, 2)
        v2 = str(r.get("DetectedSeverity", "")).strip().lower()
        return _INT_RANK.get(v2, 0)

    # Grupare pe (NatureElement, CodeElement, DetectedPolarity) — pastreaza randul cu intensitate maxima
    best = {}  # key -> (rank, row)
    for _, r in df.iterrows():
        code = str(r.get("CodeElement", "")).strip()
        typ  = str(r.get("NatureElement", "")).strip()
        pol  = str(r.get("DetectedPolarity", "")).strip() or str(r.get("Polaritate", "")).strip()
        key  = (typ, code, pol)
        rank = _int_rank(r)
        if key not in best or rank > best[key][0]:
            best[key] = (rank, r)

    rows = []
    for key, (_, r) in best.items():
        code = key[1]
        typ  = key[0]
        pol  = key[2]
        name = str(r.get("CatalogName", "")).strip()

        lex_intensity  = str(r.get("puternicitate", "")).strip()
        detected_sev   = str(r.get("DetectedSeverity", "")).strip()
        severity_score = str(r.get("SeverityScore", "")).strip()

        # Lexicon este sursa primara de intensitate (fotografia starii pacientului)
        if lex_intensity:
            estimated_intensity = lex_intensity
        elif detected_sev:
            estimated_intensity = detected_sev
        else:
            estimated_intensity = severity_label_from_score(severity_score)

        context_parts = []
        for c in ["TriggerContext", "BodyRegion", "ClinicalIntent"]:
            v = str(r.get(c, "")).strip()
            if v and v not in context_parts:
                context_parts.append(v)

        temporal_parts = []
        for c in ["DetectedTemporality", "TemporalContext"]:
            v = str(r.get(c, "")).strip()
            if v and v not in temporal_parts:
                temporal_parts.append(v)

        rows.append({
            "Type": typ,
            "Code": code,
            "Element": name,
            "Polarity": pol,
            "EstimatedIntensity": estimated_intensity,
            "TemporalContext": "; ".join(temporal_parts),
            "ClinicalContext": "; ".join(context_parts),
            "MatchedExpression": str(r.get("matched_expression", "")).strip(),
        })

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    sort_order = {"Sympt": 1, "Signe": 2, "RiskF": 3}
    out["_sort"] = out["Type"].map(sort_order).fillna(9)
    out = out.sort_values(["_sort", "Polarity", "Code"]).drop(columns=["_sort"]).reset_index(drop=True)
    return out


def safe_sheet(sheets, name):
    return sheets.get(name, pd.DataFrame())


def save_sheet_to_workbook(workbook_path, sheet_name, new_df):
    """
    Replace a single sheet inside the workbook while preserving the other sheets.
    Used for saving AutoSuggestions validation edits from Streamlit.
    """
    sheets_local = load_workbook(str(workbook_path)).copy()
    sheets_local[sheet_name] = new_df.fillna("")

    preferred = [
        "Lexicon",
        "Dialogues",
        "Annotations",
        "PatientVectors",
        "MedDiagInput",
        "ClinicalSynthesis",
        "AutoSuggestions",
        "Unmatched",
        "Summary",
        "LoaderLog",
    ]

    with pd.ExcelWriter(workbook_path, engine="openpyxl", mode="w") as writer:
        written = set()
        for name in preferred:
            if name in sheets_local:
                sheets_local[name].to_excel(writer, index=False, sheet_name=name)
                written.add(name)

        for name, df in sheets_local.items():
            if name not in written:
                df.to_excel(writer, index=False, sheet_name=name)

    load_workbook.clear()




def get_lexicon_patch_path(workbook_path: Path) -> Path:
    workbook_path = Path(workbook_path)
    return workbook_path.with_name(f"{workbook_path.stem}_LexiconPatch.csv")


def _normalize_patch_cell(v):
    return "" if v is None else str(v).strip()


def build_lexicon_patch_rows(full_lex: pd.DataFrame, edited: pd.DataFrame, actor: str = "NlpRO"):
    full_lex = full_lex.copy().fillna("")
    edited = edited.copy().fillna("")

    if "ExprID" not in full_lex.columns:
        full_lex["ExprID"] = ""
    if "ExprID" not in edited.columns:
        edited["ExprID"] = ""

    payload_cols = [
        "ExpresiePacient",
        "CodeElement",
        "Nature Element",
        "TypeElement",
        "CatalogName",
        "ElementStandard",
        "SemanticDomain",
        "puternicitate",
        "Polaritate",
        "ReviewStatus",
        "ReviewerNote",
    ]

    for col in payload_cols:
        if col not in full_lex.columns:
            full_lex[col] = ""
        if col not in edited.columns:
            edited[col] = ""

    by_id = {
        str(row.get("ExprID", "")).strip(): row
        for _, row in full_lex.iterrows()
        if str(row.get("ExprID", "")).strip()
    }

    rows = []
    now = datetime.now().isoformat(timespec="seconds")

    for _, erow in edited.iterrows():
        expr_id = _normalize_patch_cell(erow.get("ExprID", ""))

        if not expr_id:
            meaningful = [_normalize_patch_cell(erow.get(c, "")) for c in payload_cols]
            if not any(meaningful):
                continue

        action = "update" if expr_id and expr_id in by_id else "add"

        if action == "update":
            original = by_id[expr_id]
            changed = any(
                _normalize_patch_cell(original.get(col, "")) != _normalize_patch_cell(erow.get(col, ""))
                for col in payload_cols
            )
            if not changed:
                continue

        patch = {
            "PatchID": f"PATCH_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            "CreatedAt": now,
            "Actor": actor,
            "Action": action,
            "Status": "pending",
            "ExprID": expr_id,
        }

        for col in payload_cols:
            patch[col] = _normalize_patch_cell(erow.get(col, ""))

        if action == "add":
            if not patch["Polaritate"]:
                patch["Polaritate"] = "prezent"
            if not patch["puternicitate"]:
                patch["puternicitate"] = "moderat"
            if not patch["ReviewStatus"]:
                patch["ReviewStatus"] = "ManualLexiconPatch"
            if not patch["ReviewerNote"]:
                patch["ReviewerNote"] = "MAPPING_NOTE: Added through LexiconPatch."
            if not patch["TypeElement"]:
                patch["TypeElement"] = patch.get("Nature Element", "")

        rows.append(patch)

    return rows


def append_lexicon_patch(workbook_path: Path, patch_rows: list[dict]) -> Path:
    patch_path = get_lexicon_patch_path(workbook_path)

    if not patch_rows:
        return patch_path

    patch_df = pd.DataFrame(patch_rows)

    if patch_path.exists():
        old = pd.read_csv(patch_path, dtype=str).fillna("")
        patch_df = pd.concat([old, patch_df], ignore_index=True)

    patch_df.to_csv(patch_path, index=False, encoding="utf-8-sig")
    return patch_path


def render_main_page():
    try:
        st.set_page_config(page_title="NlpRO", page_icon="🩺", layout="wide")
    except Exception:
        pass  # set_page_config deja apelat de TITUS
    st.title("🩺 NlpRO")
    st.caption("VERSION: V20_OPTIMIZED — LexiconPatch + V19 active-dialog-only pipeline + no rerun after patch save.")
    st.caption("Romanian Clinical NLP Corpus • Anamneză → Annotations → Patient Vector → MedDiag Bridge → Clinical Synthesis")

    with st.sidebar:
        st.header("Configuration")

        workbook_path_str = st.text_input("Workbook Excel", value=str(DEFAULT_WORKBOOK), key="nlpro_wb_path")
        pipeline_script_str = st.text_input("Pipeline script", value=str(DEFAULT_PIPELINE_SCRIPT), key="nlpro_pipe_path")

        workbook_path = Path(workbook_path_str)
        pipeline_script = Path(pipeline_script_str)

        st.caption("Pipeline-ul rulează pe workbook-ul activ din sidebar. V17 creează backup automat înainte de scriere.")

        st.divider()

        if st.button("🔄 Reload workbook"):
            load_workbook.clear()
            st.rerun()

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            _do_fast = st.button("▶️ Run fast", help="Fara audit lexicon (~15s)")
        with col_r2:
            _do_full = st.button("▶️ Run full", help="Cu audit complet (~32s)")

        if _do_fast or _do_full:
            try:
                code, stdout, stderr = run_pipeline_with_sync(
                    pipeline_script, workbook_path,
                    st.session_state.get('active_dialog_id', ''),
                    fast=_do_fast
                )
                if code == 0:
                    st.success("Pipeline rulat cu succes.")
                else:
                    st.error(f"Pipeline error code: {code}")

                with st.expander("Pipeline output"):
                    st.code(stdout or "(no stdout)")
                    if stderr:
                        st.code(stderr)
            except Exception as exc:
                st.error(str(exc))


    if not workbook_path.exists():
        st.error(f"Workbook-ul nu există: {workbook_path}")
        return

    sheets = load_workbook(str(workbook_path))
    if not sheets:
        st.error("Workbook-ul nu a putut fi încărcat.")
        return

    lexicon = safe_sheet(sheets, "Lexicon")
    dialogues = safe_sheet(sheets, "Dialogues")
    annotations = safe_sheet(sheets, "Annotations")
    patient_vectors = safe_sheet(sheets, "PatientVectors")
    mediag = safe_sheet(sheets, "MedDiagInput")
    synthesis = safe_sheet(sheets, "ClinicalSynthesis")
    unmatched = safe_sheet(sheets, "Unmatched")
    autosuggestions = safe_sheet(sheets, "AutoSuggestions")
    summary = safe_sheet(sheets, "Summary")

    # Status is hidden by default to keep the interface clinically focused.
    with st.expander("Advanced / Debug status", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Lexicon rows", len(lexicon))
        c2.metric("Dialogues turns", len(dialogues))
        c3.metric("Annotations", len(annotations))
        c4.metric("Patient vectors", len(patient_vectors))
        c5.metric("Unmatched", len(unmatched))

        if not annotations.empty and "DetectedPolarity" in annotations.columns:
            p1, p2, p3 = st.columns(3)
            p1.metric("Present", int((annotations["DetectedPolarity"] == "prezent").sum()))
            p2.metric("Absent", int((annotations["DetectedPolarity"] == "absent").sum()))
            p3.metric("Resolved", int((annotations["DetectedPolarity"] == "rezolvat").sum()))

    st.divider()
    st.subheader("Consultație activă")

    if not dialogues.empty and "dialog_id" in dialogues.columns:
        all_dialog_ids = sorted(dialogues["dialog_id"].astype(str).dropna().unique())
    else:
        all_dialog_ids = []

    # Aplica pending dialog (setat de transcript loader sau delete) inainte de widget
    if "_pending_dialog_id" in st.session_state:
        pending = st.session_state.pop("_pending_dialog_id")
        if pending in all_dialog_ids:
            st.session_state["active_dialog_id"] = pending

    if "active_dialog_id" not in st.session_state:
        st.session_state["active_dialog_id"] = all_dialog_ids[0] if all_dialog_ids else ""

    col_sel, col_del = st.columns([4, 1])
    with col_sel:
        active_dialog_id = st.selectbox(
            "Select active dialog_id",
            all_dialog_ids,
            index=all_dialog_ids.index(st.session_state["active_dialog_id"]) if st.session_state["active_dialog_id"] in all_dialog_ids else 0,
            key="active_dialog_id",
        )
    with col_del:
        st.write("")  # aliniere verticala
        delete_clicked = st.button("🗑️ Șterge", key="nlpro_delete_dialog",
                                   help=f"Șterge dialogul activ din workbook",
                                   use_container_width=True)

    if delete_clicked and active_dialog_id:
        confirm_key = f"nlpro_confirm_del_{active_dialog_id}"
        if not st.session_state.get(confirm_key, False):
            st.session_state[confirm_key] = True
            st.warning(f"Ești sigur că vrei să ștergi **{active_dialog_id}**? Apasă din nou 🗑️ pentru confirmare.")
        else:
            try:
                sheets_rw = load_workbook(str(workbook_path)).copy()
                SHEETS_WITH_DIALOG = [
                    "Dialogues", "Annotations", "PatientVectors",
                    "MedDiagInput", "ClinicalSynthesis", "Unmatched",
                    "AutoSuggestions",
                ]
                total_removed = 0
                for sname in SHEETS_WITH_DIALOG:
                    if sname in sheets_rw and "dialog_id" in sheets_rw[sname].columns:
                        before = len(sheets_rw[sname])
                        sheets_rw[sname] = sheets_rw[sname][
                            sheets_rw[sname]["dialog_id"].astype(str) != active_dialog_id
                        ].reset_index(drop=True)
                        total_removed += before - len(sheets_rw[sname])

                save_workbook(workbook_path, sheets_rw)
                load_workbook.clear()
                st.session_state.pop(confirm_key, None)
                st.session_state.pop("active_dialog_id", None)
                st.success(f"Dialog **{active_dialog_id}** șters ({total_removed} rânduri eliminate).")
                st.rerun()
            except Exception as _exc:
                st.error(f"Eroare la ștergere: {_exc}")

    def filter_by_active_dialog(df, dialog_id):
        if df is None or df.empty or "dialog_id" not in df.columns or not dialog_id:
            return df.iloc[0:0].copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        return df[df["dialog_id"].astype(str) == str(dialog_id)].copy()

    active_dialogues = filter_by_active_dialog(dialogues, active_dialog_id)
    active_annotations = filter_by_active_dialog(annotations, active_dialog_id)
    active_patient_vectors = filter_by_active_dialog(patient_vectors, active_dialog_id)
    active_mediag = filter_by_active_dialog(mediag, active_dialog_id)
    active_synthesis = filter_by_active_dialog(synthesis, active_dialog_id)
    active_unmatched = filter_by_active_dialog(unmatched, active_dialog_id)
    active_autosuggestions = filter_by_active_dialog(autosuggestions, active_dialog_id)

    with st.expander("Detalii tehnice pentru consultația activă", expanded=False):
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Active turns", len(active_dialogues))
        a2.metric("Active annotations", len(active_annotations))
        a3.metric("Active patient vector rows", len(active_patient_vectors))
        a4.metric("Active unmatched", len(active_unmatched))
        st.metric("Active autosuggestions", len(active_autosuggestions))

    tabs = st.tabs([
        "ClinicalSynthesis",
        "MedDiagInput",
        "Annotations",
        "Transcript",
        "Load transcript",
        "AutoSuggestions",
        "Unmatched",
        "Lexicon",
        "Correct Lexicon",
        "Advanced",
    ])


    with tabs[0]:
        st.subheader(f"ClinicalSynthesis — {active_dialog_id}")

        if not active_synthesis.empty:
            row = active_synthesis.head(1)
            r = row.iloc[0]
            st.markdown("### Sinteză clinică")
            st.write(r.get("ClinicalSynthesis", ""))
            st.markdown("### Orientare clinică")
            st.write(r.get("ClinicalOrientation", ""))
            st.markdown("### Triage hint")
            st.warning(r.get("TriageHint", ""))
            with st.expander("Rând complet ClinicalSynthesis", expanded=False):
                st.dataframe(row, use_container_width=True)
        else:
            st.info("Nu există sinteză clinică pentru consultația selectată. Rulează pipeline-ul.")


    with tabs[1]:
        st.subheader(f"MedDiagInput / DiagMed input — {active_dialog_id}")
        st.caption("Acesta este inputul care trebuie trimis către DiagMed pentru consultația selectată.")

        if not active_mediag.empty and "MedDiagPayloadJSON" in active_mediag.columns:
            row = active_mediag.head(1)
            payload = row.iloc[0].get("MedDiagPayloadJSON", "")

            try:
                parsed_payload = json.loads(payload)
            except Exception:
                parsed_payload = None

            active_annotations = _fix_embedded_negation_polarity(active_annotations)
            display_table = build_mediag_display_table(active_annotations)

            st.markdown("### Elemente trimise către DiagMed")
            if not display_table.empty:
                st.dataframe(display_table, use_container_width=True, height=350)

                # ── Buton Trimite către Review & Finalize (TITUS) ────────────
                if st.button("📤 Trimite către Review & Finalize",
                             key="nlpro_send_to_review",
                             type="primary",
                             use_container_width=True):
                    try:
                        src_label = f"nlpro:{active_dialog_id}"

                        # Lookup ElementStandard RO din lexicon
                        ro_label: dict = {}
                        if not lexicon.empty:
                            for _, lx in lexicon.iterrows():
                                _cod = str(lx.get("CodeElement","")).strip().zfill(4)
                                _nat = str(lx.get("Nature Element","")).strip()
                                _std = str(lx.get("ElementStandard","")).strip()
                                if _cod and _nat and _std:
                                    ro_label[f"{_nat}:{_cod}"] = _std

                        # Mapare intensitate → weight
                        # Sursa primara: Lexicon (slab/moderat/puternic)
                        # Fallback: DetectedSeverity (severe/moderate/mild)
                        def _intensity_to_weight(intens: str) -> int:
                            v = str(intens).lower().strip()
                            if v in ("puternic", "puternice", "severe", "severă", "severa", "sever", "high", "intens"):
                                return 150
                            if v in ("slab", "mild", "ușoară", "usoara", "usor", "low"):
                                return 50
                            return 100  # moderat / moderate / default

                        rows = []
                        for _, r in display_table[display_table["Polarity"] == "prezent"].iterrows():
                            code_raw = str(r.get("Code", "")).strip()
                            nat      = str(r.get("Type", "Sympt")).strip()
                            try:
                                code_int = int(code_raw)
                            except ValueError:
                                continue
                            key_padded = f"{nat}:{code_int:04d}"
                            label_ro   = ro_label.get(key_padded, str(r.get("Element", "")))
                            weight     = _intensity_to_weight(r.get("EstimatedIntensity", ""))
                            rows.append({
                                "Key":    key_padded,
                                "Nature": nat,
                                "Code":   code_int,
                                "Label":  label_ro,
                                "Weight": weight,
                                "Source": src_label,
                            })

                        if rows:
                            current = st.session_state.get("editor_rows", [])
                            cur_df  = pd.DataFrame(current) if current else pd.DataFrame(
                                columns=["Key","Nature","Code","Label","Weight","Source"])
                            new_df  = pd.DataFrame(rows)
                            merged  = pd.concat([cur_df, new_df], ignore_index=True)
                            # Pastreaza weight-ul maxim per Key (intensitatea cea mai severa)
                            merged["Weight"] = pd.to_numeric(merged["Weight"], errors="coerce").fillna(100)
                            idx_max = merged.groupby("Key")["Weight"].idxmax()
                            merged  = merged.loc[idx_max].reset_index(drop=True)
                            st.session_state["editor_rows"] = merged.to_dict(orient="records")
                            st.success(f"✓ {len(rows)} elemente trimise către Review & Finalize.")
                        else:
                            st.warning("Niciun element cu polarity=prezent de trimis.")
                    except Exception as _exc:
                        st.error(f"Eroare la trimitere: {_exc}")

                csv_payload = display_table.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download selected DiagMed readable table CSV",
                    data=csv_payload,
                    file_name=f"DiagMed_elements_{active_dialog_id}.csv",
                    mime="text/csv",
                )
            else:
                st.info("Nu există elemente anotate pentru consultația selectată.")

            if parsed_payload:
                with st.expander("Coduri brute DiagMed", expanded=False):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.write("Sympt")
                    c1.code(",".join(parsed_payload.get("sympt", [])) or "—")
                    c2.write("Signe")
                    c2.code(",".join(parsed_payload.get("signe", [])) or "—")
                    c3.write("RiskF")
                    c3.code(",".join(parsed_payload.get("riskf", [])) or "—")
                    c4.write("Absent")
                    c4.code(",".join(parsed_payload.get("absent", [])) or "—")
                    c5.write("Resolved")
                    c5.code(",".join(parsed_payload.get("resolved", [])) or "—")

                with st.expander("Payload JSON complet", expanded=False):
                    st.json(parsed_payload)
            else:
                st.code(payload)

            st.download_button(
                label="Download selected DiagMed payload JSON",
                data=payload.encode("utf-8"),
                file_name=f"DiagMed_payload_{active_dialog_id}.json",
                mime="application/json",
            )

            with st.expander("Rând complet MedDiagInput", expanded=False):
                st.dataframe(active_mediag, use_container_width=True, height=250)
        else:
            st.info("Nu există MedDiagInput pentru consultația selectată. Rulează pipeline-ul.")


    with tabs[2]:
        st.subheader(f"Annotations — {active_dialog_id}")

        if not active_annotations.empty:
            preferred_cols = [
                "matched_expression",
                "CodeElement",
                "NatureElement",
                "CatalogName",
                "DetectedPolarity",
                "DetectedTemporality",
                "DetectedSeverity",
                "utterance",
            ]
            cols = [c for c in preferred_cols if c in active_annotations.columns]
            compact = active_annotations[cols] if cols else active_annotations
            st.dataframe(compact, use_container_width=True, height=450)

            with st.expander("Annotations complete", expanded=False):
                st.dataframe(active_annotations, use_container_width=True, height=550)
        else:
            st.info("Nu există annotations pentru consultația selectată. Verifică dacă pipeline-ul a fost rulat după import și dacă transcriptul conține expresii acoperite de Lexicon.")


    with tabs[3]:
        st.subheader(f"Transcript — {active_dialog_id}")
        if not active_dialogues.empty:
            for _, r in active_dialogues.sort_values("turn_id").iterrows():
                speaker = str(r.get("speaker", "")).upper()
                text_value = str(r.get("text", ""))
                if speaker == "PATIENT":
                    st.markdown(f"**PACIENT:** {text_value}")
                elif speaker == "DOCTOR":
                    st.markdown(f"**MEDIC:** {text_value}")
                else:
                    st.markdown(f"**{speaker}:** {text_value}")

            with st.expander("Tabel Dialogues", expanded=False):
                st.dataframe(active_dialogues, use_container_width=True, height=400)
        else:
            st.info("Nu există transcript pentru consultația selectată.")


    with tabs[4]:
        st.subheader("Load consultation transcript")
        st.markdown("""
    Format acceptat:

    ```text
    CASE: Chest pain case
    DIALOG_ID: DLG_TEST_001

    Doctor: ...
    Patient: ...
    Doctor: ...
    Patient: ...
    ```
    """)

        uploaded = st.file_uploader("Încarcă transcript .txt", type=["txt"])
        manual_text = st.text_area(
            "Sau lipește transcriptul aici",
            height=300,
            placeholder="DIALOG_ID: DLG_TEST_001\n\nDoctor: ...\nPatient: ...",
        )

        custom_dialog_id = st.text_input(
            "Nume dialog (opțional)",
            placeholder="ex: ANAM_URO_CANCER_PROSTATA_001",
            help="Dacă este completat, se folosește acest nume. Altfel se generează automat sau se preia din transcript (DIALOG_ID: ...).",
            key="custom_dialog_id_input",
        )

        replace_existing = st.checkbox("Înlocuiește dialogul dacă dialog_id există deja", value=True)

        if st.button("📥 Load transcript into workbook"):
            try:
                if uploaded is not None:
                    text_value = uploaded.read().decode("utf-8")
                else:
                    text_value = manual_text

                if not text_value.strip():
                    st.warning("Nu există transcript de încărcat.")
                else:
                    dialog_id, case_title, parsed = parse_transcript_text(text_value)

                    # Suprascrie dialog_id cu numele custom dacă e completat
                    if custom_dialog_id.strip():
                        dialog_id = custom_dialog_id.strip()
                        parsed["dialog_id"] = dialog_id

                    if parsed.empty:
                        st.error("Nu am găsit replici Doctor:/Patient:.")
                    else:
                        removed, loaded = append_dialogue_to_workbook(
                            workbook_path=workbook_path,
                            new_dialogue=parsed,
                            dialog_id=dialog_id,
                            case_title=case_title,
                            replace_existing=replace_existing,
                        )

                        st.success(f"Dialog încărcat: {dialog_id} | replici: {loaded} | rânduri vechi eliminate: {removed}")

                        with st.spinner("Rulez analiza NLP pentru noul transcript..."):
                            code, stdout, stderr = run_pipeline_with_sync(pipeline_script, workbook_path, dialog_id)

                        if code == 0:
                            st.success("Analiza NLP a fost rulată automat.")
                            st.session_state["_pending_dialog_id"] = dialog_id
                            load_workbook.clear()
                            st.rerun()
                        else:
                            st.error(f"Pipeline error code: {code}")
                            with st.expander("Pipeline output"):
                                st.code(stdout or "(no stdout)")
                                if stderr:
                                    st.code(stderr)

                        st.dataframe(parsed, use_container_width=True)
            except Exception as exc:
                st.error(str(exc))


    with tabs[5]:
        st.subheader(f"AutoSuggestions — {active_dialog_id}")
        st.caption("Validează sugestiile aici. Setează `ValidationStatus` la `accept` sau `reject`, apoi apasă Save.")

        show_all_auto = st.checkbox("Show all autosuggestions, not only active dialogue", value=False)
        auto_view = autosuggestions if show_all_auto else active_autosuggestions

        if not auto_view.empty:
            editable_cols = [
                "dialog_id",
                "turn_id",
                "utterance",
                "CandidateExpression",
                "AlreadyMatchedCodes",
                "SuggestedCodeElement",
                "SuggestedNatureElement",
                "SuggestedCatalogName",
                "SuggestedElementStandard",
                "SuggestionMethod",
                "SuggestionConfidence",
                "SuggestionReason",
                "ValidationStatus",
                "ProposedElementStandard",
                "ProposedCodeElement",
                "ProposedNatureElement",
                "ProposedCatalogName",
                "SemanticDomain",
            ]
            editable_cols = [c for c in editable_cols if c in auto_view.columns]
            edit_df = auto_view[editable_cols].copy()

            st.markdown("### Validation editor")
            edited = st.data_editor(
                edit_df,
                use_container_width=True,
                height=520,
                num_rows="dynamic",
                column_config={
                    "ValidationStatus": st.column_config.SelectboxColumn(
                        "ValidationStatus",
                        help="Alege accept pentru integrare în Lexicon, reject pentru respingere, suggested pentru nevalidat.",
                        options=["suggested", "accept", "reject", "edit"],
                        required=False,
                    ),
                    "SuggestedCodeElement": st.column_config.TextColumn("SuggestedCodeElement"),
                    "SuggestedNatureElement": st.column_config.SelectboxColumn(
                        "SuggestedNatureElement",
                        options=["Sympt", "Signe", "RiskF", ""],
                        required=False,
                    ),
                    "SuggestedCatalogName": st.column_config.TextColumn("SuggestedCatalogName"),
                    "ProposedCodeElement": st.column_config.TextColumn(
                        "ProposedCodeElement",
                        help="Completează aici dacă modifici sugestia.",
                    ),
                    "ProposedNatureElement": st.column_config.SelectboxColumn(
                        "ProposedNatureElement",
                        options=["", "Sympt", "Signe", "RiskF"],
                        required=False,
                    ),
                    "ProposedCatalogName": st.column_config.TextColumn("ProposedCatalogName"),
                },
                disabled=[
                    c for c in editable_cols
                    if c not in {
                        "ValidationStatus",
                        "ProposedElementStandard",
                        "ProposedCodeElement",
                        "ProposedNatureElement",
                        "ProposedCatalogName",
                        "SemanticDomain",
                    }
                ],
                key=f"autosuggestions_editor_{active_dialog_id}_{show_all_auto}",
            )

            col_save, col_run = st.columns(2)

            with col_save:
                if st.button("💾 Save AutoSuggestions validation"):
                    try:
                        full_auto = autosuggestions.copy()

                        # Preserve all columns and update only displayed rows.
                        key_cols = ["dialog_id", "turn_id", "CandidateExpression", "SuggestedCodeElement"]
                        for c in key_cols:
                            if c not in full_auto.columns:
                                full_auto[c] = ""
                            if c not in edited.columns:
                                edited[c] = ""

                        editable_update_cols = [
                            "ValidationStatus",
                            "ProposedElementStandard",
                            "ProposedCodeElement",
                            "ProposedNatureElement",
                            "ProposedCatalogName",
                            "SemanticDomain",
                        ]

                        for _, erow in edited.iterrows():
                            mask = (
                                (full_auto["dialog_id"].astype(str) == str(erow.get("dialog_id", "")))
                                & (full_auto["turn_id"].astype(str) == str(erow.get("turn_id", "")))
                                & (full_auto["CandidateExpression"].astype(str) == str(erow.get("CandidateExpression", "")))
                                & (full_auto["SuggestedCodeElement"].astype(str) == str(erow.get("SuggestedCodeElement", "")))
                            )

                            for col in editable_update_cols:
                                if col in full_auto.columns and col in edited.columns:
                                    full_auto.loc[mask, col] = erow.get(col, "")

                        save_sheet_to_workbook(workbook_path, "AutoSuggestions", full_auto)
                        st.success("Validările au fost salvate în foaia AutoSuggestions.")
                        st.info("Acum rulează pipeline-ul pentru integrarea rândurilor cu ValidationStatus = accept.")
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Nu am putut salva validările: {exc}")

            with col_run:
                if st.button("▶️ Save + Run pipeline"):
                    st.write( workbook_path, "=Doru")

                    try:
                        full_auto = autosuggestions.copy()
                        key_cols = ["dialog_id", "turn_id", "CandidateExpression", "SuggestedCodeElement"]
                        for c in key_cols:
                            if c not in full_auto.columns:
                                full_auto[c] = ""
                            if c not in edited.columns:
                                edited[c] = ""

                        editable_update_cols = [
                            "ValidationStatus",
                            "ProposedElementStandard",
                            "ProposedCodeElement",
                            "ProposedNatureElement",
                            "ProposedCatalogName",
                            "SemanticDomain",
                        ]

                        for _, erow in edited.iterrows():
                            mask = (
                                (full_auto["dialog_id"].astype(str) == str(erow.get("dialog_id", "")))
                                & (full_auto["turn_id"].astype(str) == str(erow.get("turn_id", "")))
                                & (full_auto["CandidateExpression"].astype(str) == str(erow.get("CandidateExpression", "")))
                                & (full_auto["SuggestedCodeElement"].astype(str) == str(erow.get("SuggestedCodeElement", "")))
                            )

                            for col in editable_update_cols:
                                if col in full_auto.columns and col in edited.columns:
                                    full_auto.loc[mask, col] = erow.get(col, "")

                        save_sheet_to_workbook(workbook_path, "AutoSuggestions", full_auto)

                        with st.spinner("Rulez pipeline-ul după validare..."):
                            code, stdout, stderr = run_pipeline_with_sync(pipeline_script, workbook_path, st.session_state.get('active_dialog_id', ''))

                        if code == 0:
                            st.success("Pipeline rulat. Sugestiile acceptate au fost integrate în Lexicon.")
                            load_workbook.clear()
                            st.rerun()
                        else:
                            st.error(f"Pipeline error code: {code}")
                            with st.expander("Pipeline output"):
                                st.code(stdout or "(no stdout)")
                                if stderr:
                                    st.code(stderr)

                    except Exception as exc:
                        st.error(f"Eroare la Save + Run: {exc}")

            with st.expander("AutoSuggestions complet", expanded=False):
                st.dataframe(auto_view, use_container_width=True, height=550)

            dataframe_download_button(
                auto_view,
                f"NlpRO_AutoSuggestions_{active_dialog_id if not show_all_auto else 'ALL'}.xlsx",
                "Download displayed AutoSuggestions as Excel",
            )
        else:
            st.info("Nu există autosuggestions pentru consultația selectată.")


    with tabs[6]:
        st.subheader(f"Unmatched — {active_dialog_id}")
        st.markdown("Completează în Excel: `CandidateExpression`, `ProposedCodeElement`, `ProposedNatureElement`, `ProposedCatalogName`.")

        show_all_unmatched = st.checkbox("Show all unmatched, not only active dialogue", value=False)
        unmatched_view = unmatched if show_all_unmatched else active_unmatched

        st.dataframe(unmatched_view, use_container_width=True, height=550)
        if not unmatched_view.empty:
            dataframe_download_button(
                unmatched_view,
                f"NlpRO_Unmatched_{active_dialog_id if not show_all_unmatched else 'ALL'}.xlsx",
                "Download displayed Unmatched as Excel",
            )


    with tabs[7]:
        st.subheader("Lexicon")
        if not lexicon.empty:
            search = st.text_input("Search lexicon", "")
            view = lexicon
            if search.strip():
                mask = view.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
                view = view[mask]
            st.dataframe(view, use_container_width=True, height=550)
        else:
            st.info("No lexicon.")



    with tabs[8]:
        st.subheader("Correct Lexicon")
        st.caption("Corectează un termen deja validat și intrat în Lexicon. Modificarea afectează rulările viitoare.")

        if not lexicon.empty:
            search_term = st.text_input("Caută expresie / cod / nume", "", key="lexicon_correction_search")

            lex_view = lexicon.copy()
            if search_term.strip():
                mask = lex_view.astype(str).apply(
                    lambda col: col.str.contains(search_term, case=False, na=False)
                ).any(axis=1)
                lex_view = lex_view[mask]

            editable_cols = [
                "ExprID",
                "ExpresiePacient",
                "CodeElement",
                "Nature Element",
                "TypeElement",
                "CatalogName",
                "ElementStandard",
                "SemanticDomain",
                "puternicitate",
                "Polaritate",
                "ReviewStatus",
                "ReviewerNote",
            ]
            editable_cols = [c for c in editable_cols if c in lex_view.columns]

            edited_lex = st.data_editor(
                lex_view[editable_cols],
                use_container_width=True,
                height=520,
                num_rows="dynamic",
                disabled=[c for c in editable_cols if c == "ExprID"],
                key="lexicon_correction_editor",
            )

            def _apply_lexicon_editor_changes(full_lex, edited):
                """
                Save edits from Correct Lexicon.

                Existing rows are updated by ExprID.
                New rows inserted in st.data_editor have empty ExprID and are appended.
                """
                full_lex = full_lex.copy().fillna("")
                edited = edited.copy().fillna("")

                if "ExprID" not in full_lex.columns:
                    full_lex["ExprID"] = ""

                for col in edited.columns:
                    if col not in full_lex.columns:
                        full_lex[col] = ""

                existing_ids = []
                for v in full_lex["ExprID"].astype(str).tolist():
                    try:
                        s = str(v).strip()
                        if s:
                            existing_ids.append(int(float(s)))
                    except Exception:
                        pass

                next_id = max(existing_ids) + 1 if existing_ids else 1
                new_rows = []

                for _, erow in edited.iterrows():
                    expr_id = str(erow.get("ExprID", "")).strip()

                    non_id_values = [
                        str(erow.get(col, "")).strip()
                        for col in edited.columns
                        if col != "ExprID"
                    ]

                    if not any(non_id_values):
                        continue

                    if expr_id:
                        mask = full_lex["ExprID"].astype(str) == expr_id

                        if mask.any():
                            for col in edited.columns:
                                if col in full_lex.columns and col != "ExprID":
                                    full_lex.loc[mask, col] = erow.get(col, "")
                        else:
                            new_row = {col: "" for col in full_lex.columns}
                            new_row["ExprID"] = expr_id
                            for col in edited.columns:
                                if col in full_lex.columns and col != "ExprID":
                                    new_row[col] = erow.get(col, "")
                            new_rows.append(new_row)
                    else:
                        new_row = {col: "" for col in full_lex.columns}
                        new_row["ExprID"] = str(next_id)
                        next_id += 1

                        for col in edited.columns:
                            if col in full_lex.columns and col != "ExprID":
                                new_row[col] = erow.get(col, "")

                        if "Polaritate" in full_lex.columns and not str(new_row.get("Polaritate", "")).strip():
                            new_row["Polaritate"] = "prezent"
                        if "puternicitate" in full_lex.columns and not str(new_row.get("puternicitate", "")).strip():
                            new_row["puternicitate"] = "moderat"
                        if "ReviewStatus" in full_lex.columns and not str(new_row.get("ReviewStatus", "")).strip():
                            new_row["ReviewStatus"] = "ManualLexiconInsert"
                        if "ReviewerNote" in full_lex.columns and not str(new_row.get("ReviewerNote", "")).strip():
                            new_row["ReviewerNote"] = "MAPPING_NOTE: Manually inserted in Correct Lexicon."
                        if "SourceSheets" in full_lex.columns and not str(new_row.get("SourceSheets", "")).strip():
                            new_row["SourceSheets"] = "CorrectLexicon"
                        if "Tags" in full_lex.columns and not str(new_row.get("Tags", "")).strip():
                            new_row["Tags"] = "manual_lexicon_insert"
                        if "TypeElement" in full_lex.columns and not str(new_row.get("TypeElement", "")).strip():
                            new_row["TypeElement"] = str(new_row.get("Nature Element", "")).strip()

                        new_rows.append(new_row)

                if new_rows:
                    full_lex = pd.concat([full_lex, pd.DataFrame(new_rows)], ignore_index=True)

                return full_lex


            c_save, c_run = st.columns(2)

            with c_save:
                if st.button("💾 Save Lexicon corrections"):
                    try:
                        t0 = time.perf_counter()
                        patch_rows = build_lexicon_patch_rows(lexicon, edited_lex)
                        patch_path = append_lexicon_patch(workbook_path, patch_rows)
                        t1 = time.perf_counter()

                        if patch_rows:
                            st.success(f"LexiconPatch salvat rapid: {len(patch_rows)} modificări → {patch_path.name} ({t1 - t0:.2f}s)")
                            st.info("Nu am rulat pipeline-ul. Apasă «Save Lexicon + Run pipeline» când vrei recalcul pe dialogul activ.")
                        else:
                            st.info("Nu există modificări noi de salvat.")
                    except Exception as exc:
                        st.error(f"Eroare la salvarea LexiconPatch: {exc}")

            with c_run:
                if st.button("▶️ Save Lexicon + Run pipeline"):
                    try:
                        updated_lex = _apply_lexicon_editor_changes(lexicon, edited_lex)
                        save_sheet_to_workbook(workbook_path, "Lexicon", updated_lex)

                        with st.spinner("Rulez pipeline-ul după corecția Lexicon..."):
                            code, stdout, stderr = run_pipeline_with_sync(pipeline_script, workbook_path, st.session_state.get('active_dialog_id', ''))

                        if code == 0:
                            st.success("Pipeline rulat după corecția Lexicon.")
                            load_workbook.clear()
                            st.rerun()
                        else:
                            st.error(f"Pipeline error code: {code}")
                            with st.expander("Pipeline output"):
                                st.code(stdout or "(no stdout)")
                                if stderr:
                                    st.code(stderr)
                    except Exception as exc:
                        st.error(f"Eroare la Save + Run: {exc}")
        else:
            st.info("Lexicon gol sau neîncărcat.")


    with tabs[9]:
        st.subheader("Advanced")

        st.markdown("### PatientVectors")
        st.dataframe(active_patient_vectors, use_container_width=True, height=300)

        st.markdown("### Summary")
        st.dataframe(summary, use_container_width=True, height=250)

        st.markdown("### Downloads")

        if workbook_path.exists():
            st.download_button(
                label="Download current workbook",
                data=workbook_path.read_bytes(),
                file_name=workbook_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        if pipeline_script.exists():
            st.download_button(
                label="Download pipeline script",
                data=pipeline_script.read_bytes(),
                file_name=pipeline_script.name,
                mime="text/x-python",
            )



if __name__ == "__main__":
    render_main_page()