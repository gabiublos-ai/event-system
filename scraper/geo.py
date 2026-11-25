"""Coordenadas (lat/lon) das cidades dos eventos, para o mapa do site.

1. Capitais e polos conhecidos vêm desta tabela (sem consulta externa).
2. As demais cidades são consultadas no Nominatim (OpenStreetMap), 1 por segundo,
   e guardadas em data/geocache.json — cada cidade é consultada uma única vez.
3. Se não achar a cidade, o evento vai para a capital do estado.
"""
from __future__ import annotations

import json
import logging
import time

import requests

from scraper.core import DATA_DIR, norm

log = logging.getLogger("scraper")
CACHE_FILE = DATA_DIR / "geocache.json"

CAPITALS = {
    "AC": (-9.975, -67.810), "AL": (-9.665, -35.735), "AP": (0.035, -51.070), "AM": (-3.119, -60.022),
    "BA": (-12.971, -38.511), "CE": (-3.732, -38.527), "DF": (-15.794, -47.882), "ES": (-20.315, -40.312),
    "GO": (-16.686, -49.264), "MA": (-2.530, -44.303), "MT": (-15.601, -56.097), "MS": (-20.469, -54.620),
    "MG": (-19.917, -43.934), "PA": (-1.456, -48.490), "PB": (-7.119, -34.845), "PR": (-25.429, -49.271),
    "PE": (-8.054, -34.881), "PI": (-5.089, -42.802), "RJ": (-22.907, -43.173), "RN": (-5.795, -35.209),
    "RS": (-30.035, -51.218), "RO": (-8.761, -63.904), "RR": (2.820, -60.672), "SC": (-27.595, -48.548),
    "SP": (-23.550, -46.633), "SE": (-10.947, -37.073), "TO": (-10.184, -48.333),
}
KNOWN = {
    "campinas|SP": (-22.906, -47.061), "sao jose dos campos|SP": (-23.179, -45.887), "santos|SP": (-23.961, -46.334),
    "ribeirao preto|SP": (-21.178, -47.810), "sorocaba|SP": (-23.502, -47.458), "barueri|SP": (-23.511, -46.876),
    "osasco|SP": (-23.533, -46.792), "guarulhos|SP": (-23.454, -46.533), "santo andre|SP": (-23.664, -46.538),
    "sao carlos|SP": (-22.017, -47.891), "niteroi|RJ": (-22.883, -43.104), "petropolis|RJ": (-22.505, -43.179),
    "uberlandia|MG": (-18.919, -48.277), "juiz de fora|MG": (-21.764, -43.350), "santa rita do sapucai|MG": (-22.252, -45.703),
    "londrina|PR": (-23.310, -51.163), "maringa|PR": (-23.420, -51.933), "joinville|SC": (-26.304, -48.846),
    "blumenau|SC": (-26.919, -49.066), "balneario camboriu|SC": (-26.991, -48.635), "chapeco|SC": (-27.101, -52.615),
    "gramado|RS": (-29.379, -50.874), "caxias do sul|RS": (-29.168, -51.179), "sao leopoldo|RS": (-29.760, -51.147),
    "campina grande|PB": (-7.230, -35.881), "vila velha|ES": (-20.330, -40.292),
}
UA = {"User-Agent": "RadarEventosBR/1.0 (mapa de eventos; contato via repositorio)"}


def _key(city: str | None, uf: str | None) -> str:
    return f"{norm(city).strip()}|{uf or ''}"


def geocode_events(events: list[dict], online: bool = True, max_queries: int = 150) -> None:
    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    queries = 0
    for e in events:
        uf = e.get("state")
        if not uf or e.get("format") == "online" and not e.get("city"):
            e["lat"] = e["lon"] = None
            continue
        k = _key(e.get("city"), uf)
        coords = KNOWN.get(k) or (cache.get(k) or {}).get("c")
        if coords is None and e.get("city") and online and queries < max_queries and k not in cache:
            queries += 1
            coords = _nominatim(e["city"], uf)
            if coords != "erro":  # falha de rede não fica no cache; tenta de novo amanhã
                cache[k] = {"c": coords}
            else:
                coords = None
            time.sleep(1.1)  # política de uso do Nominatim: no máximo 1 requisição/segundo
        e["geo_precision"] = "cidade" if coords else "estado"
        lat, lon = coords or CAPITALS.get(uf, (None, None))
        e["lat"], e["lon"] = lat, lon
    if queries:
        log.info("geocodificação: %d cidades novas consultadas", queries)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def _nominatim(city: str, uf: str):
    from scraper.core import UFS
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=15, params={
            "city": city, "state": UFS.get(uf, uf), "country": "Brasil", "format": "json", "limit": 1,
        })
        data = r.json() if r.status_code == 200 else []
        if data:
            return [round(float(data[0]["lat"]), 4), round(float(data[0]["lon"]), 4)]
    except (requests.RequestException, ValueError, KeyError) as exc:
        log.warning("geocodificação de %s/%s falhou: %s", city, uf, exc)
        return "erro"
    return None
