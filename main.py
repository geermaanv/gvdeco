"""
main.py — Déco Porteño pipeline
Telegram (bot @geermaanv_bot, fotos con la dirección como descripción)
    → Claude Vision → Geocoding → Google Sheets → confirmación al chat
"""

import sys
from datetime import datetime, timezone

from src.telegram_reader import fetch_new_groups, acknowledge, download_photo, send_message
from src.processor import analyze_image, merge_analyses, overall_certainty
from src.geocode import geocode_address
from src.sheets import get_service as sheets_service, ensure_header, append_row


def run():
    print("=== Déco Porteño — pipeline ===\n")

    sheets = sheets_service()
    ensure_header(sheets)

    groups, last_update_id = fetch_new_groups()
    print(f"[1/2] {len(groups)} ficha(s) nueva(s)\n")
    if not groups:
        print("Sin mensajes nuevos. Pipeline finalizado.")
        return 0

    inserted = 0
    for group in groups:
        if not group["address"]:
            print(f"[main] chat {group['chat_id']}: sin dirección (descripción) en las fotos, se omite")
            send_message(group["chat_id"], "⚠️ No encontré la dirección — mandá las fotos con la dirección como descripción (caption) del mensaje.")
            continue

        analyses = []
        for file_id in group["file_ids"]:
            data = download_photo(file_id)
            result = analyze_image(data, "image/jpeg")
            if result:
                analyses.append(result)

        if not analyses:
            print(f"[main] {group['address']}: Claude Vision no devolvió resultados válidos, se omite")
            send_message(group["chat_id"], f"⚠️ No pude analizar las fotos de «{group['address']}». Probá de nuevo.")
            continue

        merged = merge_analyses(analyses)
        geo = geocode_address(group["address"])
        fecha = datetime.fromtimestamp(group["date"], tz=timezone.utc).date().isoformat()

        row = [
            fecha, group["address"], geo["barrio"], geo["lat"], geo["lng"],
            merged["material"]["valor"], merged["estado"]["valor"], merged["motivo"]["valor"],
            merged["anio_edificio"]["valor"], merged["color_acabado"]["valor"], merged["herraje"]["valor"],
            merged["ref_herreria"]["valor"], overall_certainty(merged), merged["notas"], group["from"],
        ]

        append_row(sheets, row)
        inserted += 1
        print(f"[main] ✓ {group['address']} — fila agregada")
        send_message(
            group["chat_id"],
            f"✅ Ficha creada: {group['address']}\n"
            f"Material: {merged['material']['valor']} · Estado: {merged['estado']['valor']} · "
            f"Herraje: {merged['herraje']['valor']} · Certeza: {overall_certainty(merged)}",
        )

    if last_update_id is not None:
        acknowledge(last_update_id)

    print(f"\n[2/2] {inserted} fila(s) nueva(s) en el Sheet")
    print("=== Pipeline completado ===")
    return inserted


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result is not None else 1)
