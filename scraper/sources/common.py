"""Utilitários HTTP e extração genérica de eventos via JSON-LD (schema.org/Event)."""
from __future__ import annotations

import json
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from scraper.core import Event

log = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 EventosBRBot/1.0"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_session = requests.Session()
_session.headers.update(HEADERS)


def fetch(url: str, *, method: str = "GET", retries: int = 3, timeout: int = 25, **kw) -> requests.Response | None:
    for attempt in range(retries):
        try:
            r = _session.request(method, url, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 404):
                log.warning("%s -> HTTP %s", url, r.status_code)
                return None
            log.warning("%s -> HTTP %s (tentativa %d)", url, r.status_code, attempt + 1)
        except requests.RequestException as e:
            log.warning("%s -> %s (tentativa %d)", url, e, attempt + 1)
        time.sleep(2 * (attempt + 1))
    return None


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _is_event(d: dict) -> bool:
    t = d.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.endswith("Event") for x in types) and bool(d.get("name"))


def _text(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        return v.get("name") or v.get("url") or v.get("@id")
    return str(v)


def event_from_jsonld(d: dict, source: str, fallback_url: str = "") -> Event:
    loc = d.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") if isinstance(loc, dict) else None
    city = state = None
    if isinstance(addr, dict):
        city = addr.get("addressLocality")
        state = addr.get("addressRegion")
    elif isinstance(addr, str):
        city = addr
    mode = str(d.get("eventAttendanceMode") or "")
    fmt = "presencial"
    if "Online" in mode:
        fmt = "online"
    elif "Mixed" in mode:
        fmt = "hibrido"
    if isinstance(loc, dict) and loc.get("@type") == "VirtualLocation":
        fmt = "online"
    offers = d.get("offers")
    price = None
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if isinstance(offers, dict):
        p = offers.get("price") or offers.get("lowPrice")
        if p is not None:
            price = "Gratuito" if str(p) in ("0", "0.0", "0.00") else f"R$ {p}"
    st = state if state and len(str(state)) == 2 else None
    return Event(
        name=_text(d.get("name")) or "",
        url=_text(d.get("url")) or fallback_url,
        source=source,
        start_date=d.get("startDate"),
        end_date=d.get("endDate"),
        description=re.sub(r"<[^>]+>", " ", _text(d.get("description")) or ""),
        city=city,
        state=st,
        venue=_text(loc.get("name")) if isinstance(loc, dict) else None,
        format=fmt,
        organizer=_text(d.get("organizer")),
        image=_text(d.get("image")),
        price=price,
    )


def extract_jsonld_events(html: str, source: str, page_url: str = "") -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[Event] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for d in _walk(data):
            if _is_event(d):
                events.append(event_from_jsonld(d, source, page_url))
    return events


def extract_next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
