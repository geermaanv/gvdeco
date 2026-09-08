"""
main.py — Déco Porteño pipeline
Gmail (asunto "gvdeco" + fotos adjuntas + dirección en el cuerpo)
    → Claude Vision → Geocoding → Google Sheets → etiqueta "gvdeco-procesado"
"""

import sys

from src.gmail_reader import (
    get_service as gmail_service,
    ensure_label,
    fetch_new_messages,
    get_message,
    get_attachment_bytes,
    extract_message,
    mark_processed,
)
from src.processor import analyze_image, merge_analyses, overall_certainty
from src.geocode import geocode_address
from src.sheets import get_service as sheets_service, ensure_header, append_row


def run():
    print("=== Déco Porteño — pipeline ===\n")

    gmail = gmail_service()
    label_id = ensure_label(gmail)
    sheets = sheets_service()
    ensure_header(sheets)

    messages = fetch_new_messages(gmail)
    print(f"[1/2] {len(messages)} email(s) nuevo(s)\n")
    if not messages:
        print("Sin emails nuevos. Pipeline finalizado.")
        return 0

    inserted = 0
    for meta in messages:
        parsed = extract_message(get_message(gmail, meta["id"]))

        if not parsed["address"]:
            print(f"[main] {parsed['id']}: sin dirección en el cuerpo, se omite")
            continue
        if not parsed["images"]:
            print(f"[main] {parsed['id']}: sin fotos adjuntas, se omite")
            continue

        analyses = []
        for img in parsed["images"]:
            data = get_attachment_bytes(gmail, parsed["id"], img["attachmentId"])
            result = analyze_image(data, img["mimeType"])
            if result:
                analyses.append(result)

        if not analyses:
            print(f"[main] {parsed['id']}: Claude Vision no devolvió resultados válidos, se omite")
            continue

        merged = merge_analyses(analyses)
        geo = geocode_address(parsed["address"])

        row = [
            parsed["fecha"], parsed["address"], geo["barrio"], geo["lat"], geo["lng"],
            merged["material"]["valor"], merged["estado"]["valor"], merged["motivo"]["valor"],
            merged["anio_edificio"]["valor"], merged["color_acabado"]["valor"], merged["herraje"]["valor"],
            merged["ref_herreria"]["valor"], overall_certainty(merged), merged["notas"], parsed["from"],
        ]

        append_row(sheets, row)
        mark_processed(gmail, parsed["id"], label_id)
        inserted += 1
        print(f"[main] ✓ {parsed['address']} — fila agregada")

    print(f"\n[2/2] {inserted} fila(s) nueva(s) en el Sheet")
    print("=== Pipeline completado ===")
    return inserted


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result is not None else 1)
