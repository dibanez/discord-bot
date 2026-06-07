"""Subida de transcripciones y audio a Google Drive.

Reutiliza la cuenta de servicio ya configurada para Google Sheets
(``GOOGLE_CREDENTIALS_PATH``) para crear, si no existe, la jerarquía de carpetas
``anfaia/recordings`` en el Drive de la cuenta de servicio y subir ahí los
ficheros.

Importante: una cuenta de servicio sube a SU PROPIO Drive (no al de una
persona). Por eso la carpeta raíz (``anfaia``) se comparte automáticamente con
el email de ``DRIVE_SHARE_WITH`` para que sea visible en "Compartidos conmigo".

Todas las funciones públicas son tolerantes a fallos: si Drive no está
disponible o falla, registran el error y devuelven lo que se pudo subir, pero
NUNCA lanzan excepción, para no romper el guardado local ni la grabación.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import threading

_log = logging.getLogger(__name__)


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "si", "sí")


DRIVE_UPLOAD_ENABLED = _flag("DRIVE_UPLOAD_ENABLED", "true")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
DRIVE_SHARE_WITH = os.getenv("DRIVE_SHARE_WITH", "").strip()
# Rol con el que se comparte la carpeta raíz: "reader" (ver/descargar) o "writer".
DRIVE_SHARE_ROLE = os.getenv("DRIVE_SHARE_ROLE", "reader").strip() or "reader"
# Jerarquía de carpetas en Drive (de la raíz hacia dentro).
DRIVE_FOLDER_PATH = [
    p for p in os.getenv("DRIVE_FOLDER_PATH", "anfaia/recordings").split("/") if p.strip()
]

_SCOPES = ["https://www.googleapis.com/auth/drive"]
_FOLDER_MIME = "application/vnd.google-apps.folder"

_service = None
_folder_id = None
_lock = threading.Lock()


def _build_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _escape(name: str) -> str:
    # Escapar para la sintaxis de query de la API de Drive.
    return name.replace("\\", "\\\\").replace("'", "\\'")


def _find_folder(service, name: str, parent_id: str):
    q = (
        f"name = '{_escape(name)}' and mimeType = '{_FOLDER_MIME}' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    res = (
        service.files()
        .list(q=q, spaces="drive", fields="files(id, name)", pageSize=1)
        .execute()
    )
    files = res.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: str) -> str:
    meta = {"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]}
    return service.files().create(body=meta, fields="id").execute()["id"]


def _share_folder(service, folder_id: str, email: str) -> None:
    try:
        service.permissions().create(
            fileId=folder_id,
            body={"type": "user", "role": DRIVE_SHARE_ROLE, "emailAddress": email},
            sendNotificationEmail=False,
            fields="id",
        ).execute()
        _log.info("Carpeta de Drive %s compartida con %s (%s)", folder_id, email, DRIVE_SHARE_ROLE)
    except Exception:
        _log.warning("No se pudo compartir la carpeta de Drive con %s", email, exc_info=True)


def _ensure_folder(service) -> str:
    """Encuentra o crea la jerarquía DRIVE_FOLDER_PATH; devuelve el id de la última carpeta."""
    parent = "root"
    for depth, name in enumerate(DRIVE_FOLDER_PATH):
        existing = _find_folder(service, name, parent)
        if existing:
            parent = existing
            continue
        created = _create_folder(service, name, parent)
        # Compartir solo la carpeta raíz recién creada (la primera del path).
        if depth == 0 and DRIVE_SHARE_WITH:
            _share_folder(service, created, DRIVE_SHARE_WITH)
        parent = created
    return parent


def _upload_one(service, folder_id: str, local_path: str) -> str:
    from googleapiclient.http import MediaFileUpload

    mime = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)
    meta = {"name": os.path.basename(local_path), "parents": [folder_id]}
    f = (
        service.files()
        .create(body=meta, media_body=media, fields="id, webViewLink")
        .execute()
    )
    return f.get("webViewLink") or f"https://drive.google.com/file/d/{f.get('id')}"


def upload_files(paths) -> dict:
    """Sube los ficheros indicados a la carpeta de Drive (síncrono, bloqueante).

    Pensado para llamarse desde código async con ``asyncio.to_thread``.

    Devuelve ``{nombre_fichero: enlace}`` con los que se subieron bien. Tolerante
    a fallos: ante cualquier error registra y devuelve lo conseguido, sin lanzar.
    """
    if not DRIVE_UPLOAD_ENABLED:
        return {}

    paths = [p for p in (paths or []) if p and os.path.exists(p)]
    if not paths:
        return {}

    global _service, _folder_id
    links: dict = {}
    try:
        with _lock:
            if _service is None:
                _service = _build_service()
            if _folder_id is None:
                _folder_id = _ensure_folder(_service)
            for p in paths:
                try:
                    links[os.path.basename(p)] = _upload_one(_service, _folder_id, p)
                except Exception:
                    _log.exception("Error subiendo %s a Drive", p)
    except Exception:
        _log.exception("Error inicializando la subida a Drive")
    return links
