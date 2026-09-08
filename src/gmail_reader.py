"""
gmail_reader.py
Busca emails con la palabra clave en el asunto, extrae la dirección del
cuerpo y las fotos adjuntas, y marca los procesados con una etiqueta.

Autenticación: OAuth de usuario con refresh token de larga duración
(un service account no puede leer una casilla de Gmail personal).
Ver scripts/get_gmail_refresh_token.py para obtenerlo una sola vez.
"""

import os
import base64
from email.utils import parsedate_to_datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
LABEL_NAME = "gvdeco-procesado"
KEYWORD = os.environ.get("GMAIL_SUBJECT_KEYWORD", "gvdeco")


def get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


def ensure_label(service) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == LABEL_NAME:
            return label["id"]
    created = (
        service.users().labels()
        .create(userId="me", body={
            "name": LABEL_NAME,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        })
        .execute()
    )
    print(f"[gmail] Etiqueta '{LABEL_NAME}' creada")
    return created["id"]


def fetch_new_messages(service, max_results: int = 50) -> list[dict]:
    query = f"subject:{KEYWORD} -label:{LABEL_NAME} has:attachment"
    resp = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    return resp.get("messages", [])


def get_message(service, message_id: str) -> dict:
    return service.users().messages().get(userId="me", id=message_id, format="full").execute()


def get_attachment_bytes(service, message_id: str, attachment_id: str) -> bytes:
    att = (
        service.users().messages().attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    return base64.urlsafe_b64decode(att["data"] + "=" * (-len(att["data"]) % 4))


def mark_processed(service, message_id: str, label_id: str):
    service.users().messages().modify(
        userId="me", id=message_id, body={"addLabelIds": [label_id]}
    ).execute()


def _b64url_decode_text(data: str) -> str:
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _walk_parts(part: dict, plain: list, images: list):
    if not part:
        return
    mime = part.get("mimeType", "")
    body = part.get("body", {})
    if mime == "text/plain" and body.get("data"):
        plain.append(_b64url_decode_text(body["data"]))
    elif mime.startswith("image/") and body.get("attachmentId"):
        images.append({"mimeType": mime, "attachmentId": body["attachmentId"]})
    for sub in part.get("parts", []) or []:
        _walk_parts(sub, plain, images)


def extract_message(msg: dict) -> dict:
    plain, images = [], []
    _walk_parts(msg["payload"], plain, images)
    headers = msg["payload"].get("headers", [])

    body_text = "\n".join(plain).strip()
    address = next((line.strip() for line in body_text.splitlines() if line.strip()), "")

    date_header = _get_header(headers, "Date")
    try:
        fecha = parsedate_to_datetime(date_header).date().isoformat()
    except Exception:
        fecha = ""

    return {
        "id": msg["id"],
        "from": _get_header(headers, "From"),
        "fecha": fecha,
        "address": address,
        "images": images,
    }
