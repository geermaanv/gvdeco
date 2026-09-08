"""
geocode.py
Geocodifica la dirección con la Geocoding API de Google. Llamada
servidor-a-servidor (requests), sin las restricciones de CORS que tiene
el mismo endpoint llamado desde un navegador.
"""

import os
import requests

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NEIGHBORHOOD_TYPES = ("sublocality_level_1", "sublocality", "neighborhood")


def geocode_address(address: str) -> dict:
    params = {
        "address": f"{address}, Ciudad Autónoma de Buenos Aires, Argentina",
        "key": os.environ["MAPS_API_KEY"],
    }
    try:
        resp = requests.get(GEOCODE_URL, params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"[geocode] Error de red: {e}")
        return {"lat": "", "lng": "", "barrio": ""}

    if data.get("status") != "OK" or not data.get("results"):
        print(f"[geocode] Sin resultado para '{address}' ({data.get('status')})")
        return {"lat": "", "lng": "", "barrio": ""}

    result = data["results"][0]
    location = result["geometry"]["location"]
    return {
        "lat": location["lat"],
        "lng": location["lng"],
        "barrio": _pick_barrio(result.get("address_components", [])),
    }


def _pick_barrio(components: list[dict]) -> str:
    for wanted in NEIGHBORHOOD_TYPES:
        for c in components:
            if wanted in c.get("types", []):
                return c["long_name"]
    return ""
