"""
sheets.py
Escribe las fichas en Google Sheets con el schema de Déco Porteño.
Columnas: Fecha, Dirección, Barrio, Lat, Long, Material, Estado, Motivo,
          Año edif., Color/acabado, Herraje, Ref. herrería, Certeza, Notas,
          Email origen.
"""

import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM")

HEADER = [
    "Fecha", "Dirección", "Barrio", "Lat", "Long", "Material", "Estado", "Motivo",
    "Año edif.", "Color/acabado", "Herraje", "Ref. herrería", "Certeza", "Notas", "Origen (Telegram)",
]

_sheet_title_cache = None


def get_service():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _sheet_title(service) -> str:
    global _sheet_title_cache
    if _sheet_title_cache is None:
        meta = service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID, fields="sheets.properties.title"
        ).execute()
        _sheet_title_cache = meta["sheets"][0]["properties"]["title"]
    return _sheet_title_cache


def ensure_header(service):
    title = _sheet_title(service)
    result = (
        service.spreadsheets().values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"{title}!1:1")
        .execute()
    )
    if not result.get("values"):
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [HEADER]},
        ).execute()
        print("[sheets] Header creado")


def append_row(service, row: list):
    title = _sheet_title(service)
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{title}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
