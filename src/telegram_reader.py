"""
telegram_reader.py
Lee fotos + dirección mandadas al bot de Telegram, agrupa álbumes
(media_group_id) en una sola ficha y confirma los updates leídos.

No hace falta OAuth ni service account: alcanza con el token del bot.
Los updates ya leídos (offset confirmado) no vuelven a aparecer — Telegram
lleva el estado de "procesado" del lado del servidor, así que no hace
falta ningún archivo/label propio para deduplicar.
"""

import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_URL = f"https://api.telegram.org/file/bot{BOT_TOKEN}"


def _call(method: str, **params) -> dict:
    resp = requests.get(f"{API_URL}/{method}", params=params, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error en {method}: {data}")
    return data["result"]


def fetch_new_groups() -> tuple[list[dict], int | None]:
    """Devuelve (grupos, last_update_id).

    Cada grupo: {chat_id, from, date, address, file_ids: [...]}.
    Agrupa por media_group_id para que un álbum de varias fotos con un
    solo caption se procese como una sola ficha.
    """
    updates = _call("getUpdates", timeout=0)
    if not updates:
        return [], None

    groups: dict[str, dict] = {}
    order: list[str] = []

    for upd in updates:
        msg = upd.get("message")
        if not msg or "photo" not in msg:
            continue

        chat_id = str(msg["chat"]["id"])
        if ALLOWED_CHAT_ID and chat_id != str(ALLOWED_CHAT_ID):
            continue

        key = msg.get("media_group_id") or f"single-{msg['message_id']}"
        largest_photo = max(msg["photo"], key=lambda p: p.get("file_size") or p["width"] * p["height"])

        group = groups.setdefault(key, {
            "chat_id": chat_id,
            "from": msg["from"].get("username") or msg["from"].get("first_name", ""),
            "date": msg["date"],
            "address": "",
            "file_ids": [],
        })
        group["file_ids"].append(largest_photo["file_id"])
        if msg.get("caption") and not group["address"]:
            group["address"] = msg["caption"].strip()

        order.append(key)

    ordered_groups = [groups[k] for k in dict.fromkeys(order)]
    last_update_id = updates[-1]["update_id"]
    return ordered_groups, last_update_id


def acknowledge(last_update_id: int):
    """Confirma los updates hasta last_update_id para que no vuelvan a aparecer."""
    _call("getUpdates", offset=last_update_id + 1, timeout=0)


def download_photo(file_id: str) -> bytes:
    file_info = _call("getFile", file_id=file_id)
    resp = requests.get(f"{FILE_URL}/{file_info['file_path']}", timeout=30)
    resp.raise_for_status()
    return resp.content


def send_message(chat_id: str, text: str):
    try:
        _call("sendMessage", chat_id=chat_id, text=text)
    except Exception as e:
        print(f"[telegram] No se pudo responder a {chat_id}: {e}")
