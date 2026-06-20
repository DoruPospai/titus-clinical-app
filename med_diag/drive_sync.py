"""
drive_sync.py — TITUS
Sincronizare workbook-uri Excel cu Google Drive, via Service Account.

Flux:
  - La pornirea aplicației: download din Drive -> disc local (ROOT)
  - După rularea pipeline-ului (NlpRO.py run_pipeline): upload disc local -> Drive

Configurare necesară în .streamlit/secrets.toml (local) sau Secrets UI (Streamlit Cloud):

    [gdrive]
    folder_id = "1aiZsoxrDOWnc_YoplZqlcT7SYePLTR3B"

    [gdrive.service_account]
    type = "service_account"
    project_id = "titus-clinical-app"
    private_key_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
    client_email = "titus-drive-access@titus-clinical-app.iam.gserviceaccount.com"
    client_id = "..."
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"

(Conținutul exact se copiază din fișierul .json descărcat la crearea cheii.)
"""

import io
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Fișierele sincronizate cu Drive — lista unică sursă de adevăr pentru sync.
SYNCED_FILES = [
    "ClinicalPipeline_RO_SINGLE_v14_RUNTIME_AUDIT.xlsx",
    "data_clean/Tabel2_Titus.xlsx",
    "data_clean/Maladies.xlsx",
    "data_clean/Signe.xlsx",
    "data_clean/Symptomes.xlsx",
    "data_clean/Riskf.xlsx",
    "data_clean/catriskf.xlsx",
    "data_clean/Order_AgeMetadata_FINAL.xlsx",
]


def _get_drive_service():
    """
    Construiește clientul Google Drive API din service account.
    Citește credențialele din st.secrets — funcționează identic local
    (.streamlit/secrets.toml) și pe Streamlit Cloud (Secrets UI).
    """
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_info = dict(st.secrets["gdrive"]["service_account"])
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_file_id(service, folder_id: str, filename: str) -> Optional[str]:
    """Caută un fișier după nume în folderul Drive dat. Returnează file_id sau None."""
    query = (
        f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
    )
    results = service.files().list(
        q=query, fields="files(id, name, modifiedTime)", pageSize=1
    ).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def download_all(root: Path, folder_id: Optional[str] = None) -> dict:
    """
    Descarcă toate fișierele din SYNCED_FILES de pe Drive -> disc local (root).
    Apelată o singură dată, la pornirea aplicației.

    Returnează dict {filename: "ok" | "missing_on_drive" | "error: <msg>"}.
    Fișierele care nu există pe Drive sunt sărite (nu blochează pornirea —
    pot fi create local de pipeline la prima rulare și încărcate ulterior).
    """
    import streamlit as st
    from googleapiclient.http import MediaIoBaseDownload

    if folder_id is None:
        folder_id = st.secrets["gdrive"]["folder_id"]

    status = {}
    try:
        service = _get_drive_service()
    except Exception as exc:
        logger.error(f"drive_sync: nu pot crea serviciul Drive — {exc}")
        for f in SYNCED_FILES:
            status[f] = f"error: {exc}"
        return status

    for rel_path in SYNCED_FILES:
        filename = Path(rel_path).name
        local_path = root / rel_path
        try:
            file_id = _find_file_id(service, folder_id, filename)
            if file_id is None:
                status[rel_path] = "missing_on_drive"
                continue

            local_path.parent.mkdir(parents=True, exist_ok=True)
            request = service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            local_path.write_bytes(buffer.getvalue())
            status[rel_path] = "ok"
            logger.info(f"drive_sync: descărcat {filename}")
        except Exception as exc:
            status[rel_path] = f"error: {exc}"
            logger.error(f"drive_sync: eroare descărcare {filename} — {exc}")

    return status


def upload_all(root: Path, folder_id: Optional[str] = None) -> dict:
    """
    Încarcă toate fișierele din SYNCED_FILES de pe disc local -> Drive,
    suprascriind versiunea existentă (sau creând una nouă dacă nu există).
    Apelată după rularea pipeline-ului (run_pipeline din NlpRO.py).

    Returnează dict {filename: "ok" | "missing_local" | "error: <msg>"}.
    """
    import streamlit as st
    from googleapiclient.http import MediaFileUpload

    if folder_id is None:
        folder_id = st.secrets["gdrive"]["folder_id"]

    status = {}
    try:
        service = _get_drive_service()
    except Exception as exc:
        logger.error(f"drive_sync: nu pot crea serviciul Drive — {exc}")
        for f in SYNCED_FILES:
            status[f] = f"error: {exc}"
        return status

    for rel_path in SYNCED_FILES:
        filename = Path(rel_path).name
        local_path = root / rel_path
        if not local_path.exists():
            status[rel_path] = "missing_local"
            continue

        try:
            media = MediaFileUpload(
                str(local_path),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                resumable=False,
            )
            file_id = _find_file_id(service, folder_id, filename)
            if file_id:
                service.files().update(fileId=file_id, media_body=media).execute()
            else:
                metadata = {"name": filename, "parents": [folder_id]}
                service.files().create(body=metadata, media_body=media).execute()
            status[rel_path] = "ok"
            logger.info(f"drive_sync: încărcat {filename}")
        except Exception as exc:
            status[rel_path] = f"error: {exc}"
            logger.error(f"drive_sync: eroare încărcare {filename} — {exc}")

    return status
