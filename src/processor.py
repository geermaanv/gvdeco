"""
processor.py
Envía cada foto a Claude Vision y extrae los campos técnicos de herrería
con el schema exacto del Google Sheet de Déco Porteño.
"""

import os
import json
import base64
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

CERT_RANK = {"alto": 3, "medio": 2, "bajo": 1}

VISION_PROMPT = (
    "Analizá esta imagen de una puerta o elemento arquitectónico Art Déco en Buenos Aires. "
    "Completá los siguientes campos con el valor más probable y un nivel de certeza "
    "(alto/medio/bajo): Material, Estado, Motivo, Año estimado del edificio, Color/acabado, "
    "Herraje, Notas técnicas relevantes para herrería. Respondé solo en JSON.\n\n"
    "Además evaluá si el elemento sirve como referencia técnica para fabricación de herrería "
    "(Ref. herrería: sí/no). Devolvé EXCLUSIVAMENTE un objeto JSON, sin texto adicional ni "
    "bloques de código, con esta forma exacta:\n"
    '{"material":{"valor":"hierro forjado|chapa doblada|aluminio|madera+hierro|bronce","certeza":"alto|medio|bajo"},'
    '"estado":{"valor":"original|restaurado|deteriorado|modificado","certeza":"alto|medio|bajo"},'
    '"motivo":{"valor":"bandas horiz.|geométrico|mixto|floral|sin ornamento","certeza":"alto|medio|bajo"},'
    '"anio_edificio":{"valor":"<año o década estimada>","certeza":"alto|medio|bajo"},'
    '"color_acabado":{"valor":"negro|crema|bronce|grafito|oxidado natural","certeza":"alto|medio|bajo"},'
    '"herraje":{"valor":"manija circular|barra horiz.|tirador vertical|sin herraje visible","certeza":"alto|medio|bajo"},'
    '"ref_herreria":{"valor":"sí|no","certeza":"alto|medio|bajo"},'
    '"notas":"<notas técnicas breves>"}'
)


def analyze_image(image_bytes: bytes, media_type: str) -> dict | None:
    raw = ""
    try:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }],
        )
        raw = response.content[0].text.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[processor] Error JSON: {e} | raw: '{raw[:200]}'")
        return None
    except Exception as e:
        print(f"[processor] Error analizando imagen: {e}")
        return None


def _merge_field(analyses: list[dict], key: str) -> dict:
    best = None
    for a in analyses:
        field = a.get(key) or {}
        valor = field.get("valor")
        if not valor:
            continue
        rank = CERT_RANK.get((field.get("certeza") or "").lower(), 0)
        if best is None or rank > best["rank"]:
            best = {"valor": valor, "certeza": field.get("certeza", "bajo"), "rank": rank}
    return {"valor": best["valor"], "certeza": best["certeza"]} if best else {"valor": "", "certeza": ""}


def merge_analyses(analyses: list[dict]) -> dict:
    keys = ["material", "estado", "motivo", "anio_edificio", "color_acabado", "herraje", "ref_herreria"]
    merged = {k: _merge_field(analyses, k) for k in keys}
    notas = list(dict.fromkeys(a.get("notas") for a in analyses if a.get("notas")))
    merged["notas"] = " | ".join(notas)
    return merged


def overall_certainty(merged: dict) -> str:
    keys = ["material", "estado", "motivo", "anio_edificio", "color_acabado", "herraje"]
    ranks = [r for r in (CERT_RANK.get((merged[k]["certeza"] or "").lower(), 0) for k in keys) if r]
    if not ranks:
        return ""
    avg = sum(ranks) / len(ranks)
    return "alto" if avg >= 2.5 else "medio" if avg >= 1.5 else "bajo"
